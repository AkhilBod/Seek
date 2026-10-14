#!/usr/bin/env python3
"""Score Seek's retrieval strategies on the known-item benchmark.

Each query in queries.jsonl was written from one title's synopsis without
naming it. A strategy gets credit for ranking that title near the top.

    python eval/run_eval.py --database-url postgresql://...

Query embeddings are cached in eval/.embedding_cache.json so every strategy
sees the same vectors and reruns don't cost API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openai import OpenAI  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".embedding_cache.json"
TOP = 20


def embedder():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    client = OpenAI()
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(text: str) -> list[float]:
        if text not in cache:
            cache[text] = client.embeddings.create(model=model, input=text).data[0].embedding
            CACHE.write_text(json.dumps(cache))
        return cache[text]

    return embed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--queries", type=Path, default=HERE / "queries.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "results.json")
    ap.add_argument("--titles", action="store_true", help="use each target's exact title as the query instead")
    args = ap.parse_args()
    os.environ["DATABASE_URL"] = args.database_url

    from backend.app import search
    from backend.app.vector_store import hybrid_candidates

    embed = embedder()
    queries = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    if args.titles:
        queries = [{**item, "query": item["title"]} for item in queries]

    import psycopg

    with psycopg.connect(args.database_url) as conn:
        id_to_key = {
            str(row_id): str(netflix_id or tmdb_id or row_id)
            for row_id, netflix_id, tmdb_id in conn.execute("select id, netflix_id, tmdb_id from titles")
        }

    def legacy(q):
        search.embed_query = lambda text: embed(text)
        return [m.id for m in search.rank_movies(q, "Neutral", retrieval="legacy").results]

    def legacy_always_embed(q):
        search.embed_query = lambda text: embed(text)
        original = search.should_embed
        search.should_embed = lambda *a: True
        try:
            return [m.id for m in search.rank_movies(q, "Neutral", retrieval="legacy").results]
        finally:
            search.should_embed = original

    def vector_only(q):
        terms = search.tokenize(search.normalize_query(q))
        movies, _, _ = hybrid_candidates([], embed(search.normalize_query(q)), search.infer_intent(search.normalize_query(q)), k=TOP)
        return [m.id for m in movies]

    def text_only(q):
        n = search.normalize_query(q)
        movies, _, _ = hybrid_candidates(search.tokenize(n), None, search.infer_intent(n), k=TOP)
        return [m.id for m in movies]

    def hybrid(q):
        n = search.normalize_query(q)
        movies, _, _ = hybrid_candidates(search.tokenize(n), embed(n), search.infer_intent(n), k=100)
        return [m.id for m in movies]

    def hybrid_weighted(q):
        n = search.normalize_query(q)
        movies, _, _ = hybrid_candidates(search.tokenize(n), embed(n), search.infer_intent(n), k=100, keyword_weight=search.HYBRID_KEYWORD_WEIGHT)
        return [m.id for m in movies]

    def hybrid_ranked(q):
        search.embed_query = lambda text: embed(text)
        return [m.id for m in search.rank_movies(q, "Neutral", retrieval="hybrid").results]

    strategies = {
        "current pipeline": legacy,
        "current pipeline, always embed": legacy_always_embed,
        "keyword only (full-text)": text_only,
        "vector only (HNSW)": vector_only,
        "hybrid (RRF, equal weight)": hybrid,
        "hybrid (RRF, keyword x0.1)": hybrid_weighted,
        "shipped: rank_movies (hybrid)": hybrid_ranked,
    }

    # warm the embedding cache so latency below is retrieval only
    for item in queries:
        embed(search.normalize_query(item["query"]))

    report = {}
    for name, fn in strategies.items():
        hits1 = hits10 = 0
        rr = []
        latencies = []
        misses = []
        for item in queries:
            target = id_to_key[str(item["target_id"])]
            start = time.perf_counter()
            ids = fn(item["query"])[:TOP]
            latencies.append((time.perf_counter() - start) * 1000)
            rank = ids.index(target) + 1 if target in ids else None
            hits1 += rank == 1
            hits10 += bool(rank and rank <= 10)
            rr.append(1 / rank if rank else 0.0)
            if not rank:
                misses.append(item["query"])
        latencies.sort()
        n = len(queries)
        report[name] = {
            "recall@1": round(hits1 / n, 3),
            "recall@10": round(hits10 / n, 3),
            "mrr@20": round(statistics.mean(rr), 3),
            "p50_ms": round(latencies[n // 2], 1),
            "p95_ms": round(latencies[int(n * 0.95) - 1], 1),
            "sample_misses": misses[:5],
        }
        r = report[name]
        print(f"{name:34s} R@1 {r['recall@1']:.3f}  R@10 {r['recall@10']:.3f}  MRR {r['mrr@20']:.3f}  p50 {r['p50_ms']:7.1f}ms  p95 {r['p95_ms']:7.1f}ms")

    args.out.write_text(json.dumps({"queries": len(queries), "strategies": report}, indent=2))


if __name__ == "__main__":
    main()

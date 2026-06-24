#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import psycopg

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


FIELDS = [
    "netflix_id",
    "tmdb_id",
    "imdb_id",
    "title",
    "type",
    "synopsis",
    "description",
    "year",
    "genres",
    "cast",
    "cast_names",
    "director",
    "director_names",
    "country",
    "countries",
    "availability_region",
    "availability_regions",
    "release_year",
    "runtime",
    "duration",
    "poster_url",
    "backdrop_url",
    "netflix_poster_url",
    "netflix_large_image_url",
    "date_added",
    "expire_date",
    "source_url",
]


def split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("|", ",").split(",") if part.strip()]


def blank_to_none(value: Any) -> Any:
    return None if value == "" else value


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else data.get("results", [])
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def stable_id(row: dict[str, Any]) -> str:
    raw = f"{row.get('title', '')}:{row.get('release_year', '')}:{row.get('type', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def clean_row(row: dict[str, Any]) -> dict[str, Any] | None:
    title = str(row.get("title") or "").strip()
    if not title:
        return None
    cleaned = {field: row.get(field) for field in FIELDS}
    cleaned["netflix_id"] = row.get("netflix_id") or row.get("netflixid") or row.get("id") or stable_id(cleaned)
    cleaned["type"] = cleaned.get("type") or "Movie"
    cleaned["synopsis"] = cleaned.get("synopsis") or cleaned.get("description") or ""
    cleaned["genres"] = split_list(cleaned.get("genres"))
    cleaned["cast_names"] = split_list(cleaned.get("cast_names") or cleaned.get("cast"))
    cleaned["director_names"] = split_list(cleaned.get("director_names") or cleaned.get("director"))
    cleaned["countries"] = split_list(cleaned.get("countries") or cleaned.get("country"))
    cleaned["availability_regions"] = split_list(cleaned.get("availability_regions") or cleaned.get("availability_region"))
    cleaned["year"] = int(cleaned.get("year") or cleaned.get("release_year")) if str(cleaned.get("year") or cleaned.get("release_year") or "").isdigit() else None
    duration = str(cleaned.get("runtime") or cleaned.get("duration") or "").replace(" min", "")
    cleaned["runtime"] = int(duration) if duration.isdigit() else None
    for field in ("tmdb_id", "imdb_id", "poster_url", "backdrop_url", "netflix_poster_url", "netflix_large_image_url", "date_added", "expire_date", "source_url"):
        cleaned[field] = blank_to_none(cleaned.get(field))
    return cleaned


def embed_batch(rows: list[dict[str, Any]]) -> tuple[list[list[float] | None], int]:
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        return [None for _ in rows], 0
    client = OpenAI()
    texts = [
        " ".join(
            [
                row["title"],
                row.get("synopsis") or "",
                " ".join(row.get("genres") or []),
                " ".join(row.get("cast_names") or []),
                " ".join(row.get("director_names") or []),
            ]
        )
        for row in rows
    ]
    try:
        response = client.embeddings.create(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), input=texts)
        return [item.embedding for item in response.data], 0
    except Exception:
        return [None for _ in rows], len(rows)


def vector_literal(embedding: list[float] | None) -> str | None:
    if not embedding:
        return None
    return "[" + ",".join(str(value) for value in embedding) + "]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a movie/show catalog into Seek.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")

    rows = [cleaned for row in load_rows(args.source) if (cleaned := clean_row(row))]
    imported = skipped = embedding_failures = 0

    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            for index in range(0, len(rows), args.batch_size):
                batch = rows[index : index + args.batch_size]
                embeddings, failures = embed_batch(batch)
                embedding_failures += failures
                for row, embedding in zip(batch, embeddings):
                    cur.execute(
                        """
                        insert into titles (
                          netflix_id, tmdb_id, imdb_id, title, type, synopsis, year, runtime,
                          genres, cast_names, director_names, countries, availability_regions,
                          poster_url, backdrop_url, netflix_poster_url, netflix_large_image_url,
                          date_added, expire_date, source_url, embedding, updated_at
                        )
                        values (
                          %(netflix_id)s, %(tmdb_id)s, %(imdb_id)s, %(title)s, %(type)s, %(synopsis)s, %(year)s, %(runtime)s,
                          %(genres)s, %(cast_names)s, %(director_names)s, %(countries)s, %(availability_regions)s,
                          %(poster_url)s, %(backdrop_url)s, %(netflix_poster_url)s, %(netflix_large_image_url)s,
                          %(date_added)s, %(expire_date)s, %(source_url)s, %(embedding)s::vector, now()
                        )
                        on conflict (netflix_id) do nothing
                        """,
                        {**row, "embedding": vector_literal(embedding)},
                    )
                    if cur.rowcount:
                        imported += 1
                    else:
                        skipped += 1
            cur.execute(
                """
                insert into import_logs (source_name, total_rows, imported_rows, skipped_rows, embedding_failures)
                values (%s, %s, %s, %s, %s)
                """,
                (args.source.name, len(rows), imported, skipped, embedding_failures),
            )
    print(json.dumps({"source": args.source.name, "total_rows": len(rows), "imported": imported, "skipped": skipped, "embedding_failures": embedding_failures}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


TMDB_BASE = "https://api.themoviedb.org/3"
DEFAULT_DB = Path(__file__).resolve().parents[1] / "backend" / "data" / "seek_catalog.sqlite"
load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


def tmdb_get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise SystemExit("TMDB_API_KEY is required.")
    response = client.get(f"{TMDB_BASE}/{path.lstrip('/')}", params={**params, "api_key": api_key}, timeout=30)
    response.raise_for_status()
    return response.json()


def names(values: list[dict[str, Any]], limit: int = 14) -> list[str]:
    return [item["name"] for item in values[:limit] if item.get("name")]


def runtime(details: dict[str, Any], media_type: str) -> int | None:
    if media_type == "movie":
        return details.get("runtime")
    runtimes = details.get("episode_run_time") or []
    return runtimes[0] if runtimes else None


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("pragma table_info(titles)").fetchall()}
    if "tmdb_details_enriched_at" not in existing:
        conn.execute("alter table titles add column tmdb_details_enriched_at text")


def rows_to_enrich(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        select netflix_id, tmdb_id, type, title
        from titles
        where tmdb_details_enriched_at is null
        order by
          case when cast_names = '[]' or director_names = '[]' or runtime is null then 0 else 1 end,
          year desc nulls last,
          title
        limit ?
        """,
        (limit,),
    ).fetchall()


def enrich(conn: sqlite3.Connection, row: sqlite3.Row, details: dict[str, Any], media_type: str) -> None:
    credits = details.get("credits") or {}
    crew = credits.get("crew") or []
    director_jobs = {"Director", "Creator", "Executive Producer"}
    directors = [item.get("name") for item in crew if item.get("job") in director_jobs and item.get("name")]
    countries = [item.get("iso_3166_1") for item in details.get("production_countries") or [] if item.get("iso_3166_1")]
    imdb_id = (details.get("external_ids") or {}).get("imdb_id") or details.get("imdb_id")
    overview = details.get("overview")
    run = runtime(details, media_type)

    conn.execute(
        """
        update titles set
          imdb_id = coalesce(?, imdb_id),
          synopsis = coalesce(?, synopsis),
          runtime = coalesce(?, runtime),
          cast_names = case when ? != '[]' then ? else cast_names end,
          director_names = case when ? != '[]' then ? else director_names end,
          countries = case when ? != '[]' then ? else countries end,
          tmdb_details_enriched_at = current_timestamp,
          updated_at = current_timestamp
        where netflix_id = ?
        """,
        (
            imdb_id,
            overview,
            run,
            json.dumps(names(credits.get("cast") or [])),
            json.dumps(names(credits.get("cast") or [])),
            json.dumps(directors[:10]),
            json.dumps(directors[:10]),
            json.dumps(countries),
            json.dumps(countries),
            row["netflix_id"],
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich existing Seek titles with TMDB details, credits, runtime, and external IDs.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--delay", type=float, default=0.02)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    ensure_columns(conn)
    rows = rows_to_enrich(conn, args.limit)
    enriched = skipped = 0
    with httpx.Client() as client:
        for row in rows:
            try:
                media_type = "tv" if row["type"] == "Show" else "movie"
                details = tmdb_get(client, f"{media_type}/{row['tmdb_id']}", {"append_to_response": "credits,external_ids"})
                enrich(conn, row, details, media_type)
                enriched += 1
                if enriched % 50 == 0:
                    conn.commit()
                time.sleep(args.delay)
            except Exception:
                skipped += 1
    conn.commit()
    total = conn.execute("select count(*) from titles where tmdb_details_enriched_at is not null").fetchone()[0]
    conn.close()
    print(json.dumps({"attempted": len(rows), "enriched": enriched, "skipped": skipped, "total_tmdb_details_enriched": total}, indent=2))


if __name__ == "__main__":
    main()

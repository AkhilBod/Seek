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
        return {}
    response = client.get(f"{TMDB_BASE}/{path.lstrip('/')}", params={**params, "api_key": api_key}, timeout=30)
    response.raise_for_status()
    return response.json()


def omdb_get(client: httpx.Client, imdb_id: str) -> dict[str, Any]:
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key:
        raise SystemExit("OMDB_API_KEY is required.")
    response = client.get("http://www.omdbapi.com/", params={"i": imdb_id, "apikey": api_key, "plot": "full"}, timeout=30)
    if response.status_code == 401:
        return {"Response": "False", "Error": "OMDb unauthorized"}
    response.raise_for_status()
    return response.json()


def split_people(value: str | None) -> list[str]:
    if not value or value == "N/A":
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_runtime(value: str | None) -> int | None:
    if not value or value == "N/A":
        return None
    digits = "".join(char for char in value if char.isdigit())
    return int(digits) if digits else None


def none_if_na(value: Any) -> Any:
    return None if value in ("N/A", "", None) else value


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("pragma table_info(titles)").fetchall()}
    additions = {
        "rated": "text",
        "imdb_rating": "text",
        "imdb_votes": "text",
        "metascore": "text",
        "awards": "text",
        "omdb_poster_url": "text",
        "omdb_enriched_at": "text",
    }
    for column, column_type in additions.items():
        if column not in existing:
            conn.execute(f"alter table titles add column {column} {column_type}")


def rows_to_enrich(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        select netflix_id, tmdb_id, imdb_id, type, title
        from titles
        where omdb_enriched_at is null
        order by
          case when imdb_id is not null then 0 else 1 end,
          year desc nulls last,
          title
        limit ?
        """,
        (limit,),
    ).fetchall()


def fetch_imdb_id(client: httpx.Client, row: sqlite3.Row) -> str | None:
    if row["imdb_id"]:
        return row["imdb_id"]
    media_type = "tv" if row["type"] == "Show" else "movie"
    payload = tmdb_get(client, f"{media_type}/{row['tmdb_id']}/external_ids", {})
    imdb_id = payload.get("imdb_id")
    return imdb_id if imdb_id and imdb_id != "N/A" else None


def enrich_row(conn: sqlite3.Connection, row: sqlite3.Row, imdb_id: str, payload: dict[str, Any]) -> None:
    if payload.get("Response") == "False":
        conn.execute(
            "update titles set imdb_id = coalesce(imdb_id, ?), omdb_enriched_at = current_timestamp where netflix_id = ?",
            (imdb_id, row["netflix_id"]),
        )
        return

    cast_names = split_people(payload.get("Actors"))
    director_names = split_people(payload.get("Director"))
    runtime = parse_runtime(payload.get("Runtime"))
    plot = none_if_na(payload.get("Plot"))
    poster = none_if_na(payload.get("Poster"))

    conn.execute(
        """
        update titles set
          imdb_id = coalesce(imdb_id, ?),
          synopsis = coalesce(?, synopsis),
          runtime = coalesce(?, runtime),
          cast_names = case when ? != '[]' then ? else cast_names end,
          director_names = case when ? != '[]' then ? else director_names end,
          rated = ?,
          imdb_rating = ?,
          imdb_votes = ?,
          metascore = ?,
          awards = ?,
          omdb_poster_url = ?,
          poster_url = coalesce(poster_url, ?),
          omdb_enriched_at = current_timestamp,
          updated_at = current_timestamp
        where netflix_id = ?
        """,
        (
            imdb_id,
            plot,
            runtime,
            json.dumps(cast_names),
            json.dumps(cast_names),
            json.dumps(director_names),
            json.dumps(director_names),
            none_if_na(payload.get("Rated")),
            none_if_na(payload.get("imdbRating")),
            none_if_na(payload.get("imdbVotes")),
            none_if_na(payload.get("Metascore")),
            none_if_na(payload.get("Awards")),
            poster,
            poster,
            row["netflix_id"],
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich the local Seek catalog with OMDb metadata.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=900)
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    ensure_columns(conn)
    rows = rows_to_enrich(conn, args.limit)
    enriched = skipped = 0

    with httpx.Client() as client:
        for row in rows:
            try:
                imdb_id = fetch_imdb_id(client, row)
                if not imdb_id:
                    skipped += 1
                    conn.execute("update titles set omdb_enriched_at = current_timestamp where netflix_id = ?", (row["netflix_id"],))
                    continue
                payload = omdb_get(client, imdb_id)
                lower_payload = str(payload).lower()
                if "limit" in lower_payload or "invalid api key" in lower_payload or "unauthorized" in lower_payload:
                    print(json.dumps({"stopped": payload, "enriched": enriched, "skipped": skipped}, indent=2))
                    break
                enrich_row(conn, row, imdb_id, payload)
                enriched += 1
                if enriched % 50 == 0:
                    conn.commit()
                time.sleep(args.delay)
            except Exception as exc:
                skipped += 1
                print(f"Skipped {row['title']}: {type(exc).__name__}")
    conn.commit()
    total_enriched = conn.execute("select count(*) from titles where omdb_enriched_at is not null").fetchone()[0]
    conn.close()
    print(json.dumps({"attempted": len(rows), "enriched": enriched, "skipped": skipped, "total_omdb_enriched": total_enriched}, indent=2))


if __name__ == "__main__":
    main()

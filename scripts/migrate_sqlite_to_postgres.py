#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import psycopg


DEFAULT_SQLITE = Path(__file__).resolve().parents[1] / "backend" / "data" / "seek_catalog.sqlite"


def vector_literal(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return raw if raw.startswith("[") else None
    return "[" + ",".join(str(value) for value in values) + "]"


def json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value if str(item)]


def rows_from_sqlite(path: Path) -> list[sqlite3.Row]:
    if not path.exists():
        raise SystemExit(f"SQLite catalog not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    columns = {row["name"] for row in conn.execute("pragma table_info(titles)").fetchall()}
    select_columns = [
        "netflix_id",
        "tmdb_id",
        "imdb_id",
        "title",
        "type",
        "synopsis",
        "year",
        "runtime",
        "genres",
        "cast_names",
        "director_names",
        "countries",
        "availability_regions",
        "poster_url",
        "backdrop_url",
        "netflix_poster_url",
        "netflix_large_image_url",
        "date_added",
        "expire_date",
        "source_url",
        "embedding",
    ]
    expressions = [column if column in columns else f"null as {column}" for column in select_columns]
    rows = conn.execute(f"select {', '.join(expressions)} from titles").fetchall()
    conn.close()
    return rows


def row_params(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "netflix_id": row["netflix_id"],
        "tmdb_id": row["tmdb_id"],
        "imdb_id": row["imdb_id"],
        "title": row["title"],
        "type": row["type"],
        "synopsis": row["synopsis"],
        "year": row["year"],
        "runtime": row["runtime"],
        "genres": json_list(row["genres"]),
        "cast_names": json_list(row["cast_names"]),
        "director_names": json_list(row["director_names"]),
        "countries": json_list(row["countries"]),
        "availability_regions": json_list(row["availability_regions"]),
        "poster_url": row["poster_url"],
        "backdrop_url": row["backdrop_url"],
        "netflix_poster_url": row["netflix_poster_url"],
        "netflix_large_image_url": row["netflix_large_image_url"],
        "date_added": row["date_added"],
        "expire_date": row["expire_date"],
        "source_url": row["source_url"],
        "embedding": vector_literal(row["embedding"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate the local Seek SQLite catalog to Postgres/pgvector.")
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")

    rows = rows_from_sqlite(args.sqlite_path)
    imported = skipped = 0

    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("drop index if exists titles_embedding_idx")
            conn.commit()
            for index in range(0, len(rows), args.batch_size):
                batch = rows[index : index + args.batch_size]
                params = [row_params(row) for row in batch]
                cur.executemany(
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
                    on conflict (netflix_id) do update set
                      tmdb_id = excluded.tmdb_id,
                      imdb_id = excluded.imdb_id,
                      title = excluded.title,
                      type = excluded.type,
                      synopsis = excluded.synopsis,
                      year = excluded.year,
                      runtime = excluded.runtime,
                      genres = excluded.genres,
                      cast_names = excluded.cast_names,
                      director_names = excluded.director_names,
                      countries = excluded.countries,
                      availability_regions = excluded.availability_regions,
                      poster_url = excluded.poster_url,
                      backdrop_url = excluded.backdrop_url,
                      netflix_poster_url = excluded.netflix_poster_url,
                      netflix_large_image_url = excluded.netflix_large_image_url,
                      date_added = excluded.date_added,
                      expire_date = excluded.expire_date,
                      source_url = excluded.source_url,
                      embedding = excluded.embedding,
                      updated_at = now()
                    """,
                    params,
                )
                imported += len(batch)
                conn.commit()
                print(f"Migrated {min(index + args.batch_size, len(rows))}/{len(rows)} rows")

    print(json.dumps({"total_rows": len(rows), "imported_or_updated": imported, "skipped": skipped}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
NETFLIX_PROVIDER_ID = 8
JUSTWATCH_NETFLIX = "https://www.justwatch.com/us/provider/netflix"
TMDB_SOURCE = "https://www.themoviedb.org"
DEFAULT_DB = Path(__file__).resolve().parents[1] / "backend" / "data" / "seek_catalog.sqlite"
load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


def tmdb_headers() -> dict[str, str]:
    token = os.getenv("TMDB_READ_ACCESS_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def tmdb_get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("TMDB_API_KEY")
    headers = tmdb_headers()
    if not api_key and not headers:
        raise SystemExit("Set TMDB_API_KEY or TMDB_READ_ACCESS_TOKEN.")
    query = dict(params)
    if api_key and not headers:
        query["api_key"] = api_key
    response = client.get(f"{TMDB_BASE}/{path.lstrip('/')}", params=query, headers=headers, timeout=45)
    response.raise_for_status()
    return response.json()


def image(path: str | None, size: str) -> str | None:
    return f"{TMDB_IMAGE_BASE}/{size}{path}" if path else None


def year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).year
    except ValueError:
        return None


def runtime_from_details(details: dict[str, Any], media_type: str) -> int | None:
    if media_type == "movie":
        return details.get("runtime")
    runtimes = details.get("episode_run_time") or []
    return runtimes[0] if runtimes else None


def names(values: list[dict[str, Any]], limit: int = 12) -> list[str]:
    return [item["name"] for item in values[:limit] if item.get("name")]


def genre_maps(client: httpx.Client) -> dict[str, dict[int, str]]:
    maps: dict[str, dict[int, str]] = {}
    for media_type in ("movie", "tv"):
        payload = tmdb_get(client, f"genre/{media_type}/list", {})
        maps[media_type] = {item["id"]: item["name"] for item in payload.get("genres", [])}
    return maps


def fetch_details(client: httpx.Client, tmdb_id: int, media_type: str) -> dict[str, Any]:
    return tmdb_get(client, f"{media_type}/{tmdb_id}", {"append_to_response": "credits,external_ids"})


def normalize(result: dict[str, Any], details: dict[str, Any], region: str, media_type: str) -> dict[str, Any]:
    credits = details.get("credits") or {}
    crew = credits.get("crew") or []
    directors = [item.get("name") for item in crew if item.get("job") in ("Director", "Creator") and item.get("name")]
    imdb_id = (details.get("external_ids") or {}).get("imdb_id") or details.get("imdb_id")
    title = details.get("title") or details.get("name") or result.get("title") or result.get("name")
    release_date = details.get("release_date") or details.get("first_air_date")
    genres = names(details.get("genres") or [], 10)
    countries = [item.get("iso_3166_1") for item in details.get("production_countries") or [] if item.get("iso_3166_1")]
    return {
        "netflix_id": f"tmdb:{media_type}:{details['id']}",
        "tmdb_id": str(details["id"]),
        "imdb_id": imdb_id,
        "title": title,
        "type": "Show" if media_type == "tv" else "Movie",
        "synopsis": details.get("overview") or result.get("overview") or "",
        "year": year_from_date(release_date),
        "runtime": runtime_from_details(details, media_type),
        "genres": genres,
        "cast_names": names((credits.get("cast") or []), 14),
        "director_names": directors[:8],
        "countries": countries,
        "availability_regions": [region],
        "poster_url": image(details.get("poster_path") or result.get("poster_path"), "w500"),
        "backdrop_url": image(details.get("backdrop_path") or result.get("backdrop_path"), "w1280"),
        "netflix_poster_url": None,
        "netflix_large_image_url": None,
        "source_url": JUSTWATCH_NETFLIX,
    }


def normalize_fast(result: dict[str, Any], region: str, media_type: str, genres_by_id: dict[int, str], source_url: str) -> dict[str, Any]:
    title = result.get("title") or result.get("name")
    release_date = result.get("release_date") or result.get("first_air_date")
    tmdb_id = result["id"]
    return {
        "netflix_id": f"tmdb:{media_type}:{tmdb_id}",
        "tmdb_id": str(tmdb_id),
        "imdb_id": None,
        "title": title,
        "type": "Show" if media_type == "tv" else "Movie",
        "synopsis": result.get("overview") or "",
        "year": year_from_date(release_date),
        "runtime": None,
        "genres": [genres_by_id[item] for item in result.get("genre_ids", []) if item in genres_by_id],
        "cast_names": [],
        "director_names": [],
        "countries": [item for item in result.get("origin_country", []) if item] if media_type == "tv" else [],
        "availability_regions": [region],
        "poster_url": image(result.get("poster_path"), "w500"),
        "backdrop_url": image(result.get("backdrop_path"), "w1280"),
        "netflix_poster_url": None,
        "netflix_large_image_url": None,
        "source_url": source_url,
    }


def embedding_text(row: dict[str, Any]) -> str:
    return " ".join(
        [
            row["title"],
            row.get("synopsis") or "",
            " ".join(row.get("genres") or []),
            " ".join(row.get("cast_names") or []),
            " ".join(row.get("director_names") or []),
        ]
    )


def embed_rows(rows: list[dict[str, Any]], batch_size: int) -> int:
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        return 0
    client = OpenAI()
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    embedded = 0
    pending = [row for row in rows if not row.get("embedding")]
    for index in range(0, len(pending), batch_size):
        batch = pending[index : index + batch_size]
        try:
            response = client.embeddings.create(model=model, input=[embedding_text(row) for row in batch])
            for row, item in zip(batch, response.data):
                row["embedding"] = item.embedding
                embedded += 1
        except Exception as exc:
            print(f"Embedding batch failed at offset {index}: {exc}")
    return embedded


def hydrate_existing_embeddings(rows: list[dict[str, Any]], db: Path) -> int:
    if not db.exists():
        return 0
    conn = sqlite3.connect(db)
    existing = dict(conn.execute("select netflix_id, embedding from titles where embedding is not null").fetchall())
    conn.close()
    reused = 0
    for row in rows:
        embedding = existing.get(row["netflix_id"])
        if embedding:
            row["embedding"] = json.loads(embedding)
            reused += 1
    return reused


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists titles (
          netflix_id text primary key,
          tmdb_id text,
          imdb_id text,
          title text not null,
          type text,
          synopsis text,
          year integer,
          runtime integer,
          genres text,
          cast_names text,
          director_names text,
          countries text,
          availability_regions text,
          poster_url text,
          backdrop_url text,
          netflix_poster_url text,
          netflix_large_image_url text,
          source_url text,
          embedding text,
          created_at text default current_timestamp,
          updated_at text default current_timestamp
        )
        """
    )
    conn.execute("create index if not exists titles_title_idx on titles(title)")
    conn.execute("create index if not exists titles_tmdb_idx on titles(tmdb_id)")
    conn.execute("create index if not exists titles_imdb_idx on titles(imdb_id)")


def upsert_rows(rows: list[dict[str, Any]], db: Path) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    ensure_schema(conn)
    for row in rows:
        conn.execute(
            """
            insert into titles (
              netflix_id, tmdb_id, imdb_id, title, type, synopsis, year, runtime,
              genres, cast_names, director_names, countries, availability_regions,
              poster_url, backdrop_url, netflix_poster_url, netflix_large_image_url,
              source_url, embedding, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            on conflict(netflix_id) do update set
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
              source_url = excluded.source_url,
              embedding = coalesce(excluded.embedding, titles.embedding),
              updated_at = current_timestamp
            """,
            (
                row["netflix_id"],
                row["tmdb_id"],
                row["imdb_id"],
                row["title"],
                row["type"],
                row["synopsis"],
                row["year"],
                row["runtime"],
                json.dumps(row["genres"]),
                json.dumps(row["cast_names"]),
                json.dumps(row["director_names"]),
                json.dumps(row["countries"]),
                json.dumps(row["availability_regions"]),
                row["poster_url"],
                row["backdrop_url"],
                row["netflix_poster_url"],
                row["netflix_large_image_url"],
                row["source_url"],
                json.dumps(row.get("embedding")) if row.get("embedding") else None,
            ),
        )
    conn.commit()
    conn.close()


def discover(
    client: httpx.Client,
    media_type: str,
    region: str,
    pages: int,
    delay: float,
    provider: str,
    details: bool,
    genres_by_type: dict[str, dict[int, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "page": page,
            "sort_by": "popularity.desc",
            "include_adult": "false",
        }
        source_url = TMDB_SOURCE
        if provider == "netflix":
            params.update(
                {
                    "watch_region": region,
                    "with_watch_providers": NETFLIX_PROVIDER_ID,
                }
            )
            source_url = JUSTWATCH_NETFLIX
        payload = tmdb_get(
            client,
            f"discover/{media_type}",
            params,
        )
        for result in payload.get("results", []):
            tmdb_id = result.get("id")
            if not tmdb_id or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            if details:
                detail_payload = fetch_details(client, tmdb_id, media_type)
                row = normalize(result, detail_payload, region, media_type)
                row["source_url"] = source_url
            else:
                row = normalize_fast(result, region, media_type, genres_by_type[media_type], source_url)
            rows.append(row)
            time.sleep(delay)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local vector catalog from TMDB.")
    parser.add_argument("--regions", default=os.getenv("TMDB_WATCH_REGIONS", "US"))
    parser.add_argument("--pages", type=int, default=10, help="Pages per media type and region. TMDB pages are 20 titles.")
    parser.add_argument("--provider", choices=["netflix", "all"], default="netflix")
    parser.add_argument("--details", action="store_true", help="Fetch credits, IMDb IDs, runtimes, and production countries for each title.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.02)
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args()

    by_id: dict[str, dict[str, Any]] = {}
    with httpx.Client() as client:
        genres_by_type = genre_maps(client)
        for region in [item.strip().upper() for item in args.regions.split(",") if item.strip()]:
            for media_type in ("movie", "tv"):
                for row in discover(client, media_type, region, args.pages, args.delay, args.provider, args.details, genres_by_type):
                    existing = by_id.get(row["netflix_id"])
                    if existing:
                        row["availability_regions"] = sorted(set(existing["availability_regions"] + row["availability_regions"]))
                    by_id[row["netflix_id"]] = row

    rows = list(by_id.values())
    reused = hydrate_existing_embeddings(rows, args.db)
    embedded = 0 if args.no_embeddings else embed_rows(rows, args.batch_size)
    upsert_rows(rows, args.db)
    print(json.dumps({"database": str(args.db), "titles": len(rows), "reused_embeddings": reused, "embedded": embedded}, indent=2))


if __name__ == "__main__":
    main()

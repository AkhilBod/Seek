#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
import psycopg

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
NETFLIX_PROVIDER_URL = "https://www.justwatch.com/us/provider/netflix"
load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


def parse_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("|", ",").split(",") if part.strip()]


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return None


def unogs_headers() -> dict[str, str]:
    api_key = os.getenv("UNOGS_API_KEY")
    host = os.getenv("UNOGS_API_HOST", "unogs-unogs-v1.p.rapidapi.com")
    if not api_key:
        raise SystemExit("UNOGS_API_KEY is required.")
    return {"x-rapidapi-key": api_key, "x-rapidapi-host": host}


def unogs_get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv("UNOGS_API_BASE_URL", "https://unogs-unogs-v1.p.rapidapi.com").rstrip("/")
    response = client.get(f"{base_url}/{path.lstrip('/')}", params=params, headers=unogs_headers(), timeout=45)
    response.raise_for_status()
    return response.json()


def extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "items", "titles", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload, list):
        return payload
    return []


def has_next_page(payload: dict[str, Any], rows: list[dict[str, Any]], page: int, page_size: int) -> bool:
    total = parse_int(first_present(payload, "total", "total_results", "count"))
    if total is not None:
        return page * page_size < total
    return len(rows) >= page_size


def fetch_unogs_country(client: httpx.Client, country: str, page_size: int, delay: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    # Endpoint names differ by uNoGS plan/version. Keep these overrideable via env.
    path = os.getenv("UNOGS_SEARCH_PATH", "search/titles")
    while True:
        payload = unogs_get(
            client,
            path,
            {
                "country_list": country,
                "country": country,
                "limit": page_size,
                "offset": (page - 1) * page_size,
                "page": page,
                "type": "movie,series",
                "orderby": "date",
            },
        )
        page_rows = extract_results(payload)
        rows.extend(page_rows)
        if not has_next_page(payload, page_rows, page, page_size):
            break
        page += 1
        time.sleep(delay)
    return rows


def fetch_unogs_details(client: httpx.Client, netflix_id: str) -> dict[str, Any]:
    path = os.getenv("UNOGS_DETAIL_PATH", "title/details")
    try:
        return unogs_get(client, path, {"netflixid": netflix_id, "netflix_id": netflix_id})
    except httpx.HTTPError:
        return {}


def tmdb_get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        return {}
    response = client.get(
        f"https://api.themoviedb.org/3/{path.lstrip('/')}",
        params={**params, "api_key": api_key},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def tmdb_image(path: str | None, size: str) -> str | None:
    return f"{TMDB_IMAGE_BASE}/{size}{path}" if path else None


def enrich_tmdb(client: httpx.Client, row: dict[str, Any]) -> dict[str, Any]:
    imdb_id = row.get("imdb_id")
    title = row["title"]
    year = row.get("year")
    tmdb_id = None
    media_type = None
    poster_url = None
    backdrop_url = None

    if imdb_id and os.getenv("TMDB_API_KEY"):
        payload = tmdb_get(client, f"find/{imdb_id}", {"external_source": "imdb_id"})
        candidates = payload.get("movie_results") or payload.get("tv_results") or []
        if candidates:
            chosen = candidates[0]
            tmdb_id = str(chosen.get("id")) if chosen.get("id") else None
            media_type = "movie" if payload.get("movie_results") else "tv"
            poster_url = tmdb_image(chosen.get("poster_path"), "w500")
            backdrop_url = tmdb_image(chosen.get("backdrop_path"), "w1280")

    if not tmdb_id and os.getenv("TMDB_API_KEY"):
        payload = tmdb_get(client, "search/multi", {"query": title, "year": year or ""})
        candidates = [item for item in payload.get("results", []) if item.get("media_type") in ("movie", "tv")]
        if candidates:
            chosen = candidates[0]
            tmdb_id = str(chosen.get("id")) if chosen.get("id") else None
            media_type = chosen.get("media_type")
            poster_url = tmdb_image(chosen.get("poster_path"), "w500")
            backdrop_url = tmdb_image(chosen.get("backdrop_path"), "w1280")

    return {
        **row,
        "tmdb_id": tmdb_id or row.get("tmdb_id"),
        "type": "Show" if media_type == "tv" else row.get("type"),
        "poster_url": poster_url or row.get("poster_url") or row.get("netflix_poster_url"),
        "backdrop_url": backdrop_url or row.get("backdrop_url") or row.get("netflix_large_image_url"),
    }


def normalize_unogs(row: dict[str, Any], region: str, details: dict[str, Any] | None = None) -> dict[str, Any] | None:
    merged = {**row, **(details or {})}
    netflix_id = str(first_present(merged, "netflix_id", "netflixid", "nfid", "id") or "").strip()
    title = str(first_present(merged, "title", "title_name", "name") or "").strip()
    if not netflix_id or not title:
        return None

    title_type = str(first_present(merged, "type", "title_type", "vtype") or "Movie").lower()
    runtime = first_present(merged, "runtime", "duration")
    if isinstance(runtime, str) and runtime.endswith(" min"):
        runtime = runtime.replace(" min", "")

    return {
        "netflix_id": netflix_id,
        "tmdb_id": first_present(merged, "tmdb_id", "tmdbid"),
        "imdb_id": first_present(merged, "imdb_id", "imdbid"),
        "title": title,
        "type": "Show" if title_type in ("series", "show", "tv") else "Movie",
        "synopsis": first_present(merged, "synopsis", "overview", "description") or "",
        "year": parse_int(first_present(merged, "year", "release_year")),
        "runtime": parse_int(runtime),
        "genres": parse_list(first_present(merged, "genres", "genre")),
        "cast_names": parse_list(first_present(merged, "cast", "cast_names")),
        "director_names": parse_list(first_present(merged, "director", "directors", "director_names")),
        "countries": parse_list(first_present(merged, "country", "countries")),
        "availability_regions": sorted(set(parse_list(first_present(merged, "country_list", "availability_regions")) + [region])),
        "netflix_poster_url": first_present(merged, "poster", "poster_url", "image"),
        "netflix_large_image_url": first_present(merged, "large_image", "largeimage", "backdrop", "backdrop_url"),
        "date_added": parse_date(first_present(merged, "date_added", "dateadded")),
        "expire_date": parse_date(first_present(merged, "expire_date", "expiredate")),
        "source_url": NETFLIX_PROVIDER_URL,
    }


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


def upsert_titles(database_url: str, rows: list[dict[str, Any]], batch_size: int) -> dict[str, int]:
    imported = updated = embedding_failures = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for index in range(0, len(rows), batch_size):
                batch = rows[index : index + batch_size]
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
                          %(date_added)s, %(expire_date)s, %(source_url)s, %(embedding)s, now()
                        )
                        on conflict (netflix_id) do update set
                          tmdb_id = coalesce(excluded.tmdb_id, titles.tmdb_id),
                          imdb_id = coalesce(excluded.imdb_id, titles.imdb_id),
                          title = excluded.title,
                          type = excluded.type,
                          synopsis = excluded.synopsis,
                          year = excluded.year,
                          runtime = excluded.runtime,
                          genres = excluded.genres,
                          cast_names = excluded.cast_names,
                          director_names = excluded.director_names,
                          countries = excluded.countries,
                          availability_regions = (
                            select array(select distinct unnest(titles.availability_regions || excluded.availability_regions))
                          ),
                          poster_url = coalesce(excluded.poster_url, titles.poster_url),
                          backdrop_url = coalesce(excluded.backdrop_url, titles.backdrop_url),
                          netflix_poster_url = coalesce(excluded.netflix_poster_url, titles.netflix_poster_url),
                          netflix_large_image_url = coalesce(excluded.netflix_large_image_url, titles.netflix_large_image_url),
                          date_added = coalesce(excluded.date_added, titles.date_added),
                          expire_date = coalesce(excluded.expire_date, titles.expire_date),
                          source_url = excluded.source_url,
                          embedding = coalesce(excluded.embedding, titles.embedding),
                          updated_at = now()
                        """,
                        {**row, "embedding": embedding},
                    )
                    if cur.statusmessage.endswith(" 1"):
                        imported += 1
                    else:
                        updated += 1
            cur.execute(
                """
                insert into import_logs (source_name, total_rows, imported_rows, skipped_rows, embedding_failures)
                values (%s, %s, %s, %s, %s)
                """,
                ("unogs-netflix", len(rows), imported, updated, embedding_failures),
            )
    return {"imported_or_updated": imported + updated, "embedding_failures": embedding_failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the current Netflix catalog from uNoGS and enrich artwork from TMDB.")
    parser.add_argument("--countries", default=os.getenv("UNOGS_COUNTRIES", "US"), help="Comma-separated country codes.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--details", action="store_true", help="Fetch per-title uNoGS details before TMDB enrichment.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.database_url and not args.dry_run:
        raise SystemExit("DATABASE_URL is required unless --dry-run is used.")

    normalized_by_netflix_id: dict[str, dict[str, Any]] = {}
    with httpx.Client() as client:
        for country in [item.strip().upper() for item in args.countries.split(",") if item.strip()]:
            for raw in fetch_unogs_country(client, country, args.page_size, args.delay):
                netflix_id = str(first_present(raw, "netflix_id", "netflixid", "nfid", "id") or "")
                details = fetch_unogs_details(client, netflix_id) if args.details and netflix_id else {}
                normalized = normalize_unogs(raw, country, details)
                if not normalized:
                    continue
                existing = normalized_by_netflix_id.get(normalized["netflix_id"])
                if existing:
                    normalized["availability_regions"] = sorted(set(existing["availability_regions"] + normalized["availability_regions"]))
                normalized_by_netflix_id[normalized["netflix_id"]] = enrich_tmdb(client, normalized)
                time.sleep(args.delay)

    rows = list(normalized_by_netflix_id.values())
    if args.dry_run:
        print(json.dumps({"count": len(rows), "sample": rows[:3]}, indent=2))
        return

    result = upsert_titles(args.database_url, rows, args.batch_size)
    print(json.dumps({"source": "unogs-netflix", "total_titles": len(rows), **result}, indent=2))


if __name__ == "__main__":
    main()

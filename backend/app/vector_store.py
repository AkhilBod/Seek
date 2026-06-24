from __future__ import annotations

import json
import os
import sqlite3
from functools import lru_cache
from math import sqrt
from pathlib import Path

import numpy as np

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

from .models import Movie


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "data" / "seek_catalog.sqlite"


def db_path() -> Path:
    return Path(os.getenv("SEEK_SQLITE_PATH", str(DEFAULT_SQLITE_PATH)))


def database_url() -> str | None:
    url = os.getenv("DATABASE_URL")
    if url and psycopg is None:
        raise RuntimeError("DATABASE_URL is set, but psycopg is not installed. Run pip install -r backend/requirements.txt.")
    return url


def has_catalog() -> bool:
    if database_url():
        return True
    path = db_path()
    return path.exists() and path.stat().st_size > 0


def parse_json_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item)]
    except Exception:
        pass
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_embedding(value) -> list[float] | None:
    if not value:
        return None
    if isinstance(value, list):
        return [float(item) for item in value]
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return [float(part) for part in text.split(",") if part.strip()]
    except ValueError:
        return None


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    a_norm = sqrt(sum(x * x for x in a))
    b_norm = sqrt(sum(y * y for y in b))
    if not a_norm or not b_norm:
        return 0.0
    return dot / (a_norm * b_norm)


@lru_cache(maxsize=1)
def load_titles() -> list[Movie]:
    if not has_catalog():
        return []
    if database_url():
        return load_postgres_titles()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        select
          netflix_id, tmdb_id, imdb_id, title, type, synopsis, year, runtime,
          genres, cast_names, director_names, countries, availability_regions,
          poster_url, backdrop_url, netflix_poster_url, netflix_large_image_url,
          source_url, embedding
        from titles
        """
    ).fetchall()
    conn.close()
    movies: list[Movie] = []
    for row in rows:
        genres = json.loads(row["genres"] or "[]")
        source_url = row["source_url"] or "https://www.themoviedb.org"
        platform = "Netflix" if "justwatch.com" in source_url else "TMDB"
        movies.append(
            Movie(
                id=row["netflix_id"] or row["tmdb_id"] or row["imdb_id"] or row["title"],
                title=row["title"],
                type=row["type"] or "Movie",
                description=row["synopsis"] or "",
                genres=genres,
                cast=json.loads(row["cast_names"] or "[]"),
                director=", ".join(json.loads(row["director_names"] or "[]")),
                country=json.loads(row["countries"] or "[]"),
                availability_region=json.loads(row["availability_regions"] or "[]"),
                release_year=row["year"],
                rating="",
                duration=f"{row['runtime']} min" if row["runtime"] else "",
                poster_url=row["poster_url"] or row["netflix_poster_url"],
                backdrop_url=row["backdrop_url"] or row["netflix_large_image_url"],
                platform=platform,
                source_url=source_url,
                tags=genres,
            )
        )
    return movies


def row_to_movie(row: dict) -> Movie:
    genres = parse_json_list(row.get("genres"))
    source_url = row.get("source_url") or "https://www.themoviedb.org"
    platform = "Netflix" if "justwatch.com" in source_url else "TMDB"
    runtime = row.get("runtime")
    movie_id = row.get("netflix_id") or row.get("tmdb_id") or row.get("imdb_id") or row.get("id") or row.get("title")
    return Movie(
        id=str(movie_id),
        title=row.get("title") or "Untitled",
        type=row.get("type") or "Movie",
        description=row.get("synopsis") or "",
        genres=genres,
        cast=parse_json_list(row.get("cast_names")),
        director=", ".join(parse_json_list(row.get("director_names"))),
        country=parse_json_list(row.get("countries")),
        availability_region=parse_json_list(row.get("availability_regions")),
        release_year=row.get("year"),
        rating="",
        duration=f"{runtime} min" if runtime else "",
        poster_url=row.get("poster_url") or row.get("netflix_poster_url"),
        backdrop_url=row.get("backdrop_url") or row.get("netflix_large_image_url"),
        platform=platform,
        source_url=source_url,
        tags=genres,
    )


def load_postgres_titles() -> list[Movie]:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            select
              id, netflix_id, tmdb_id, imdb_id, title, type, synopsis, year, runtime,
              genres, cast_names, director_names, countries, availability_regions,
              poster_url, backdrop_url, netflix_poster_url, netflix_large_image_url,
              source_url
            from titles
            """
        ).fetchall()
    return [row_to_movie(row) for row in rows]


def load_embedding_by_movie_id(movie_id: str) -> list[float] | None:
    if not has_catalog():
        return None
    if database_url():
        with psycopg.connect(database_url()) as conn:
            row = conn.execute(
                """
                select embedding::text
                from titles
                where netflix_id = %s or tmdb_id = %s or imdb_id = %s or id::text = %s
                limit 1
                """,
                (movie_id, movie_id, movie_id, movie_id),
            ).fetchone()
        return parse_embedding(row[0]) if row else None
    conn = sqlite3.connect(db_path())
    row = conn.execute(
        "select embedding from titles where netflix_id = ? or tmdb_id = ? or imdb_id = ? limit 1",
        (movie_id, movie_id, movie_id),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    return json.loads(row[0])


def load_embeddings_by_id() -> dict[str, list[float]]:
    if not has_catalog():
        return {}
    if database_url():
        with psycopg.connect(database_url()) as conn:
            rows = conn.execute(
                """
                select netflix_id, tmdb_id, imdb_id, id::text, embedding::text
                from titles
                where embedding is not null
                """
            ).fetchall()
        embeddings: dict[str, list[float]] = {}
        for netflix_id, tmdb_id, imdb_id, row_id, raw in rows:
            embedding = parse_embedding(raw)
            if not embedding:
                continue
            for key in (netflix_id, tmdb_id, imdb_id, row_id):
                if key:
                    embeddings[str(key)] = embedding
        return embeddings
    conn = sqlite3.connect(db_path())
    rows = conn.execute("select netflix_id, tmdb_id, imdb_id, embedding from titles where embedding is not null").fetchall()
    conn.close()
    embeddings: dict[str, list[float]] = {}
    for netflix_id, tmdb_id, imdb_id, raw in rows:
        if not raw:
            continue
        embedding = json.loads(raw)
        for key in (netflix_id, tmdb_id, imdb_id):
            if key:
                embeddings[str(key)] = embedding
    return embeddings


@lru_cache(maxsize=1)
def load_embedding_matrix() -> tuple[list[str], np.ndarray]:
    if not has_catalog():
        return [], np.empty((0, 0), dtype=np.float32)
    if database_url():
        with psycopg.connect(database_url()) as conn:
            rows = conn.execute("select coalesce(netflix_id, tmdb_id, imdb_id, id::text), embedding::text from titles where embedding is not null").fetchall()
    else:
        conn = sqlite3.connect(db_path())
        rows = conn.execute("select netflix_id, embedding from titles where embedding is not null").fetchall()
        conn.close()
    ids: list[str] = []
    vectors: list[list[float]] = []
    for movie_id, raw in rows:
        if not raw:
            continue
        vector = parse_embedding(raw) if database_url() else json.loads(raw)
        if not vector:
            continue
        ids.append(str(movie_id))
        vectors.append(vector)
    if not vectors:
        return [], np.empty((0, 0), dtype=np.float32)
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return ids, matrix / norms


def vector_scores(query_embedding: list[float] | None) -> dict[str, float]:
    if not query_embedding:
        return {}
    ids, matrix = load_embedding_matrix()
    if matrix.size == 0:
        return {}
    query = np.asarray(query_embedding, dtype=np.float32)
    norm = np.linalg.norm(query)
    if norm == 0:
        return {}
    scores = matrix @ (query / norm)
    return {movie_id: float(score) for movie_id, score in zip(ids, scores)}


def catalog_stats() -> dict | None:
    if not has_catalog():
        return None
    if database_url():
        with psycopg.connect(database_url(), row_factory=dict_row) as conn:
            row = conn.execute(
                """
                select
                  count(*) as total_titles,
                  sum(case when type = 'Movie' then 1 else 0 end) as movies_count,
                  sum(case when type = 'Show' then 1 else 0 end) as shows_count,
                  sum(case when embedding is not null then 1 else 0 end) as embedded_count,
                  max(updated_at) as last_import_time
                from titles
                """
            ).fetchone()
            region_rows = conn.execute("select availability_regions from titles").fetchall()
        regions = sorted({region for item in region_rows for region in parse_json_list(item["availability_regions"])})
        total = row["total_titles"] or 0
        embedded = row["embedded_count"] or 0
        return {
            "total_titles": total,
            "movies_count": row["movies_count"] or 0,
            "shows_count": row["shows_count"] or 0,
            "regions_available": regions,
            "last_import_time": str(row["last_import_time"] or "Postgres catalog"),
            "embedding_coverage_percentage": round((embedded / total) * 100) if total else 0,
            "search_index_status": "Ready: Postgres catalog with pgvector embeddings",
        }
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        select
          count(*) as total_titles,
          sum(case when type = 'Movie' then 1 else 0 end) as movies_count,
          sum(case when type = 'Show' then 1 else 0 end) as shows_count,
          sum(case when embedding is not null then 1 else 0 end) as embedded_count,
          max(updated_at) as last_import_time
        from titles
        """
    ).fetchone()
    region_rows = conn.execute("select availability_regions from titles").fetchall()
    conn.close()
    regions = sorted({region for item in region_rows for region in json.loads(item["availability_regions"] or "[]")})
    total = row["total_titles"] or 0
    embedded = row["embedded_count"] or 0
    return {
        "total_titles": total,
        "movies_count": row["movies_count"] or 0,
        "shows_count": row["shows_count"] or 0,
        "regions_available": regions,
        "last_import_time": row["last_import_time"] or "Local vector catalog",
        "embedding_coverage_percentage": round((embedded / total) * 100) if total else 0,
        "search_index_status": "Ready: SQLite vector catalog with OpenAI embeddings",
    }

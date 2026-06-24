from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import SearchRequest
from .search import rank_movies
from .seed import SEED_MOVIES
from .vector_store import catalog_stats as vector_catalog_stats

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Seek API", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "seek-api"}


@app.post("/search")
def search(request: SearchRequest):
    return rank_movies(request.query, request.selected_profile)


@app.get("/movies/{movie_id}")
def get_movie(movie_id: str):
    for movie in SEED_MOVIES:
        if movie.id == movie_id:
            return movie
    raise HTTPException(status_code=404, detail="Movie not found")


@app.get("/movies/{movie_id}/similar")
def similar(movie_id: str):
    movie = next((item for item in SEED_MOVIES if item.id == movie_id), None)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    query = " ".join(movie.genres + movie.tags[:4])
    return rank_movies(query, "Neutral").results[:6]


@app.post("/import-csv")
async def import_csv(file: UploadFile = File(...)):
    content = await file.read()
    return {
        "source_name": file.filename,
        "total_bytes": len(content),
        "message": "Use scripts/import_catalog.py for durable Postgres ingestion with embeddings.",
    }


@app.get("/catalog/stats")
def catalog_stats():
    vector_stats = vector_catalog_stats()
    if vector_stats:
        return vector_stats
    regions = sorted({region for movie in SEED_MOVIES for region in movie.availability_region})
    return {
        "total_titles": len(SEED_MOVIES),
        "movies_count": len([movie for movie in SEED_MOVIES if movie.type == "Movie"]),
        "shows_count": len([movie for movie in SEED_MOVIES if movie.type == "Show"]),
        "regions_available": regions,
        "last_import_time": "Demo seed loaded at startup",
        "embedding_coverage_percentage": 100,
        "search_index_status": "Ready: TF-IDF fallback, pgvector schema supported",
    }


@app.get("/debug/searches")
def debug_searches():
    return {
        "recent_searches": ["dark funny revenge movie", "comfort movie for a rainy night"],
        "low_confidence_searches": ["ambiguous actor memory", "unknown regional title"],
    }

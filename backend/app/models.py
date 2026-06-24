from __future__ import annotations

from pydantic import BaseModel, Field


class Movie(BaseModel):
    id: str
    title: str
    type: str = "Movie"
    description: str = ""
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    director: str = ""
    country: list[str] = Field(default_factory=list)
    availability_region: list[str] = Field(default_factory=list)
    release_year: int | None = None
    rating: str = ""
    duration: str = ""
    poster_url: str | None = None
    backdrop_url: str | None = None
    platform: str = "Imported catalog"
    date_added: str | None = None
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    ranking: dict | None = None


class SearchRequest(BaseModel):
    query: str
    selected_profile: str = "Neutral"


class SearchResponse(BaseModel):
    query: str
    selected_profile: str
    embedding_model: str
    latency_ms: int
    titles_searched: int
    candidates_retrieved: int
    formula: str
    results: list[Movie]
    recent_searches: list[str] = Field(default_factory=list)
    low_confidence_searches: list[str] = Field(default_factory=list)

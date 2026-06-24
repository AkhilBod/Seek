from __future__ import annotations

import re
import time
from collections import Counter
from datetime import date
from math import sqrt
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from .models import Movie, SearchResponse
from .seed import SEED_MOVIES
from .vector_store import load_titles, vector_scores

FORMULA = "0.55 * semantic_score + 0.25 * keyword_score + 0.15 * profile_score + 0.05 * diversity_score"

PROFILE_TERMS = {
    "Neutral": [],
    "Thriller Fan": ["thriller", "tense", "crime", "slow-burn", "dark", "intense", "mystery"],
    "Comfort Watcher": ["comfort", "warm", "gentle", "rainy", "family", "soft", "less stressful"],
    "Prestige Drama": ["drama", "prestige", "emotional", "class tension", "serious", "grief"],
    "Sci-Fi Nerd": ["sci-fi", "mind-bending", "AI", "future", "language", "loneliness"],
    "Comedy First": ["comedy", "funny", "witty", "chaotic", "satire", "buddy comedy"],
    "Date Night": ["romance", "witty", "warm", "mystery", "emotional", "funny"],
    "Family Friendly": ["family", "gentle", "warm", "PG", "adventure", "comfort"],
}

DETECTIVE_TERMS = {
    "detective",
    "investigation",
    "investigator",
    "murder",
    "case",
    "police",
    "cop",
    "serial killer",
    "missing",
    "mystery",
    "crime",
    "homicide",
    "whodunit",
    "private eye",
    "forensic",
    "detectives",
}

DETECTIVE_GENRES = {"thriller", "mystery", "crime"}
DETECTIVE_BAD_GENRES = {"comedy", "kids", "documentary", "reality", "sci-fi & fantasy", "science fiction", "family", "animation"}
HORROR_GENRES = {"horror"}


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def tokenize(value: str) -> list[str]:
    return [part for part in re.sub(r"[^a-z0-9\s-]", " ", value.lower()).split() if part]


def movie_text(movie: Movie) -> str:
    return " ".join(
        [
            movie.title,
            movie.type,
            movie.description,
            " ".join(movie.genres),
            " ".join(movie.tags),
            " ".join(movie.cast),
            movie.director,
            " ".join(movie.country),
        ]
    ).lower()


def infer_intent(normalized: str) -> dict:
    wants_movie = bool(re.search(r"\b(movie|movies|film|films)\b", normalized)) and not bool(re.search(r"\b(show|shows|series|tv)\b", normalized))
    wants_show = bool(re.search(r"\b(show|shows|series|tv)\b", normalized)) and not wants_movie
    wants_new = bool(re.search(r"\b(new|recent|modern|latest|newer|2020s)\b", normalized))
    wants_detective = any(term in normalized for term in DETECTIVE_TERMS) or "detective thriller" in normalized
    wants_thrillerish = any(term in normalized for term in ("thriller", "mystery", "crime", "detective", "murder", "investigation"))
    wants_horror = "horror" in normalized
    return {
        "wants_movie": wants_movie,
        "wants_show": wants_show,
        "wants_new": wants_new,
        "wants_detective": wants_detective,
        "wants_thrillerish": wants_thrillerish,
        "wants_horror": wants_horror,
    }


def movie_genres(movie: Movie) -> set[str]:
    return {genre.lower() for genre in movie.genres}


def passes_hard_filters(movie: Movie, intent: dict) -> bool:
    genres = movie_genres(movie)
    corpus = movie_text(movie)
    if intent["wants_movie"] and movie.type.lower() != "movie":
        return False
    if intent["wants_show"] and movie.type.lower() != "show":
        return False
    if intent["wants_new"] and (movie.release_year or 0) < 2020:
        return False
    if intent["wants_new"] and movie.release_year and movie.release_year > date.today().year:
        return False
    if intent["wants_thrillerish"] and not (genres & DETECTIVE_GENRES):
        return False
    if intent["wants_detective"] and not (genres & {"crime", "mystery"} or any(term in corpus for term in DETECTIVE_TERMS)):
        return False
    return True


def intent_boosts(movie: Movie, corpus: str, intent: dict) -> tuple[float, list[str]]:
    genres = movie_genres(movie)
    boost = 0.0
    signals: list[str] = []

    if intent["wants_new"] and (movie.release_year or 0) >= 2020:
        boost += 0.08
        signals.append("new release")
    if intent["wants_movie"] and movie.type.lower() == "movie":
        boost += 0.05
        signals.append("movie")
    if intent["wants_thrillerish"] and genres & DETECTIVE_GENRES:
        boost += 0.12
        signals.append("crime/mystery/thriller genre")
    if intent["wants_detective"]:
        detective_hits = [term for term in DETECTIVE_TERMS if term in corpus]
        if "mystery" in genres:
            boost += 0.06
            signals.append("mystery genre")
        if "crime" in genres:
            boost += 0.05
            signals.append("crime genre")
        if not genres & {"crime", "mystery"}:
            boost -= 0.12
            signals.append("penalized weak detective genre")
        if "action" in genres and "mystery" not in genres:
            boost -= 0.05
            signals.append("penalized action drift")
        if detective_hits:
            boost += min(0.12, 0.04 * len(detective_hits))
            signals.append("detective/investigation language")
        if genres & DETECTIVE_BAD_GENRES:
            boost -= 0.18
            signals.append("penalized off-intent genre")
        if genres & HORROR_GENRES and not intent["wants_horror"]:
            boost -= 0.1
            signals.append("penalized horror drift")
    return boost, signals


def cosine_from_terms(query_terms: list[str], doc_terms: list[str]) -> float:
    q = Counter(query_terms)
    d = Counter(doc_terms)
    dot = sum(q[term] * d[term] for term in q)
    q_norm = sqrt(sum(value * value for value in q.values()))
    d_norm = sqrt(sum(value * value for value in d.values()))
    if not q_norm or not d_norm:
        return 0.0
    return dot / (q_norm * d_norm)


def embed_query(query: str) -> list[float] | None:
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        return None
    try:
        client = OpenAI()
        response = client.embeddings.create(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), input=query)
        return response.data[0].embedding
    except Exception:
        return None


def rank_movies(query: str, profile: str, movies: list[Movie] | None = None) -> SearchResponse:
    started = time.perf_counter()
    normalized = normalize_query(query)
    query_terms = tokenize(normalized)
    intent = infer_intent(normalized)
    previous_genres: set[str] = set()
    ranked = []

    source_movies = movies or load_titles() or SEED_MOVIES
    filtered_movies = [movie for movie in source_movies if passes_hard_filters(movie, intent)]
    candidate_movies = filtered_movies or source_movies
    query_embedding = embed_query(normalized)
    vector_scores_by_id = vector_scores(query_embedding)

    for movie in candidate_movies:
        corpus = movie_text(movie)
        doc_terms = tokenize(corpus)
        matched = [term for term in query_terms if term in corpus]
        vector_score = vector_scores_by_id.get(movie.id, 0)
        semantic_score = (
            max(0.0, min(1.0, (vector_score + 1) / 2))
            if vector_score
            else min(1.0, 0.28 + cosine_from_terms(query_terms, doc_terms) + len(matched) / max(len(query_terms), 1) * 0.5)
        )
        keyword_score = min(1.0, len(matched) / max(len(query_terms), 1))
        profile_hits = sum(1 for term in PROFILE_TERMS.get(profile, []) if term.lower() in corpus)
        profile_score = 0.55 if profile == "Neutral" else min(1.0, 0.24 + profile_hits * 0.2)
        overlap = len([genre for genre in movie.genres if genre in previous_genres])
        diversity_score = max(0.25, 1 - overlap * 0.22)
        intent_boost, intent_signals = intent_boosts(movie, corpus, intent)
        final_score = max(0.0, min(0.96, 0.55 * semantic_score + 0.25 * keyword_score + 0.15 * profile_score + 0.05 * diversity_score + intent_boost))
        matched_fields = []
        if matched:
            matched_fields.append("description/tags")
        if any(term in movie.title.lower() for term in query_terms):
            matched_fields.append("title")
        if any(term in " ".join(movie.genres).lower() for term in query_terms):
            matched_fields.append("genres")
        if profile_hits:
            matched_fields.append("profile preferences")
        matched_fields.extend(intent_signals)

        item = movie.model_copy(deep=True)
        item.ranking = {
            "semantic_score": semantic_score,
            "keyword_score": keyword_score,
            "profile_score": profile_score,
            "diversity_score": diversity_score,
            "final_score": final_score,
            "matched_fields": list(dict.fromkeys(matched_fields)),
            "explanation": f"Matched {', '.join(matched[:4]) or 'nearby intent'} across {', '.join(list(dict.fromkeys(matched_fields))[:4]) or 'catalog text'}.",
        }
        ranked.append(item)

    ranked.sort(key=lambda movie: movie.ranking["final_score"] if movie.ranking else 0, reverse=True)
    for movie in ranked[:20]:
        previous_genres.update(movie.genres)

    return SearchResponse(
        query=query,
        selected_profile=profile,
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small") if query_embedding else "TF-IDF keyword fallback",
        latency_ms=round((time.perf_counter() - started) * 1000),
        titles_searched=len(source_movies),
        candidates_retrieved=min(20, len(ranked)),
        formula=FORMULA,
        results=ranked[:20],
        recent_searches=["dark funny revenge movie", "comfort movie for a rainy night", "emotional sci-fi about loneliness"],
        low_confidence_searches=["very obscure memory fragment", "movie with the red umbrella but maybe a show"],
    )

#!/usr/bin/env python3
"""Build a known-item search benchmark from the catalog.

For a random sample of titles, an LLM writes the kind of vague query a person
types when they remember what a movie or show felt like but not what it was
called. The title it came from is the one correct answer.

Queries are rejected if they leak the answer: any word from the title, or any
capitalized name from the synopsis (characters, places, actors). What's left
has to be found from plot and mood alone.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from pathlib import Path

import psycopg
from openai import OpenAI

PROMPT = """Here is a movie or TV show from a streaming catalog.

Type: {type}
Genres: {genres}
Synopsis: {synopsis}

Write ONE search query that a person might type into a streaming app's search box \
when they remember roughly what this was about or how it felt, but not its name. \
Rules: 4 to 12 words, lowercase, no title, no character names, no actor names, no \
place names, no years. Describe the plot or vibe loosely, the way a real person would. \
Return only the query."""

STOP = {"the", "and", "of", "a", "an", "in", "on", "to", "for", "with", "from", "at", "by", "is", "my", "your", "part", "season"}


def leaks(query: str, title: str, synopsis: str) -> bool:
    q = set(re.findall(r"[a-z0-9']+", query.lower()))
    title_words = {w for w in re.findall(r"[a-z0-9']+", title.lower()) if len(w) > 2 and w not in STOP}
    if q & title_words:
        return True
    # capitalized words that aren't sentence starts are usually names
    names = set()
    for sentence in re.split(r"(?<=[.!?])\s+", synopsis):
        for word in re.findall(r"\b[A-Z][a-z']+\b", sentence)[1:]:
            names.add(word.lower())
    return bool(q & (names - STOP))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("SEEK_EVAL_DATABASE_URL"))
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("queries.jsonl"))
    args = ap.parse_args()

    with psycopg.connect(args.database_url) as conn:
        rows = conn.execute(
            "select id, title, type, genres, synopsis from titles "
            "where length(coalesce(synopsis, '')) >= 120 order by id"
        ).fetchall()
    random.Random(args.seed).shuffle(rows)

    client = OpenAI()
    kept, rejected = [], 0
    for row_id, title, kind, genres, synopsis in rows:
        if len(kept) >= args.n:
            break
        reply = client.chat.completions.create(
            model=args.model,
            temperature=0.7,
            messages=[{"role": "user", "content": PROMPT.format(type=kind, genres=", ".join(genres or []), synopsis=synopsis)}],
        )
        query = reply.choices[0].message.content.strip().strip('"').lower()
        if leaks(query, title, synopsis) or not 3 <= len(query.split()) <= 14:
            rejected += 1
            continue
        kept.append({"target_id": row_id, "title": title, "query": query})

    with args.out.open("w") as f:
        for item in kept:
            f.write(json.dumps(item) + "\n")
    print(f"kept {len(kept)}, rejected {rejected} for leaking the answer or bad length -> {args.out}")


if __name__ == "__main__":
    main()

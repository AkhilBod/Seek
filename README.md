# Seek

Seek is a search-first movie discovery engine for natural-language prompts like “dark funny revenge movie,” “comfort movie for a rainy night,” or “something like The Bear but less stressful.”

It is intentionally not a streaming clone. The product focuses on one polished search experience, explainable ranking, and catalog ingestion that can scale to a large streaming dataset when one is provided.

## Why It Matters

Movie discovery often fails when people know the mood, plot texture, or emotional shape they want but not the title. Seek treats discovery as retrieval: hybrid semantic and keyword search, profile-aware reranking, and transparent explanations.

Resume bullet:

> Built Seek, a search-first movie discovery engine using hybrid vector/keyword retrieval, personalized reranking, and explainable ranking across a large streaming catalog, enabling natural-language discovery by mood, theme, plot, and vague user intent.

## Architecture

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- Database-ready: PostgreSQL with pgvector
- Embeddings: OpenAI embeddings when `OPENAI_API_KEY` is present; local/TF-IDF fallback otherwise
- Deployment targets: Vercel frontend, Render/Fly.io backend, Supabase/Neon Postgres

## Search Pipeline

1. Normalize the user query.
2. Convert query into an embedding when configured.
3. Retrieve pgvector semantic candidates from the catalog.
4. Run keyword search across title, description, genres, cast, director, country, region, and type.
5. Merge semantic and keyword candidates.
6. Apply selected demo profile preferences.
7. Return top results with deterministic explanations.

Scoring:

```txt
final_score =
0.65 * semantic_score +
0.25 * keyword_score +
0.10 * profile_score
```

## Local Setup

```bash
npm run install:all
npm run dev
```

In a second terminal:

```bash
npm run backend
```

Frontend: `http://localhost:3000`
Backend: `http://localhost:8000`

The frontend is fully demoable without the backend. If `NEXT_PUBLIC_API_BASE_URL` is not set, it uses the local seed catalog and browser-side hybrid fallback.

## Environment Variables

Frontend:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Backend:

```bash
DATABASE_URL=postgresql://user:password@host:5432/seek
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
UNOGS_API_KEY=...
UNOGS_API_HOST=unogs-unogs-v1.p.rapidapi.com
UNOGS_API_BASE_URL=https://unogs-unogs-v1.p.rapidapi.com
TMDB_API_KEY=...
TMDB_READ_ACCESS_TOKEN=...
TMDB_WATCH_REGIONS=US
OMDB_API_KEY=...
```

## Catalog Import

Initialize Postgres:

```bash
psql "$DATABASE_URL" -f backend/schema.sql
```

Import CSV or JSON:

```bash
python3 scripts/import_catalog.py ./catalog.csv --database-url "$DATABASE_URL"
```

Supported fields:

```txt
netflix_id,tmdb_id,imdb_id,title,type,synopsis,year,runtime,genres,
cast_names,director_names,countries,availability_regions,poster_url,
backdrop_url,netflix_poster_url,netflix_large_image_url,date_added,
expire_date,source_url
```

The importer cleans missing fields, normalizes genres/cast/director metadata, creates embeddings in batches when possible, skips duplicates, and records import counts, skipped rows, and embedding failures.

## Netflix Catalog + Artwork Pipeline

Netflix does not provide a normal public catalog API. For a current Netflix catalog, Seek uses this import path:

1. Pull country catalogs from uNoGS with pagination.
2. Dedupe titles by `netflix_id`.
3. Optionally fetch uNoGS title details.
4. Enrich artwork from TMDB using IMDb ID first, then title/year search.
5. Build image URLs with TMDB sizes: `w500` posters and `w1280` backdrops.
6. Generate embeddings when `OPENAI_API_KEY` is present.
7. Upsert into Postgres `titles`.

```bash
python3 scripts/import_unogs_netflix.py \
  --countries US,CA,GB \
  --details \
  --database-url "$DATABASE_URL"
```

Dry run without writing:

```bash
python3 scripts/import_unogs_netflix.py --countries US --dry-run
```

Image dimensions in the UI:

- Poster cards use `aspect-[2/3]`.
- Wide result thumbnails use `aspect-video`.
- Hero and modal backdrops use 16:9 artwork.

If uNoGS is not available, use TMDB's Netflix watch-provider catalog as the practical demo source. It retrieves Netflix-available movies and shows by region, enriches details/credits/external IDs, builds clean TMDB poster/backdrop URLs, generates OpenAI embeddings, and stores a local SQLite vector catalog at `backend/data/seek_catalog.sqlite`.

```bash
export TMDB_API_KEY="..."
export TMDB_READ_ACCESS_TOKEN="..."
export OPENAI_API_KEY="..."
export OPENAI_EMBEDDING_MODEL="text-embedding-3-small"

python3 scripts/import_tmdb_netflix.py --regions US --pages 25
```

`--pages 25` imports up to about 1,000 titles before dedupe because TMDB returns 20 results per page for movies and shows. Increase pages or add regions for a broader catalog:

```bash
python3 scripts/import_tmdb_netflix.py --regions US,CA,GB --pages 50
```

Enrich the local catalog with OMDb metadata:

```bash
python3 scripts/enrich_omdb.py --limit 900
```

OMDb enrichment fills IMDb IDs, runtime, cast, director, rating, IMDb score/votes, awards, full plot text, and poster fallbacks where the API has data.

If OMDb is unavailable or rate-limited, enrich from TMDB details instead:

```bash
python3 scripts/enrich_tmdb_details.py --limit 2000
```

TMDB detail enrichment fills runtime, cast, director/creator names, countries, plot text, and IMDb IDs for existing catalog rows.

## Demo Flow

1. Open the landing page.
2. Click “dark funny revenge movie.”
3. Review ranked results and “Why this matched.”
4. Open a result modal.
5. Inspect the ranking breakdown.
6. Change the profile to rerank the same query.
7. Open `/debug` to inspect retrieval signals.
8. Open `/catalog` to review index stats.

## Deployment

Production uses hosted Postgres/pgvector when `DATABASE_URL` is set. Local development can still use the ignored SQLite catalog at `backend/data/seek_catalog.sqlite`.

### Database

Create a Postgres database through Neon or Supabase, enable pgvector, then apply the schema:

```bash
psql "$DATABASE_URL" -f backend/schema.sql
```

Seed the hosted database from the local SQLite catalog:

```bash
python3 scripts/migrate_sqlite_to_postgres.py --database-url "$DATABASE_URL"
```

Or import a CSV/JSON catalog directly:

```bash
python3 scripts/import_catalog.py ./catalog.csv --database-url "$DATABASE_URL"
```

### Frontend on Vercel

Set the Vercel project root to `frontend`.

```bash
npm install
npm run build
```

Add:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-seek-api.example.com
```

### Backend on Render

This repo includes `render.yaml` and `backend/Dockerfile`. Create a Render Blueprint from the repo, then set the secret environment variables:

```bash
DATABASE_URL=postgresql://...
OPENAI_API_KEY=...
TMDB_API_KEY=...
TMDB_READ_ACCESS_TOKEN=...
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

Render start command inside the container:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

After the backend deploys, set the Vercel frontend env var to the Render URL:

```bash
NEXT_PUBLIC_API_BASE_URL=https://seek-api.onrender.com
```

## Screenshots

Add screenshots of:

- Landing page search hero
- Search results with explanations
- Detail modal with ranking breakdown
- Debug page
- Catalog stats page

## Example Queries

- dark funny revenge movie
- something like The Bear but less stressful
- comfort movie for a rainy night
- mind-bending sci-fi but not Marvel
- crime movie with smart dialogue
- movie to watch after a breakup but not too depressing
- slow-burn thriller with rich people drama
- intense movie but not horror
- funny movie with chaotic friends
- emotional sci-fi about loneliness

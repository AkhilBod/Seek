create extension if not exists vector;

create table if not exists titles (
  id bigserial primary key,
  netflix_id text unique,
  tmdb_id text,
  imdb_id text,
  title text not null,
  type text,
  synopsis text,
  year integer,
  runtime integer,
  genres text[] default '{}',
  cast_names text[] default '{}',
  director_names text[] default '{}',
  countries text[] default '{}',
  availability_regions text[] default '{}',
  poster_url text,
  backdrop_url text,
  netflix_poster_url text,
  netflix_large_image_url text,
  date_added date,
  expire_date date,
  source_url text,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists titles_genres_idx on titles using gin (genres);
create index if not exists titles_regions_idx on titles using gin (availability_regions);
create index if not exists titles_imdb_idx on titles (imdb_id);
create index if not exists titles_tmdb_idx on titles (tmdb_id);

create or replace view movies as
select
  coalesce(netflix_id, id::text) as id,
  title,
  coalesce(type, 'Movie') as type,
  synopsis as description,
  genres,
  cast_names as cast_members,
  array_to_string(director_names, ', ') as director,
  countries as country,
  availability_regions as availability_region,
  year as release_year,
  null::text as rating,
  case when runtime is null then null else runtime::text || ' min' end as duration,
  poster_url,
  backdrop_url,
  'Netflix'::text as platform,
  date_added,
  source_url,
  embedding,
  created_at,
  updated_at
from titles;

create table if not exists search_logs (
  id bigserial primary key,
  query text not null,
  selected_profile text not null,
  result_count integer not null,
  latency_ms integer not null,
  created_at timestamptz not null default now()
);

create table if not exists import_logs (
  id bigserial primary key,
  source_name text not null,
  total_rows integer not null,
  imported_rows integer not null,
  skipped_rows integer not null,
  embedding_failures integer not null,
  created_at timestamptz not null default now()
);

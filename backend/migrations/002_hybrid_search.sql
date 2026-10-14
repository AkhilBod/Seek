-- Real hybrid retrieval: an ANN index for embeddings and a full-text index for
-- keywords. Before this, candidates came from ILIKE over the whole table and
-- cosine similarity was computed in Python on whatever 600 rows that returned.

create or replace function seek_search_text(title text, synopsis text, genres text[])
returns tsvector
language sql
immutable
as $$
  select setweight(to_tsvector('english', coalesce(title, '')), 'A')
      || setweight(to_tsvector('english', coalesce(array_to_string(genres, ' '), '')), 'B')
      || setweight(to_tsvector('english', coalesce(synopsis, '')), 'C')
$$;

alter table titles
  add column if not exists search_tsv tsvector
  generated always as (seek_search_text(title, synopsis, genres)) stored;

create index if not exists titles_search_tsv_idx on titles using gin (search_tsv);
create index if not exists titles_embedding_hnsw_idx on titles using hnsw (embedding vector_cosine_ops);

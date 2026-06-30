import { CatalogStats, Movie, Profile, Ranking, SearchResponse } from "./types";
import { seedMovies } from "./seed";

export const profiles: Profile[] = [
  "Neutral",
  "Thriller Fan",
  "Comfort Watcher",
  "Prestige Drama",
  "Sci-Fi Nerd",
  "Comedy First",
  "Date Night",
  "Family Friendly"
];

const profileTerms: Record<Profile, string[]> = {
  Neutral: [],
  "Thriller Fan": ["thriller", "tense", "crime", "slow-burn", "dark", "intense", "mystery"],
  "Comfort Watcher": ["comfort", "warm", "gentle", "rainy", "family", "soft", "less stressful"],
  "Prestige Drama": ["drama", "prestige", "emotional", "class tension", "serious", "grief"],
  "Sci-Fi Nerd": ["sci-fi", "mind-bending", "AI", "future", "language", "loneliness"],
  "Comedy First": ["comedy", "funny", "witty", "chaotic", "satire", "buddy comedy"],
  "Date Night": ["romance", "witty", "warm", "mystery", "emotional", "funny"],
  "Family Friendly": ["family", "gentle", "warm", "PG", "adventure", "comfort"]
};

export const examples = [
  "dark funny revenge movie",
  "comfort movie for a rainy night",
  "emotional sci-fi about loneliness",
  "crime thriller with smart dialogue",
  "something intense but not horror",
  "something like The Bear but less stressful"
];

const tokenize = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

const textFor = (movie: Movie) =>
  [
    movie.title,
    movie.type,
    movie.description,
    movie.genres.join(" "),
    movie.tags.join(" "),
    movie.cast.join(" "),
    movie.director,
    movie.country.join(" ")
  ].join(" ");

const scoreMovie = (movie: Movie, query: string, profile: Profile): Ranking => {
  const queryTerms = tokenize(query);
  const corpus = textFor(movie).toLowerCase();
  const title = movie.title.toLowerCase();
  const genres = movie.genres.join(" ").toLowerCase();
  const tags = movie.tags.join(" ").toLowerCase();
  const matched = queryTerms.filter((term) => corpus.includes(term));
  const phraseBoost = corpus.includes(query.toLowerCase()) ? 0.18 : 0;
  const semanticHits = queryTerms.filter((term) => tags.includes(term) || movie.description.toLowerCase().includes(term));
  const semantic_score = Math.min(1, 0.24 + semanticHits.length / Math.max(queryTerms.length, 1) + phraseBoost);
  const keyword_score = Math.min(
    1,
    matched.length / Math.max(queryTerms.length, 1) +
      (queryTerms.some((term) => title.includes(term)) ? 0.15 : 0) +
      (queryTerms.some((term) => genres.includes(term)) ? 0.1 : 0)
  );
  const profileHits = profileTerms[profile].filter((term) => corpus.includes(term.toLowerCase())).length;
  const profile_score = profile === "Neutral" ? 0.55 : Math.min(1, 0.24 + profileHits * 0.2);
  const final_score = 0.65 * semantic_score + 0.25 * keyword_score + 0.1 * profile_score;
  const matched_fields = [
    ...(matched.length ? ["description/tags"] : []),
    ...(queryTerms.some((term) => title.includes(term)) ? ["title"] : []),
    ...(queryTerms.some((term) => genres.includes(term)) ? ["genres"] : []),
    ...(profileHits ? ["profile preferences"] : [])
  ];

  return {
    semantic_score,
    keyword_score,
    profile_score,
    final_score,
    matched_fields: [...new Set(matched_fields)],
    explanation:
      matched.length > 0
        ? `Matched ${matched.slice(0, 4).join(", ")} across ${matched_fields.slice(0, 3).join(", ") || "catalog text"}.`
        : `Ranked through genre proximity, description similarity, and ${profile} profile fit.`
  };
};

export async function searchCatalog(query: string, profile: Profile): Promise<SearchResponse> {
  const started = performance.now();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (apiBase) {
    try {
      const res = await fetch(`${apiBase}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, selected_profile: profile }),
        cache: "no-store"
      });
      if (res.ok) return res.json();
    } catch {
      // Keep the demo alive if the API is not running.
    }
  }

  const results = seedMovies
    .map((movie) => ({ ...movie, ranking: scoreMovie(movie, query, profile) }))
    .sort((a, b) => (b.ranking?.final_score ?? 0) - (a.ranking?.final_score ?? 0))
    .slice(0, 20);

  return {
    query,
    selected_profile: profile,
    embedding_model: "browser TF-IDF demo fallback",
    latency_ms: Math.round(performance.now() - started),
    titles_searched: seedMovies.length,
    candidates_retrieved: results.length,
    formula: "0.65 * semantic + 0.25 * keyword + 0.10 * profile",
    results,
    recent_searches: examples.slice(0, 4),
    low_confidence_searches: ["obscure director with no genre hints", "that one movie with the blue room"]
  };
}

export async function getCatalogStats(): Promise<CatalogStats> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (apiBase) {
    try {
      const res = await fetch(`${apiBase}/catalog/stats`, { cache: "no-store" });
      if (res.ok) return res.json();
    } catch {}
  }

  const regions = [...new Set(seedMovies.flatMap((movie) => movie.availability_region))].sort();
  return {
    total_titles: seedMovies.length,
    movies_count: seedMovies.filter((movie) => movie.type === "Movie").length,
    shows_count: seedMovies.filter((movie) => movie.type === "Show").length,
    regions_available: regions,
    last_import_time: "Demo seed loaded locally",
    embedding_coverage_percentage: 100,
    search_index_status: "Ready: local hybrid fallback"
  };
}

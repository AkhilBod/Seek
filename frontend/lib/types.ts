export type Profile =
  | "Neutral"
  | "Thriller Fan"
  | "Comfort Watcher"
  | "Prestige Drama"
  | "Sci-Fi Nerd"
  | "Comedy First"
  | "Date Night"
  | "Family Friendly";

export type Ranking = {
  semantic_score: number;
  keyword_score: number;
  profile_score: number;
  final_score: number;
  matched_fields: string[];
  explanation: string;
};

export type Movie = {
  id: string;
  title: string;
  type: "Movie" | "Show";
  description: string;
  genres: string[];
  cast: string[];
  director: string;
  country: string[];
  availability_region: string[];
  release_year: number;
  rating: string;
  duration: string;
  poster_url?: string;
  backdrop_url?: string;
  platform: string;
  date_added?: string;
  source_url?: string;
  tags: string[];
  runtime?: string;
  ranking?: Ranking;
};

export type SearchResponse = {
  query: string;
  selected_profile: Profile;
  embedding_model: string;
  latency_ms: number;
  titles_searched: number;
  candidates_retrieved: number;
  formula: string;
  results: Movie[];
  recent_searches?: string[];
  low_confidence_searches?: string[];
};

export type CatalogStats = {
  total_titles: number;
  movies_count: number;
  shows_count: number;
  regions_available: string[];
  last_import_time: string;
  embedding_coverage_percentage: number;
  search_index_status: string;
};

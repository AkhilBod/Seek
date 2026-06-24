"use client";

import { Suspense, useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Nav } from "@/components/Nav";
import { SearchBar } from "@/components/SearchBar";
import { ResultsGrid } from "@/components/ResultsGrid";
import { ResultModal } from "@/components/ResultModal";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { searchCatalog } from "@/lib/search";
import { Movie, Profile, SearchResponse } from "@/lib/types";

function SearchView() {
  const params = useSearchParams();
  const router = useRouter();
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [isPending, startTransition] = useTransition();
  const query = params.get("q") || "dark funny revenge movie";
  const profile = (params.get("profile") || "Neutral") as Profile;

  useEffect(() => {
    let active = true;
    startTransition(async () => {
      const next = await searchCatalog(query, profile);
      if (active) setResponse(next);
    });
    return () => {
      active = false;
    };
  }, [query, profile]);

  const updateSearch = (nextQuery: string, nextProfile: Profile) => {
    router.push(`/search?${new URLSearchParams({ q: nextQuery, profile: nextProfile }).toString()}`);
  };

  return (
    <main className="search-bg min-h-screen">
      <Nav />
      <div className="w-full px-4 pb-14 pt-16 md:px-10">
        <div className="sticky top-16 z-30 -mx-4 mb-7 border-b border-white/[0.08] bg-black/[0.92] px-4 py-3 backdrop-blur md:-mx-10 md:px-10">
          <SearchBar
            initialQuery={query}
            profile={profile}
            onSearch={updateSearch}
            onProfileChange={(nextProfile) => updateSearch(query, nextProfile)}
          />
        </div>
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <p className="text-lg font-semibold text-white md:text-2xl">“{query}”</p>
          {response && (
            <p className="text-sm text-white/48">
              {response.results.length} results • {response.latency_ms}ms • {response.embedding_model}
            </p>
          )}
        </div>
        {isPending || !response ? (
          <LoadingSkeleton />
        ) : (
          <ResultsGrid results={response.results} onOpen={setSelectedMovie} />
        )}
      </div>
      <ResultModal movie={selectedMovie} onClose={() => setSelectedMovie(null)} />
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <SearchView />
    </Suspense>
  );
}

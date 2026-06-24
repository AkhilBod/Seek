"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/Nav";
import { SearchBar } from "@/components/SearchBar";
import { SearchDebugger } from "@/components/SearchDebugger";
import { searchCatalog } from "@/lib/search";
import { Profile, SearchResponse } from "@/lib/types";

export default function DebugPage() {
  const [query, setQuery] = useState("dark funny revenge movie");
  const [profile, setProfile] = useState<Profile>("Thriller Fan");
  const [response, setResponse] = useState<SearchResponse | null>(null);

  useEffect(() => {
    searchCatalog(query, profile).then(setResponse);
  }, [query, profile]);

  return (
    <main className="cinema-bg min-h-screen">
      <Nav />
      <section className="mx-auto max-w-7xl px-5 pb-16 pt-32">
        <p className="text-sm text-ember">Debug</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Search ranking debugger</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-white/58">
          Inspect retrieval, reranking, latency, matched fields, and confidence signals for a natural-language query.
        </p>
        <div className="mt-8">
          <SearchBar
            initialQuery={query}
            profile={profile}
            onSearch={(nextQuery, nextProfile) => {
              setQuery(nextQuery);
              setProfile(nextProfile);
            }}
            onProfileChange={setProfile}
          />
        </div>
        <div className="mt-8">
          <SearchDebugger response={response} />
        </div>
        {response && (
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="glass rounded-lg p-5">
              <h2 className="font-semibold text-white">Recent searches</h2>
              <p className="mt-3 text-sm leading-6 text-white/58">{response.recent_searches?.join(" • ")}</p>
            </div>
            <div className="glass rounded-lg p-5">
              <h2 className="font-semibold text-white">Low-confidence searches</h2>
              <p className="mt-3 text-sm leading-6 text-white/58">{response.low_confidence_searches?.join(" • ")}</p>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

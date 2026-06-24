"use client";

import { Movie } from "@/lib/types";
import { ResultCard } from "./ResultCard";
import { EmptyState } from "./EmptyState";

export function ResultsGrid({ results, onOpen }: { results: Movie[]; onOpen: (movie: Movie) => void }) {
  if (!results.length) return <EmptyState />;

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-7 lg:grid-cols-3 xl:grid-cols-4 xl:gap-x-5 xl:gap-y-8">
      {results.map((movie) => (
        <ResultCard key={movie.id} movie={movie} onOpen={onOpen} />
      ))}
    </div>
  );
}

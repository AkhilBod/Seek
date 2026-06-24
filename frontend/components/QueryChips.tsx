"use client";

import { examples } from "@/lib/search";

export function QueryChips({ onSelect }: { onSelect: (query: string) => void }) {
  return (
    <div className="mx-auto mt-7 flex max-w-4xl flex-wrap justify-center gap-3">
      {examples.slice(0, 6).map((query) => (
        <button
          key={query}
          onClick={() => onSelect(query)}
          className="rounded-full border border-white/10 bg-white/[0.055] px-4 py-2 text-sm text-white/68 transition hover:border-ember/50 hover:text-white"
        >
          {query}
        </button>
      ))}
    </div>
  );
}

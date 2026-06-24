"use client";

import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useRef, useState } from "react";
import { Profile } from "@/lib/types";

type Props = {
  initialQuery?: string;
  profile: Profile;
  large?: boolean;
  onSearch: (query: string, profile: Profile) => void;
  onProfileChange?: (profile: Profile) => void;
};

export function SearchBar({ initialQuery = "", profile, large = false, onSearch, onProfileChange }: Props) {
  const [query, setQuery] = useState(initialQuery);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setQuery(initialQuery), [initialQuery]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed) onSearch(trimmed, profile);
  };

  const submitFromInput = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed) onSearch(trimmed, profile);
  };

  return (
    <form onSubmit={submit} className="mx-auto w-full max-w-5xl">
      <div
        className={`group flex items-center rounded-none border bg-black/70 shadow-[0_18px_70px_rgba(0,0,0,0.55)] transition focus-within:border-[#e50914] ${
          large
            ? "min-h-[68px] border-white/18 md:min-h-[76px]"
            : "min-h-11 border-white/12"
        }`}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={submitFromInput}
          placeholder="Try: slow-burn thriller with rich people drama"
          className={`min-w-0 flex-1 bg-transparent text-white outline-none placeholder:text-white/38 ${
            large ? "px-5 text-xl md:px-7 md:text-2xl" : "px-4 text-sm md:px-5 md:text-base"
          }`}
        />
      </div>
    </form>
  );
}

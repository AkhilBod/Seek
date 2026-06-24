"use client";

import { Movie } from "@/lib/types";

const fallbackPoster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80";
const fallbackImages = [
  "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=900&q=80",
  "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&w=900&q=80",
  "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=900&q=80",
  "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=900&q=80",
  "https://images.unsplash.com/photo-1505686994434-e3cc5abf1330?auto=format&fit=crop&w=900&q=80",
  "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=900&q=80"
];

const imageFor = (movie: Movie) => {
  if (movie.backdrop_url || movie.poster_url) return movie.backdrop_url || movie.poster_url || fallbackPoster;
  const index = [...movie.id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % fallbackImages.length;
  return fallbackImages[index];
};

export function ResultCard({ movie, onOpen }: { movie: Movie; onOpen: (movie: Movie) => void }) {
  return (
    <article className="group relative">
      <button onClick={() => onOpen(movie)} className="block w-full text-left">
        <span className="block overflow-hidden rounded-sm bg-white/[0.06]">
          <img
            src={imageFor(movie)}
            alt=""
            className="aspect-video w-full object-cover transition duration-500 group-hover:scale-105"
          />
        </span>
        <span className="mt-3 block min-w-0">
          <span className="block truncate text-lg font-semibold leading-tight text-white md:text-xl">{movie.title}</span>
          <span className="mt-1 block truncate text-sm text-white/56">
            {movie.release_year || "Unknown"} • {movie.type} • {Math.round((movie.ranking?.final_score ?? 0) * 100)}% match
          </span>
          <span className="mt-1 block truncate text-xs text-white/36">{movie.genres.slice(0, 3).join(" / ")}</span>
        </span>
      </button>
    </article>
  );
}

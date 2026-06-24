"use client";

import { X } from "lucide-react";
import { Movie } from "@/lib/types";
import { RankingBreakdown } from "./RankingBreakdown";

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

export function ResultModal({ movie, onClose }: { movie: Movie | null; onClose: () => void }) {
  if (!movie) return null;
  const close = (event?: React.MouseEvent) => {
    event?.stopPropagation();
    onClose();
  };
  const score = Math.round((movie.ranking?.final_score ?? 0) * 100);
  const cast = movie.cast.length ? movie.cast.slice(0, 4).join(", ") : "Cast unavailable";
  const director = movie.director || "Director unavailable";
  const runtime = movie.duration || (movie.type === "Show" ? "Series" : "Feature");
  const maturity = movie.rating || (movie.type === "Show" ? "TV-MA" : "R");

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/78 px-3 py-6 backdrop-blur-sm md:py-10" onClick={() => onClose()}>
      <article
        className="thin-scrollbar w-full max-w-6xl overflow-hidden rounded-md bg-[#141414] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <section className="relative aspect-video min-h-[420px] overflow-hidden bg-black">
          <img
            src={imageFor(movie)}
            alt=""
            className="absolute inset-0 h-full w-full object-cover opacity-34"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#141414] via-[#141414]/45 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/20 to-transparent" />
          <button
            onClick={close}
            className="absolute right-5 top-5 z-20 rounded-full bg-[#181818] p-3 text-white transition hover:bg-white/15"
            aria-label="Close details"
          >
            <X className="h-7 w-7" />
          </button>
          <div className="absolute bottom-0 left-0 z-10 w-full p-6 md:p-14">
            <div className="max-w-2xl">
              <h2 className="text-4xl font-black leading-none text-white drop-shadow-2xl md:text-6xl">{movie.title}</h2>
            </div>
          </div>
        </section>

        <section className="grid gap-12 px-6 pb-14 pt-8 md:grid-cols-[1.25fr_0.75fr] md:px-14">
          <div>
            <div className="mb-6 flex flex-wrap items-center gap-3 text-lg text-white/70">
              <span>{movie.release_year || "Unknown"}</span>
              <span>{runtime}</span>
              <span className="rounded border border-white/45 px-2 py-0.5 text-sm text-white">{maturity}</span>
              <span>{movie.type}</span>
              <span className="font-semibold text-emerald-400">{score}% Match</span>
            </div>
            <p className="max-w-3xl text-xl leading-9 text-white/88">{movie.description || "No synopsis available."}</p>
            <div>
              <h3 className="mb-2 mt-10 text-xl font-bold text-white">Why this matched</h3>
              <p className="text-base leading-7 text-white/62">{movie.ranking?.explanation}</p>
            </div>
          </div>
          <aside className="space-y-5 text-lg leading-8 text-white">
            <p><span className="text-white/42">Cast:</span> {cast}</p>
            <p><span className="text-white/42">Director:</span> {director}</p>
            <p><span className="text-white/42">Genres:</span> {movie.genres.join(", ") || "Unknown"}</p>
            <p><span className="text-white/42">Availability:</span> {movie.availability_region.join(", ") || "Unknown"}</p>
            <div className="pt-6">
              {movie.ranking && <RankingBreakdown ranking={movie.ranking} />}
            </div>
          </aside>
        </section>
      </article>
    </div>
  );
}

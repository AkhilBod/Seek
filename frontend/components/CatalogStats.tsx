import { CatalogStats as Stats } from "@/lib/types";

export function CatalogStats({ stats }: { stats: Stats }) {
  const cards = [
    ["Total titles indexed", stats.total_titles.toLocaleString()],
    ["Movies", stats.movies_count.toLocaleString()],
    ["Shows", stats.shows_count.toLocaleString()],
    ["Embedding coverage", `${stats.embedding_coverage_percentage}%`]
  ];

  return (
    <div className="grid gap-4 md:grid-cols-4">
      {cards.map(([label, value]) => (
        <div key={label} className="glass rounded-lg p-5">
          <p className="text-sm text-white/48">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
        </div>
      ))}
      <div className="glass rounded-lg p-5 md:col-span-2">
        <p className="text-sm text-white/48">Regions available</p>
        <p className="mt-3 text-lg text-white">{stats.regions_available.join(", ") || "No regions indexed"}</p>
      </div>
      <div className="glass rounded-lg p-5 md:col-span-2">
        <p className="text-sm text-white/48">Search index status</p>
        <p className="mt-3 text-lg text-white">{stats.search_index_status}</p>
        <p className="mt-2 text-sm text-white/48">Last import: {stats.last_import_time}</p>
      </div>
    </div>
  );
}

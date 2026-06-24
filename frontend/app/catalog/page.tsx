import { CatalogStats } from "@/components/CatalogStats";
import { Nav } from "@/components/Nav";
import { getCatalogStats } from "@/lib/search";

export default async function CatalogPage() {
  const stats = await getCatalogStats();

  return (
    <main className="cinema-bg min-h-screen">
      <Nav />
      <section className="mx-auto max-w-6xl px-5 pb-16 pt-32">
        <p className="text-sm text-ember">Catalog</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Streaming catalog index</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-white/58">
          Seek supports CSV or JSON ingestion for large movie and show catalogs, regional availability metadata,
          embeddings, keyword indexing, and import logs.
        </p>
        <div className="mt-10">
          <CatalogStats stats={stats} />
        </div>
      </section>
    </main>
  );
}

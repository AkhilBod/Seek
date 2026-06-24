"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Nav } from "@/components/Nav";
import { SearchBar } from "@/components/SearchBar";
import { Profile } from "@/lib/types";

const backdropUrls = [
  "https://image.tmdb.org/t/p/w1280/IYUD7rAIXzBM91TT3Z5fILUS7n.jpg",
  "https://image.tmdb.org/t/p/w1280/dKqa850uvbNSCaQCV4Im1XlzEtQ.jpg",
  "https://image.tmdb.org/t/p/w1280/fnxQUdLAjmSRCdudbYClkSnrxVf.jpg",
  "https://image.tmdb.org/t/p/w1280/kMe4TKMDNXTKptQPAdOF0oZHq3V.jpg",
  "https://image.tmdb.org/t/p/w1280/4HWAQu28e2yaWrtupFPGFkdNU7V.jpg",
  "https://image.tmdb.org/t/p/w1280/A1bWhTFQKkhF1yhSKWosSyzn2Hp.jpg",
  "https://image.tmdb.org/t/p/w1280/nrp2khEM6JWFqqNLeub1J6Qafe0.jpg",
  "https://image.tmdb.org/t/p/w1280/aKPCZwkSZy2ASLo0QKeYmcoplfA.jpg",
  "https://image.tmdb.org/t/p/w1280/vXO3m7GNvUhXQwNmqRD8aOGLifh.jpg"
];

export default function Home() {
  const router = useRouter();
  const profile: Profile = "Neutral";

  const runSearch = (query: string, selectedProfile: Profile) => {
    const params = new URLSearchParams({ q: query, profile: selectedProfile });
    router.push(`/search?${params.toString()}`);
  };

  return (
    <main className="cinema-bg relative min-h-screen overflow-hidden">
      <Nav />
      <div className="pointer-events-none absolute inset-0 bg-black" />
      <div className="pointer-events-none absolute inset-x-0 top-16 grid h-[calc(100vh-4rem)] grid-cols-2 grid-rows-5 gap-2 p-2 opacity-72 md:grid-cols-3 md:grid-rows-3 md:gap-3 md:p-4">
        <div className="absolute inset-0 z-10 bg-[radial-gradient(circle_at_50%_40%,rgba(0,0,0,0.08),rgba(0,0,0,0.72)_76%),linear-gradient(180deg,rgba(126,0,8,0.62)_0%,rgba(0,0,0,0.1)_34%,#000_100%)]" />
        <div className="absolute inset-0 z-10 bg-gradient-to-r from-black/42 via-transparent to-black/42" />
        <div className="absolute inset-x-0 bottom-0 z-10 h-32 bg-gradient-to-t from-black to-transparent" />
        {backdropUrls.map((url, index) => (
          <img
            key={`${url}-${index}`}
            src={url}
            alt=""
            className={`h-full w-full rounded-sm object-cover grayscale-[12%] ${
              index === 0 ? "md:row-span-2" : ""
            } ${index === 1 ? "md:col-span-2" : ""} ${index === 5 ? "hidden md:block" : ""}`}
          />
        ))}
      </div>
      <section className="relative z-10 flex min-h-screen items-center justify-center px-5 pb-10 pt-20 md:px-10">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="w-full"
        >
          <div className="mx-auto max-w-5xl">
            <SearchBar large profile={profile} onSearch={runSearch} />
          </div>
        </motion.div>
      </section>
    </main>
  );
}

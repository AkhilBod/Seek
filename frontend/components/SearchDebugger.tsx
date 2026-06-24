"use client";

import { SearchResponse } from "@/lib/types";

export function SearchDebugger({ response }: { response: SearchResponse | null }) {
  if (!response) return null;
  const top = response.results.slice(0, 8);

  return (
    <div className="space-y-5">
      <div className="glass rounded-lg p-5">
        <div className="grid gap-4 text-sm text-white/62 md:grid-cols-3">
          <p><span className="text-white">Query:</span> {response.query}</p>
          <p><span className="text-white">Profile:</span> {response.selected_profile}</p>
          <p><span className="text-white">Embedding model:</span> {response.embedding_model}</p>
          <p><span className="text-white">Latency:</span> {response.latency_ms}ms</p>
          <p><span className="text-white">Titles searched:</span> {response.titles_searched}</p>
          <p><span className="text-white">Candidates:</span> {response.candidates_retrieved}</p>
        </div>
        <p className="mt-4 rounded-lg bg-black/28 p-3 font-mono text-xs text-white/56">{response.formula}</p>
      </div>
      <div className="glass overflow-hidden rounded-lg">
        <div className="border-b border-white/10 p-5">
          <h2 className="font-semibold text-white">Top retrieved candidates</h2>
          <p className="mt-1 text-sm text-white/48">Scores shown after profile and diversity reranking.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-white/[0.04] text-white/45">
              <tr>
                <th className="px-5 py-3">Title</th>
                <th className="px-5 py-3">Semantic</th>
                <th className="px-5 py-3">Keyword</th>
                <th className="px-5 py-3">Profile</th>
                <th className="px-5 py-3">Diversity</th>
                <th className="px-5 py-3">Final</th>
                <th className="px-5 py-3">Matched fields</th>
              </tr>
            </thead>
            <tbody>
              {top.map((movie) => (
                <tr key={movie.id} className="border-t border-white/8 text-white/64">
                  <td className="px-5 py-4 font-medium text-white">{movie.title}</td>
                  <td className="px-5 py-4">{Math.round((movie.ranking?.semantic_score ?? 0) * 100)}%</td>
                  <td className="px-5 py-4">{Math.round((movie.ranking?.keyword_score ?? 0) * 100)}%</td>
                  <td className="px-5 py-4">{Math.round((movie.ranking?.profile_score ?? 0) * 100)}%</td>
                  <td className="px-5 py-4">{Math.round((movie.ranking?.diversity_score ?? 0) * 100)}%</td>
                  <td className="px-5 py-4 text-ember">{Math.round((movie.ranking?.final_score ?? 0) * 100)}%</td>
                  <td className="px-5 py-4">{movie.ranking?.matched_fields.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

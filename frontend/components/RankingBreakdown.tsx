import { Ranking } from "@/lib/types";

const format = (value: number) => `${Math.round(value * 100)}%`;

export function RankingBreakdown({ ranking }: { ranking: Ranking }) {
  const rows = [
    ["Semantic", ranking.semantic_score],
    ["Keyword", ranking.keyword_score],
    ["Final", ranking.final_score]
  ];

  return (
    <div className="rounded-lg border border-white/10 bg-black/25 p-4">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="font-medium text-white">Ranking breakdown</span>
        <span className="text-white/45">weighted hybrid score</span>
      </div>
      <div className="space-y-3">
        {rows.map(([label, raw]) => {
          const value = raw as number;
          return (
            <div key={label as string}>
              <div className="mb-1 flex justify-between text-xs text-white/60">
                <span>{label}</span>
                <span>{format(value)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/10">
                <div className="h-full rounded-full bg-ember" style={{ width: format(value) }} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-xs leading-5 text-white/50">
        Formula: semantic meaning and keyword intent.
      </p>
    </div>
  );
}

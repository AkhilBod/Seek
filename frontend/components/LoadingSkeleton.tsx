export function LoadingSkeleton() {
  return (
    <div className="grid gap-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="glass grid animate-pulse gap-4 rounded-lg p-3 md:grid-cols-[132px_1fr]">
          <div className="aspect-[2/3] rounded-md bg-white/10" />
          <div className="space-y-4 p-1">
            <div className="h-4 w-1/3 rounded bg-white/10" />
            <div className="h-7 w-1/2 rounded bg-white/10" />
            <div className="h-20 rounded bg-white/10" />
            <div className="h-28 rounded bg-white/10" />
          </div>
        </div>
      ))}
    </div>
  );
}

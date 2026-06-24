export function EmptyState() {
  return (
    <div className="glass rounded-lg p-10 text-center">
      <h2 className="text-xl font-semibold text-white">No strong matches yet</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-white/58">
        Try describing mood, genre, pacing, a similar title, or something you want to avoid.
      </p>
    </div>
  );
}

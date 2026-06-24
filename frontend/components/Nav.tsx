import Link from "next/link";

export function Nav() {
  return (
    <nav className="fixed left-0 right-0 top-0 z-40 flex h-16 items-center bg-gradient-to-b from-black/82 to-black/0 px-5 text-sm text-white/72 md:px-10">
      <Link href="/" className="text-xl font-black tracking-[0.2em] text-[#e50914]">
        SEEK
      </Link>
    </nav>
  );
}

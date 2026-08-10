import Link from "next/link";

const LINKS = [
  { href: "/predictions", label: "Win Predictions" },
  { href: "/players", label: "Player Power Rankings" },
  { href: "/coaching", label: "Coaching Evaluation" },
];

export function Nav() {
  return (
    <nav className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-4">
        <Link href="/" className="font-semibold text-neutral-900">
          🏀 Basketball Predictions
        </Link>
        <div className="flex gap-4 text-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-neutral-600 hover:text-neutral-900 hover:underline"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}

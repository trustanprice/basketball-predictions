"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NavTeamSelector } from "./NavTeamSelector";

const LINKS = [
  { href: "/predictions", label: "Win Predictions" },
  { href: "/players", label: "Power Rankings" },
  { href: "/coaching", label: "Coaching Eval" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-line/10 bg-page">
      <div className="mx-auto flex max-w-5xl items-center gap-8 px-4 py-5 sm:px-8">
        <Link href="/" className="text-headline text-lg tracking-wide text-ink">
          Basketball Predictions
        </Link>
        <div className="flex gap-6">
          {LINKS.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-label text-xs transition-colors ${
                  isActive ? "text-accent" : "text-ink-muted hover:text-ink"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        <NavTeamSelector />
      </div>
    </nav>
  );
}

import Link from "next/link";

const CARDS = [
  {
    number: "01",
    href: "/predictions",
    title: "Win Predictions",
    description:
      "Predicted wins per team with an 80% interval, and the full model methodology.",
  },
  {
    number: "02",
    href: "/players",
    title: "Power Rankings",
    description:
      "Top 5 offense / top 5 defense league-wide — every score expandable into its full formula.",
  },
  {
    number: "03",
    href: "/coaching",
    title: "Coaching Evaluation",
    description: "Actual win% vs. roster-talent-implied win%, per coach and per team-season.",
  },
];

export default function Home() {
  return (
    <div className="space-y-16">
      <div>
        <p className="text-label mb-4 text-xs text-accent">Research Memo — NBA Analytics</p>
        <h1 className="text-headline text-5xl sm:text-6xl">Basketball Predictions</h1>
        <p className="prose-narrow mt-5 text-ink-muted">
          A win-total model, live player power rankings, and coaching evaluation — all
          served from a real API, all explainable. Every number on this site can be
          traced back to <strong>its raw inputs</strong>.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {CARDS.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="card card-interactive group rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <span className="text-label text-xs text-accent">{card.number}</span>
            <h2 className="text-headline mt-3 text-2xl">{card.title}</h2>
            <p className="mt-2 text-sm text-ink-muted">{card.description}</p>
          </Link>
        ))}
      </div>

      <div className="rounded-lg bg-gradient-to-br from-card via-card to-accent/15 p-10 text-center">
        <p className="text-label mb-3 text-xs text-ink-muted">Start Here</p>
        <h2 className="text-headline text-3xl sm:text-4xl">See how a number was calculated</h2>
        <p className="prose-narrow mx-auto mt-3 text-ink-muted">
          Pick any view — every prediction, rating, and evaluation on this site expands into
          its exact formula, raw inputs, and weights.
        </p>
        <Link
          href="/predictions"
          className="text-label mt-6 inline-block rounded-md bg-accent px-6 py-3 text-xs text-page transition-all duration-200 ease-out hover:-translate-y-0.5 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          View Win Predictions
        </Link>
      </div>
    </div>
  );
}

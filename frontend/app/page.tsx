import Link from "next/link";

const CARDS = [
  {
    href: "/predictions",
    title: "Win Predictions",
    description:
      "Predicted wins per team with an interval, and the full model methodology.",
  },
  {
    href: "/players",
    title: "Player Power Rankings",
    description:
      "Top 5 offense / top 5 defense league-wide — every score expandable into its full formula.",
  },
  {
    href: "/coaching",
    title: "Coaching Evaluation",
    description: "Actual win% vs. roster-talent-implied win%, per coach and per team-season.",
  },
];

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Basketball Predictions</h1>
      <p className="max-w-2xl text-neutral-600">
        A win-total model, live player power rankings, and coaching evaluation — all
        served from a real API, all explainable. Every number on this site can be
        traced back to its inputs.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        {CARDS.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-lg border border-neutral-200 bg-white p-5 transition hover:border-neutral-400"
          >
            <h2 className="font-medium text-neutral-900">{card.title}</h2>
            <p className="mt-1 text-sm text-neutral-600">{card.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

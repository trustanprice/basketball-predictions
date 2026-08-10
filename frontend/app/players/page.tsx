import { getPlayerPowerRankings } from "@/lib/api";
import { RatingBreakdownCard } from "@/components/RatingBreakdownCard";
import { SectionHeading } from "@/components/SectionHeading";
import { ScrollSpyNav } from "@/components/ScrollSpyNav";

const SECTIONS = [
  {
    id: "offense",
    number: "01",
    label: "Offense",
    description: "Top 5 offensive players league-wide, each expandable into its full formula.",
  },
  {
    id: "defense",
    number: "02",
    label: "Defense",
    description: "Top 5 defensive players league-wide, each expandable into its full formula.",
  },
];

export default async function PlayersPage() {
  const rankings = await getPlayerPowerRankings();

  if (!rankings) {
    return (
      <div>
        <p className="text-label mb-3 text-xs text-accent">Phase 3-4 — Live Ratings</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Player Power Rankings</h1>
        <div className="card--hollow mt-8 text-ink-muted">
          Not available yet — the backend refreshes these on its own schedule from live
          NBA.com data (see backend/AGENTS.md&apos;s refresh strategy). Check back shortly.
        </div>
      </div>
    );
  }

  return (
    <div className="md:pl-16">
      <ScrollSpyNav sections={SECTIONS} />
      <div className="mb-12">
        <p className="text-label mb-3 text-xs text-accent">Phase 3-4 — Live Ratings</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Player Power Rankings</h1>
        <p className="prose-narrow mt-4 text-ink-muted">
          {rankings.season} season, {rankings.n_qualified_players} qualified players.{" "}
          {rankings.methodology_note}
        </p>
      </div>

      <div className="space-y-16">
        <section>
          <SectionHeading number="01" id="offense" title="Offense" />
          <div className="space-y-3">
            {rankings.offense.map((b, i) => (
              <RatingBreakdownCard key={b.subject_id} rank={i + 1} breakdown={b} />
            ))}
          </div>
        </section>
        <section>
          <SectionHeading number="02" id="defense" title="Defense" />
          <div className="space-y-3">
            {rankings.defense.map((b, i) => (
              <RatingBreakdownCard key={b.subject_id} rank={i + 1} breakdown={b} />
            ))}
          </div>
        </section>
      </div>

      <p className="text-label mt-10 text-[11px] text-ink-muted/70">
        Generated {new Date(rankings.generated_at).toLocaleString()}
      </p>
    </div>
  );
}

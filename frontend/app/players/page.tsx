import { getPlayerPowerRankings } from "@/lib/api";
import { RatingBreakdownCard } from "@/components/RatingBreakdownCard";

export default async function PlayersPage() {
  const rankings = await getPlayerPowerRankings();

  if (!rankings) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Player Power Rankings</h1>
        <div className="rounded-lg border border-neutral-200 bg-white p-6 text-neutral-600">
          Not available yet — the backend refreshes these on its own schedule from live
          NBA.com data (see backend/AGENTS.md&apos;s refresh strategy). Check back shortly.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Player Power Rankings</h1>
        <p className="mt-1 text-neutral-600">{rankings.season} season, {rankings.n_qualified_players} qualified players.</p>
        <p className="mt-2 max-w-3xl text-sm text-neutral-500">{rankings.methodology_note}</p>
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        <section>
          <h2 className="mb-3 font-medium text-neutral-900">Top 5 Offense</h2>
          <div className="space-y-3">
            {rankings.offense.map((b, i) => (
              <RatingBreakdownCard key={b.subject_id} rank={i + 1} breakdown={b} />
            ))}
          </div>
        </section>
        <section>
          <h2 className="mb-3 font-medium text-neutral-900">Top 5 Defense</h2>
          <div className="space-y-3">
            {rankings.defense.map((b, i) => (
              <RatingBreakdownCard key={b.subject_id} rank={i + 1} breakdown={b} />
            ))}
          </div>
        </section>
      </div>

      <p className="text-xs text-neutral-400">
        Generated {new Date(rankings.generated_at).toLocaleString()}
      </p>
    </div>
  );
}

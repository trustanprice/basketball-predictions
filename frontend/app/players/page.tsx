import { getPlayerPowerRankings, getPlayerProjectedLeaders } from "@/lib/api";
import { PlayersExplorer } from "@/components/PlayersExplorer";

export default async function PlayersPage() {
  const [rankings, projected] = await Promise.all([
    getPlayerPowerRankings(),
    getPlayerProjectedLeaders(),
  ]);

  if (!rankings) {
    return (
      <div>
        <p className="text-label mb-3 text-xs text-accent">Phase 3-4 — Live Ratings</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Player Power Rankings</h1>
        <div className="card--hollow mt-8 text-ink-muted">
          Rankings aren&apos;t in yet — these refresh on their own schedule from live NBA.com
          data, and the first pull hasn&apos;t landed. Check back shortly.
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-12">
        <p className="text-label mb-3 text-xs text-accent">Phase 3-4 — Live Ratings</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Player Power Rankings</h1>
        <p className="prose-narrow mt-4 text-ink-muted">
          {rankings.season} season, {rankings.n_qualified_players} qualified players.{" "}
          {rankings.methodology_note}
        </p>
      </div>

      <PlayersExplorer
        offense={rankings.offense}
        defense={rankings.defense}
        projected={projected ? { offense: projected.offense, defense: projected.defense, note: projected.note } : null}
      />

      <p className="text-label mt-10 text-[11px] text-ink-muted/70">
        Generated {new Date(rankings.generated_at).toLocaleString()}
      </p>
    </div>
  );
}

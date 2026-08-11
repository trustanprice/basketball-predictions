import type { RatingBreakdown, RatingComponent } from "@/lib/types";
import { PlayerHeadshot } from "./PlayerHeadshot";

/**
 * Each component's contribution to the composite, at a glance — a
 * zero-centered diverging bar (positive contributions extend right in the
 * "positive/validated" green, negative extend left in muted gray), sized
 * relative to the largest |contribution| in this specific breakdown. This is
 * a companion to the full numeric table below it, not a replacement — the
 * table is still what makes composite_score hand-reproducible; this is what
 * makes "what actually drove this score" readable in one glance instead of
 * requiring someone to scan five rows of decimals.
 */
function ContributionBars({ components }: { components: RatingComponent[] }) {
  const maxAbs = Math.max(...components.map((c) => Math.abs(c.contribution)), 0.001);
  return (
    <div className="mt-4 space-y-1.5">
      {components.map((c) => {
        const isPositive = c.contribution > 0;
        const widthPct = (Math.abs(c.contribution) / maxAbs) * 50;
        return (
          <div key={c.name} className="flex items-center gap-2">
            <span className="text-label w-36 shrink-0 truncate text-[10px] text-ink-muted">{c.name}</span>
            <div className="relative h-2 flex-1 rounded-full bg-line/10">
              <div aria-hidden className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-line/30" />
              <div
                aria-hidden
                className={`absolute top-0 h-full rounded-full ${isPositive ? "bg-positive" : "bg-ink-muted"}`}
                style={isPositive ? { left: "50%", width: `${widthPct}%` } : { right: "50%", width: `${widthPct}%` }}
              />
            </div>
            <span
              className={`text-label w-14 shrink-0 text-right text-[10px] ${isPositive ? "text-positive" : "text-ink-muted"}`}
            >
              {isPositive ? "+" : ""}
              {c.contribution.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Renders one composite score with its full breakdown, expandable via native
 * <details> — every component's raw value, z-score, weight, and contribution,
 * per backend/AGENTS.md's transparency requirement: a reader should be able to
 * reproduce the composite_score by hand from what's shown here.
 */
export function RatingBreakdownCard({
  rank,
  breakdown,
}: {
  rank: number;
  breakdown: RatingBreakdown;
}) {
  return (
    <details className="card card-interactive">
      <summary className="flex cursor-pointer items-center justify-between gap-3 rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        <span className="flex items-center gap-3">
          <span className="text-label text-xs text-ink-muted">{String(rank).padStart(2, "0")}</span>
          <PlayerHeadshot playerId={breakdown.subject_id} name={breakdown.subject_name} size={36} />
          <span className="text-headline text-xl">{breakdown.subject_name}</span>
        </span>
        <span className="text-label shrink-0 text-sm text-accent">
          {breakdown.composite_score.toFixed(3)}
        </span>
      </summary>
      <ContributionBars components={breakdown.components} />
      <table className="mt-4 w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line/10">
            <th className="text-label py-1.5 pr-3 text-[11px] font-normal text-ink-muted">
              Component
            </th>
            <th className="text-label py-1.5 pr-3 text-[11px] font-normal text-ink-muted">
              Raw
            </th>
            <th className="text-label py-1.5 pr-3 text-[11px] font-normal text-ink-muted">
              Z-score
            </th>
            <th className="text-label py-1.5 pr-3 text-[11px] font-normal text-ink-muted">
              Weight
            </th>
            <th className="text-label py-1.5 text-[11px] font-normal text-ink-muted">
              Contribution
            </th>
          </tr>
        </thead>
        <tbody>
          {breakdown.components.map((c) => (
            <tr key={c.name} className="border-b border-line/5">
              <td className="text-label py-2 pr-3 text-xs text-ink">
                {c.name}
                {!c.higher_is_better && (
                  <span className="ml-1 text-ink-muted/60">(lower better)</span>
                )}
              </td>
              <td className="py-2 pr-3 text-ink-muted">
                {typeof c.raw_value === "number" ? c.raw_value.toFixed(3) : c.raw_value}
              </td>
              <td className="py-2 pr-3 text-ink-muted">{c.z_score.toFixed(3)}</td>
              <td className="py-2 pr-3 text-ink-muted">{c.weight}</td>
              <td className={`py-2 ${c.contribution > 0 ? "text-positive" : "text-ink-muted"}`}>
                {c.contribution > 0 ? "+" : ""}
                {c.contribution.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

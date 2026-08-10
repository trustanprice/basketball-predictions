import type { RatingBreakdown } from "@/lib/types";

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
        <span className="flex items-baseline gap-3">
          <span className="text-label text-xs text-ink-muted">{String(rank).padStart(2, "0")}</span>
          <span className="text-headline text-xl">{breakdown.subject_name}</span>
        </span>
        <span className="text-label shrink-0 text-sm text-accent">
          {breakdown.composite_score.toFixed(3)}
        </span>
      </summary>
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

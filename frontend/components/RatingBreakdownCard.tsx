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
    <details className="rounded-lg border border-neutral-200 bg-white p-4">
      <summary className="flex cursor-pointer items-center justify-between">
        <span className="font-medium text-neutral-900">
          {rank}. {breakdown.subject_name}
        </span>
        <span className="text-sm text-neutral-500">
          score {breakdown.composite_score.toFixed(3)}
        </span>
      </summary>
      <table className="mt-3 w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-200 text-neutral-500">
            <th className="py-1 pr-3 font-medium">Component</th>
            <th className="py-1 pr-3 font-medium">Raw value</th>
            <th className="py-1 pr-3 font-medium">Z-score</th>
            <th className="py-1 pr-3 font-medium">Weight</th>
            <th className="py-1 font-medium">Contribution</th>
          </tr>
        </thead>
        <tbody>
          {breakdown.components.map((c) => (
            <tr key={c.name} className="border-b border-neutral-100">
              <td className="py-1 pr-3">
                {c.name}
                {!c.higher_is_better && (
                  <span className="ml-1 text-neutral-400">(lower is better)</span>
                )}
              </td>
              <td className="py-1 pr-3 text-neutral-600">
                {typeof c.raw_value === "number" ? c.raw_value.toFixed(3) : c.raw_value}
              </td>
              <td className="py-1 pr-3 text-neutral-600">{c.z_score.toFixed(3)}</td>
              <td className="py-1 pr-3 text-neutral-600">{c.weight}</td>
              <td className="py-1 text-neutral-600">{c.contribution.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

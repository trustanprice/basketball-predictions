"use client";

import { useState } from "react";
import type { CoachCareerSummary, CoachTeamSeason } from "@/lib/types";

function formatPct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

/**
 * Career summary (primary view) with a click-to-expand team-season history
 * per coach. Both datasets are fetched once, server-side, and passed in —
 * expanding a coach just filters the already-loaded team-season list, no
 * extra API call.
 */
export function CoachingExplorer({
  careerSummary,
  teamSeasons,
}: {
  careerSummary: CoachCareerSummary[];
  teamSeasons: CoachTeamSeason[];
}) {
  const [expandedCoach, setExpandedCoach] = useState<string | null>(null);
  const seasonsForExpanded = teamSeasons
    .filter((ts) => ts.coach === expandedCoach)
    .sort((a, b) => a.season - b.season);

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-neutral-200 text-neutral-500">
              <th className="px-4 py-2 font-medium">Coach</th>
              <th className="px-4 py-2 font-medium">Teams</th>
              <th className="px-4 py-2 font-medium">Seasons</th>
              <th className="px-4 py-2 font-medium">Avg actual win%</th>
              <th className="px-4 py-2 font-medium">Avg implied win%</th>
              <th className="px-4 py-2 font-medium">Avg wins above expectation</th>
            </tr>
          </thead>
          <tbody>
            {careerSummary.map((c) => (
              <tr
                key={c.coach}
                onClick={() => setExpandedCoach((cur) => (cur === c.coach ? null : c.coach))}
                className={`cursor-pointer border-b border-neutral-100 hover:bg-neutral-50 ${
                  expandedCoach === c.coach ? "bg-neutral-50" : ""
                }`}
              >
                <td className="px-4 py-2 font-medium text-neutral-900">{c.coach}</td>
                <td className="px-4 py-2 text-neutral-600">{c.teams_coached.join(", ")}</td>
                <td className="px-4 py-2 text-neutral-600">{c.seasons_coached}</td>
                <td className="px-4 py-2 text-neutral-600">{formatPct(c.avg_actual_win_pct)}</td>
                <td className="px-4 py-2 text-neutral-600">{formatPct(c.avg_implied_win_pct)}</td>
                <td
                  className={`px-4 py-2 font-medium ${
                    c.avg_wins_above_expectation >= 0 ? "text-emerald-700" : "text-red-700"
                  }`}
                >
                  {c.avg_wins_above_expectation >= 0 ? "+" : ""}
                  {formatPct(c.avg_wins_above_expectation)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {expandedCoach && (
        <div className="rounded-lg border border-neutral-200 bg-white p-4">
          <h3 className="mb-3 font-medium text-neutral-900">{expandedCoach} — team-season history</h3>
          <div className="space-y-3">
            {seasonsForExpanded.map((ts) => (
              <details key={`${ts.season}-${ts.team}`} className="rounded-md border border-neutral-100 p-3">
                <summary className="flex cursor-pointer items-center justify-between text-sm">
                  <span>
                    {ts.season} — {ts.team}
                  </span>
                  <span
                    className={ts.wins_above_expectation >= 0 ? "text-emerald-700" : "text-red-700"}
                  >
                    actual {formatPct(ts.actual_win_pct)} vs. implied {formatPct(ts.implied_win_pct)} (
                    {ts.wins_above_expectation >= 0 ? "+" : ""}
                    {formatPct(ts.wins_above_expectation)})
                  </span>
                </summary>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-neutral-200 text-neutral-500">
                      <th className="py-1 pr-3 font-medium">Talent component</th>
                      <th className="py-1 pr-3 font-medium">Raw value</th>
                      <th className="py-1 pr-3 font-medium">Z-score</th>
                      <th className="py-1 pr-3 font-medium">Weight</th>
                      <th className="py-1 font-medium">Contribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ts.talent_breakdown.components.map((c) => (
                      <tr key={c.name} className="border-b border-neutral-100">
                        <td className="py-1 pr-3">{c.name}</td>
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
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

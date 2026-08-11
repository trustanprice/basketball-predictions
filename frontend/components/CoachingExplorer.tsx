"use client";

import { useState, type CSSProperties } from "react";
import type { CoachCareerSummary, CoachTeamSeason, TeamPrediction } from "@/lib/types";
import { getTeamColors, isTextSafe } from "@/lib/teamColors";
import { SectionHeading } from "./SectionHeading";
import { Popover } from "./Popover";
import { StyleCorrelationScatter } from "./StyleCorrelationScatter";
import { TeamShotHeatmap } from "./TeamShotHeatmap";
import { useTeamTheme } from "./TeamThemeProvider";

// Matches the historical range backend/ratings/refresh_team_style.py covers
// (season-start-year 2016-2025) — the shot-chart endpoint itself supports
// any completed season, this is just what the rest of this page's data spans.
const SHOT_HEATMAP_SEASONS = Array.from({ length: 10 }, (_, i) => {
  const startYear = 2025 - i;
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
});

function formatPct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function WaeValue({ value }: { value: number }) {
  return (
    <span className={`text-label ${value >= 0 ? "text-positive" : "text-ink-muted"}`}>
      {value >= 0 ? "+" : ""}
      {formatPct(value)}
    </span>
  );
}

/**
 * A team name, anywhere it appears in this page (career-summary's teams
 * list, a season row's team) — click reveals that team's current win-model
 * forecast (predicted wins, interval, top_features), the same Popover
 * pattern used everywhere else a name is clickable on this site.
 */
function TeamNameChip({ team, predictions }: { team: string; predictions: TeamPrediction[] }) {
  const prediction = predictions.find((p) => p.team === team);
  const { selectedTeam } = useTeamTheme();
  const { primary } = getTeamColors(team);
  const textColor = isTextSafe(primary) ? primary : undefined;
  const isSitewideSelection = team === selectedTeam;

  return (
    <Popover
      trigger={
        <span
          className={`inline-flex items-center gap-1.5 rounded-full ${
            isSitewideSelection ? "ring-1 ring-offset-1 ring-offset-page" : ""
          }`}
          style={isSitewideSelection ? ({ "--tw-ring-color": primary } as CSSProperties) : undefined}
        >
          <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: primary }} />
          <span style={textColor ? { color: textColor } : undefined}>{team}</span>
        </span>
      }
    >
      <p className="text-label" style={{ color: textColor ?? "var(--color-ink)" }}>
        {team}
      </p>
      {prediction ? (
        <>
          <p className="text-label mt-2 text-2xl text-accent">
            {prediction.predicted_wins.toFixed(0)}
            <span className="ml-2 text-[10px] text-ink-muted">predicted wins, {prediction.season}</span>
          </p>
          {prediction.predicted_wins_lower !== null && prediction.predicted_wins_upper !== null && (
            <p className="text-label mt-1 text-[10px] text-ink-muted">
              {prediction.predicted_wins_lower.toFixed(0)}–{prediction.predicted_wins_upper.toFixed(0)} win
              interval
            </p>
          )}
          {Object.keys(prediction.top_features).length > 0 && (
            <div className="mt-3 space-y-1 border-t border-line/10 pt-3">
              {Object.entries(prediction.top_features).map(([feature, value]) => (
                <p key={feature} className="text-label flex justify-between text-[10px] text-ink-muted">
                  <span>{feature}</span>
                  <span>{value.toFixed(2)}</span>
                </p>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="mt-2 text-xs text-ink-muted">No current forecast available.</p>
      )}
    </Popover>
  );
}

/**
 * Career summary (primary view) with a click-to-expand team-season history
 * per coach. All three datasets are fetched once, server-side, and passed
 * in — expanding a coach just filters the already-loaded team-season list,
 * no extra API call; team-name popovers read from the already-loaded
 * predictions list the same way. Owns its own section structure (01 Career
 * Summary / 02 Wins Above Expectation) since expandedCoach state is shared
 * across both.
 */
export function CoachingExplorer({
  careerSummary,
  teamSeasons,
  predictions,
}: {
  careerSummary: CoachCareerSummary[];
  teamSeasons: CoachTeamSeason[];
  predictions: TeamPrediction[];
}) {
  const [expandedCoach, setExpandedCoach] = useState<string | null>(null);
  const seasonsForExpanded = teamSeasons
    .filter((ts) => ts.coach === expandedCoach)
    .sort((a, b) => a.season - b.season);

  return (
    <div className="space-y-16">
      <section>
        <SectionHeading number="01" id="career-summary" title="Career Summary" />
        <div className="overflow-x-auto rounded-lg border border-line/10 bg-card">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line/10">
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Coach</th>
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Teams</th>
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Seasons</th>
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Actual Win%</th>
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Implied Win%</th>
                <th className="text-label px-4 py-3 text-[11px] font-normal text-ink-muted">Avg WAE</th>
              </tr>
            </thead>
            <tbody>
              {careerSummary.map((c) => {
                const isExpanded = expandedCoach === c.coach;
                return (
                  <tr
                    key={c.coach}
                    className={`border-b border-line/5 transition-colors duration-200 ease-out ${
                      isExpanded ? "bg-page/60" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setExpandedCoach((cur) => (cur === c.coach ? null : c.coach))}
                        aria-expanded={isExpanded}
                        aria-controls="wins-above-expectation"
                        className="cursor-pointer rounded-sm text-ink underline decoration-ink-muted/40 decoration-dotted underline-offset-4 transition-colors duration-200 ease-out hover:decoration-ink-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                      >
                        {c.coach}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        {c.teams_coached.map((team) => (
                          <TeamNameChip key={team} team={team} predictions={predictions} />
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{c.seasons_coached}</td>
                    <td className="px-4 py-3 text-ink-muted">{formatPct(c.avg_actual_win_pct)}</td>
                    <td className="px-4 py-3 text-ink-muted">{formatPct(c.avg_implied_win_pct)}</td>
                    <td className="px-4 py-3">
                      <WaeValue value={c.avg_wins_above_expectation} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {expandedCoach && (
        <section>
          <SectionHeading
            number="02"
            id="wins-above-expectation"
            title="Wins Above Expectation"
            description={`${expandedCoach} — team-season history. Expand any season for the talent composite's formula.`}
          />
          <div className="space-y-3">
            {seasonsForExpanded.map((ts) => (
              <details key={`${ts.season}-${ts.team}`} className="card card-interactive">
                <summary className="flex cursor-pointer items-center justify-between gap-3 rounded-sm text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                  {/* Plain text, not a TeamNameChip: <summary> is itself an
                      interactive toggle, and nesting another interactive
                      (button-based popover) element inside it is both invalid
                      HTML and a real bug (a click would fire both the details
                      toggle and the popover). This team's forecast is still
                      one click away via the Career Summary table above. */}
                  <span className="text-headline flex items-center gap-2 text-lg">
                    {ts.season} <span className="text-ink-muted">—</span> {ts.team}
                  </span>
                  <span className="text-label text-xs text-ink-muted">
                    actual {formatPct(ts.actual_win_pct)} vs. implied {formatPct(ts.implied_win_pct)} (
                    <WaeValue value={ts.wins_above_expectation} />)
                  </span>
                </summary>
                {(ts.pace !== null || ts.ast_pct !== null || ts.three_pa_rate !== null) && (
                  <p className="text-label mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-ink-muted">
                    <span>Style context (correlation, not causation):</span>
                    {ts.pace !== null && <span>Pace {ts.pace.toFixed(1)}</span>}
                    {ts.ast_pct !== null && <span>AST% {(ts.ast_pct * 100).toFixed(1)}%</span>}
                    {ts.three_pa_rate !== null && <span>3PA Rate {(ts.three_pa_rate * 100).toFixed(1)}%</span>}
                  </p>
                )}
                <table className="mt-4 w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/10">
                      <th className="text-label py-1.5 pr-3 text-[10px] font-normal text-ink-muted">
                        Talent Component
                      </th>
                      <th className="text-label py-1.5 pr-3 text-[10px] font-normal text-ink-muted">
                        Raw
                      </th>
                      <th className="text-label py-1.5 pr-3 text-[10px] font-normal text-ink-muted">
                        Z-score
                      </th>
                      <th className="text-label py-1.5 pr-3 text-[10px] font-normal text-ink-muted">
                        Weight
                      </th>
                      <th className="text-label py-1.5 text-[10px] font-normal text-ink-muted">
                        Contribution
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ts.talent_breakdown.components.map((c) => (
                      <tr key={c.name} className="border-b border-line/5">
                        <td className="text-label py-2 pr-3 text-[11px] text-ink">{c.name}</td>
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
            ))}
          </div>
        </section>
      )}

      <section>
        <SectionHeading
          number="03"
          id="team-style"
          title="Team Style"
          description="Real pace/shot-profile data and shot-location heatmaps, shown as descriptive context alongside coaching outcomes — not a causal explanation for them."
        />
        <div className="space-y-8">
          <StyleCorrelationScatter teamSeasons={teamSeasons} />
          <TeamShotHeatmap
            defaultTeam={teamSeasons[0]?.team ?? "Boston Celtics"}
            seasons={SHOT_HEATMAP_SEASONS}
          />
        </div>
      </section>
    </div>
  );
}

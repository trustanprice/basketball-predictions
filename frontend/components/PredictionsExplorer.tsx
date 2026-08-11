"use client";

import { useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { getSafeTeamAccentColor, getTeamColors } from "@/lib/teamColors";
import { SectionHeading } from "./SectionHeading";
import { MethodologyPanel } from "./MethodologyPanel";
import { FeatureScatterChart } from "./FeatureScatterChart";

/**
 * Client island for the predictions page's interactive pieces. Which
 * team's forecast is showing is entirely local state, independent of the
 * nav's sitewide team selector (components/NavTeamSelector.tsx, via
 * TeamThemeProvider) — that control only recolors the site now, it doesn't
 * pick what's displayed anywhere. So a user can have the whole UI themed
 * Cavaliers while this section shows the Lakers' forecast; nothing here
 * reads or writes the sitewide selection. The dropdown below and the
 * scatter chart's click-a-point interaction both write to this same local
 * state.
 */
export function PredictionsExplorer({
  predictions,
  methodology,
}: {
  predictions: TeamPrediction[];
  methodology: ModelMetadata;
}) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const selected = selectedTeam ? predictions.find((p) => p.team === selectedTeam) : undefined;
  const selectedColor = selected ? getSafeTeamAccentColor(selected.team) : undefined;
  const selectedPrimary = selected ? getTeamColors(selected.team).primary : undefined;
  const sortedTeams = [...predictions].sort((a, b) => a.team.localeCompare(b.team));

  return (
    <div className="space-y-16">
      <section>
        <SectionHeading number="01" id="prediction" title="Prediction" />

        <div className="mb-5">
          <label htmlFor="team-select" className="text-label mb-2 block text-xs text-ink-muted">
            Select a Team
          </label>
          <select
            id="team-select"
            value={selectedTeam ?? ""}
            onChange={(e) => setSelectedTeam(e.target.value || null)}
            className="text-label rounded-md border border-line/20 bg-card px-4 py-2.5 text-xs text-ink"
          >
            <option value="">Select a team…</option>
            {sortedTeams.map((p) => (
              <option key={p.team} value={p.team}>
                {p.team}
              </option>
            ))}
          </select>
        </div>

        {selected ? (
          // Hollow/outline: this is always the current, unplayed forecast
          // season — "locked/future," not a settled result. The left border
          // is team color (identity), separate from the amber key-stat number.
          <div
            className="card--hollow border-l-4 transition-colors duration-200 ease-out"
            style={{ borderLeftColor: selectedPrimary }}
          >
            <p className="text-label text-xs text-ink-muted">
              <span style={{ color: selectedColor }}>{selected.team}</span> — {selected.season} Forecast
            </p>
            <span
              aria-hidden
              className="mt-1.5 block h-0.5 w-10 rounded-full transition-colors duration-200 ease-out"
              style={{ backgroundColor: selectedPrimary }}
            />
            <p className="text-label mt-3 text-6xl text-accent">
              {selected.predicted_wins.toFixed(0)}
              {selected.actual_wins !== null && (
                <span className="ml-4 text-base text-ink-muted">
                  actual {selected.actual_wins.toFixed(0)}
                </span>
              )}
            </p>
            {selected.predicted_wins_lower !== null && selected.predicted_wins_upper !== null && (
              <p className="text-label mt-3 text-xs text-ink-muted">
                80% interval: {selected.predicted_wins_lower.toFixed(0)}–
                {selected.predicted_wins_upper.toFixed(0)} wins
              </p>
            )}
          </div>
        ) : (
          <div className="card--hollow text-sm text-ink-muted">
            Select a team above (or click a point on the chart below) to see its forecast.
          </div>
        )}
      </section>

      <section>
        <SectionHeading number="02" id="methodology" title="Methodology" />
        <MethodologyPanel metadata={methodology} />
      </section>

      <section>
        <SectionHeading number="03" id="chart" title="Feature Chart" />
        <FeatureScatterChart
          predictions={predictions}
          metadata={methodology}
          selectedTeam={selectedTeam}
          onSelectTeam={setSelectedTeam}
        />
      </section>
    </div>
  );
}

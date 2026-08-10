"use client";

import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { getSafeTeamAccentColor, getTeamColors } from "@/lib/teamColors";
import { SectionHeading } from "./SectionHeading";
import { MethodologyPanel } from "./MethodologyPanel";
import { FeatureScatterChart } from "./FeatureScatterChart";
import { useTeamTheme } from "./TeamThemeProvider";

/**
 * Client island for the predictions page's interactive pieces. Team
 * selection itself lives in the nav now (components/NavTeamSelector.tsx,
 * via TeamThemeProvider) — this page has no picker of its own; the forecast
 * card and scatter chart just reflect and (for the chart's click-a-point
 * interaction) write to that same global selection. Everything else it
 * needs (all 30 teams' predictions, the shared methodology) is fetched once,
 * server-side, and passed in — no client-side API calls, per
 * frontend/AGENTS.md.
 */
export function PredictionsExplorer({
  predictions,
  methodology,
}: {
  predictions: TeamPrediction[];
  methodology: ModelMetadata;
}) {
  const { selectedTeam, setSelectedTeam } = useTeamTheme();
  const selected = selectedTeam ? predictions.find((p) => p.team === selectedTeam) : undefined;
  const selectedColor = selected ? getSafeTeamAccentColor(selected.team) : undefined;
  const selectedPrimary = selected ? getTeamColors(selected.team).primary : undefined;

  return (
    <div className="space-y-16">
      <section>
        <SectionHeading number="01" id="prediction" title="Prediction" />

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
            Select a team from the nav above to see its forecast.
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

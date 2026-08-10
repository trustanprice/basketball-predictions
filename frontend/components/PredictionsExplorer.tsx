"use client";

import { useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { getSafeTeamAccentColor, getTeamColors, isTextSafe } from "@/lib/teamColors";
import { SectionHeading } from "./SectionHeading";
import { MethodologyPanel } from "./MethodologyPanel";
import { FeatureScatterChart } from "./FeatureScatterChart";
import { Popover } from "./Popover";

function TeamChip({
  prediction,
  isSelected,
  onSelect,
}: {
  prediction: TeamPrediction;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const { primary } = getTeamColors(prediction.team);
  const textColor = isTextSafe(primary) ? primary : undefined;

  return (
    <Popover
      align="left"
      renderTrigger={(triggerProps) => (
        <button
          type="button"
          onClick={(e) => {
            onSelect();
            triggerProps.onClick(e);
          }}
          aria-expanded={triggerProps["aria-expanded"]}
          aria-controls={triggerProps["aria-controls"]}
          className={`text-label flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-[11px] transition-colors duration-200 ease-out ${
            isSelected ? "border-accent/40 bg-card" : "border-line/10 bg-card hover:border-line/20"
          }`}
        >
          <span
            aria-hidden
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: primary }}
          />
          <span className="truncate" style={textColor ? { color: textColor } : undefined}>
            {prediction.team}
          </span>
        </button>
      )}
    >
      <p className="text-label text-ink">{prediction.team}</p>
      <p className="text-label mt-2 text-2xl text-accent">{prediction.predicted_wins.toFixed(0)}</p>
      {prediction.predicted_wins_lower !== null && prediction.predicted_wins_upper !== null && (
        <p className="text-label mt-1 text-[10px] text-ink-muted">
          {prediction.predicted_wins_lower.toFixed(0)}–{prediction.predicted_wins_upper.toFixed(0)} win
          interval
        </p>
      )}
    </Popover>
  );
}

/**
 * Client island for the predictions page's interactive pieces: the team
 * selector (dropdown + a clickable team grid, kept in sync) and the shared
 * selectedTeam state that flows into the forecast card and the scatter
 * chart. Everything it needs (all 30 teams' predictions, the shared
 * methodology) is fetched once, server-side, and passed in — no client-side
 * API calls, per frontend/AGENTS.md. Owns the section structure (01
 * Prediction / 02 Methodology / 03 Chart) since selectedTeam state is shared
 * across all three.
 */
export function PredictionsExplorer({
  predictions,
  methodology,
}: {
  predictions: TeamPrediction[];
  methodology: ModelMetadata;
}) {
  const sorted = [...predictions].sort((a, b) => a.team.localeCompare(b.team));
  const [selectedTeam, setSelectedTeam] = useState(sorted[0]?.team ?? "");
  const selected = predictions.find((p) => p.team === selectedTeam);
  const selectedColor = selected ? getSafeTeamAccentColor(selected.team) : undefined;
  const selectedPrimary = selected ? getTeamColors(selected.team).primary : undefined;

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
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
            className="text-label rounded-md border border-line/20 bg-card px-4 py-2.5 text-xs text-ink"
          >
            {sorted.map((p) => (
              <option key={p.team} value={p.team}>
                {p.team}
              </option>
            ))}
          </select>
        </div>

        {selected && (
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
        )}

        <div className="mt-6">
          <p className="text-label mb-2 text-xs text-ink-muted">All Teams</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {sorted.map((p) => (
              <TeamChip
                key={p.team}
                prediction={p}
                isSelected={p.team === selectedTeam}
                onSelect={() => setSelectedTeam(p.team)}
              />
            ))}
          </div>
        </div>
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

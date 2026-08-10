"use client";

import { useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { MethodologyPanel } from "./MethodologyPanel";
import { FeatureScatterChart } from "./FeatureScatterChart";

/**
 * Client island for the one genuinely interactive piece of the predictions
 * page: the team selector. Everything it needs (all 30 teams' predictions,
 * the shared methodology) is fetched once, server-side, and passed in — no
 * client-side API calls, per frontend/AGENTS.md.
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

  return (
    <div className="space-y-6">
      <div>
        <label htmlFor="team-select" className="mb-1 block text-sm font-medium text-neutral-700">
          Select a team
        </label>
        <select
          id="team-select"
          value={selectedTeam}
          onChange={(e) => setSelectedTeam(e.target.value)}
          className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm"
        >
          {sorted.map((p) => (
            <option key={p.team} value={p.team}>
              {p.team}
            </option>
          ))}
        </select>
      </div>

      {selected && (
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <p className="text-sm text-neutral-500">
            {selected.team} — {selected.season} predicted wins
          </p>
          <p className="text-3xl font-semibold text-neutral-900">
            {selected.predicted_wins.toFixed(0)}
            {selected.actual_wins !== null && (
              <span className="ml-3 text-base font-normal text-neutral-500">
                actual: {selected.actual_wins.toFixed(0)}
              </span>
            )}
          </p>
          {selected.predicted_wins_lower !== null && selected.predicted_wins_upper !== null && (
            <p className="mt-1 text-sm text-neutral-500">
              80% interval: {selected.predicted_wins_lower.toFixed(0)}–
              {selected.predicted_wins_upper.toFixed(0)} wins
            </p>
          )}
        </div>
      )}

      <MethodologyPanel metadata={methodology} />

      <FeatureScatterChart predictions={predictions} metadata={methodology} selectedTeam={selectedTeam} />
    </div>
  );
}

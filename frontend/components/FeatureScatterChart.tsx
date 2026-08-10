"use client";

import { useMemo, useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";

const WIDTH = 560;
const HEIGHT = 380;
const PADDING = { top: 16, right: 16, bottom: 40, left: 56 };

/**
 * Scatter of two of the win model's top-importance features, one point per
 * team. Axes are chosen dynamically at render time, not hardcoded to any
 * specific feature names: walks metadata.top_feature_importance in rank
 * order and picks the first two features present (non-null) for every team
 * being plotted. Today that's usually NOT the literal top-2 by importance —
 * SOS (the #1 feature) is null for the entire current forecast season (a
 * real, pre-existing data-pipeline gap — see backend/AGENTS.md) — so this
 * shows an explicit on-chart caveat whenever the plotted axes aren't the true
 * top-2, rather than silently presenting them as if they were.
 */
export function FeatureScatterChart({
  predictions,
  metadata,
  selectedTeam,
}: {
  predictions: TeamPrediction[];
  metadata: ModelMetadata;
  selectedTeam?: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  const axisChoice = useMemo(() => {
    const rankedNames = metadata.top_feature_importance.map((f) => f.feature);
    const availableEverywhere = rankedNames.filter((name) =>
      predictions.every((p) => typeof p.top_features[name] === "number")
    );
    return {
      xFeature: availableEverywhere[0] ?? null,
      yFeature: availableEverywhere[1] ?? null,
      isTrueTop2: availableEverywhere[0] === rankedNames[0] && availableEverywhere[1] === rankedNames[1],
      topTwoByImportance: rankedNames.slice(0, 2),
    };
  }, [predictions, metadata]);

  if (!axisChoice.xFeature || !axisChoice.yFeature) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-4 text-sm text-neutral-500">
        Not enough feature data available across all teams to plot a chart right now.
      </div>
    );
  }

  const { xFeature, yFeature } = axisChoice;
  const points = predictions.map((p) => ({
    team: p.team,
    x: p.top_features[xFeature],
    y: p.top_features[yFeature],
    predictedWins: p.predicted_wins,
  }));

  const xValues = points.map((p) => p.x);
  const yValues = points.map((p) => p.y);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const winsMin = Math.min(...points.map((p) => p.predictedWins));
  const winsMax = Math.max(...points.map((p) => p.predictedWins));

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const scaleX = (v: number) =>
    PADDING.left + (xMax === xMin ? plotWidth / 2 : ((v - xMin) / (xMax - xMin)) * plotWidth);
  const scaleY = (v: number) =>
    PADDING.top + plotHeight - (yMax === yMin ? plotHeight / 2 : ((v - yMin) / (yMax - yMin)) * plotHeight);
  const scaleRadius = (wins: number) =>
    winsMax === winsMin ? 5 : 4 + ((wins - winsMin) / (winsMax - winsMin)) * 6;

  const hoveredPoint = points.find((p) => p.team === hovered);

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="font-medium text-neutral-900">
          {xFeature} vs. {yFeature}
        </h3>
        <span className="text-xs text-neutral-500">dot size = predicted wins</span>
      </div>

      {!axisChoice.isTrueTop2 && (
        <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Showing {xFeature} vs. {yFeature}, not the true top-2 by importance (
          {axisChoice.topTwoByImportance.join(", ")}) — one or both aren&apos;t available for
          every team right now. See {metadata.feature_notes[axisChoice.topTwoByImportance[0]]
            ? axisChoice.topTwoByImportance[0]
            : "the methodology panel"}{" "}
          for why.
        </p>
      )}

      <svg width={WIDTH} height={HEIGHT} role="img" aria-label={`Scatter of ${xFeature} vs ${yFeature} by team`}>
        {/* axes */}
        <line
          x1={PADDING.left}
          y1={PADDING.top + plotHeight}
          x2={PADDING.left + plotWidth}
          y2={PADDING.top + plotHeight}
          stroke="#d4d4d4"
        />
        <line x1={PADDING.left} y1={PADDING.top} x2={PADDING.left} y2={PADDING.top + plotHeight} stroke="#d4d4d4" />
        <text x={PADDING.left + plotWidth / 2} y={HEIGHT - 6} textAnchor="middle" className="fill-neutral-500 text-xs">
          {xFeature}
        </text>
        <text
          x={14}
          y={PADDING.top + plotHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${PADDING.top + plotHeight / 2})`}
          className="fill-neutral-500 text-xs"
        >
          {yFeature}
        </text>

        {points.map((p) => {
          const isSelected = p.team === selectedTeam;
          return (
            <circle
              key={p.team}
              cx={scaleX(p.x)}
              cy={scaleY(p.y)}
              r={scaleRadius(p.predictedWins)}
              fill={isSelected ? "#ea580c" : "#60a5fa"}
              fillOpacity={isSelected ? 0.95 : 0.6}
              stroke={isSelected ? "#9a3412" : "none"}
              strokeWidth={isSelected ? 2 : 0}
              onMouseEnter={() => setHovered(p.team)}
              onMouseLeave={() => setHovered((h) => (h === p.team ? null : h))}
            />
          );
        })}
      </svg>

      <div className="mt-1 h-5 text-xs text-neutral-600">
        {hoveredPoint &&
          `${hoveredPoint.team} — ${xFeature}: ${hoveredPoint.x.toFixed(2)}, ${yFeature}: ${hoveredPoint.y.toFixed(2)}, predicted wins: ${hoveredPoint.predictedWins.toFixed(1)}`}
      </div>
    </div>
  );
}

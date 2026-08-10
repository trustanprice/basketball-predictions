"use client";

import { useMemo, useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { getSafeTeamAccentColor } from "@/lib/teamColors";

const WIDTH = 560;
const HEIGHT = 380;
const PADDING = { top: 16, right: 16, bottom: 40, left: 56 };

const LINE_COLOR = "#f2ede0";
const INK_MUTED_COLOR = "#a89f8e";

/**
 * Scatter of two of the win model's top-importance features, one point per
 * team. Axes are chosen dynamically at render time, not hardcoded to any
 * specific feature names: walks metadata.top_feature_importance in rank
 * order and picks the first two features present (non-null) for every team
 * being plotted. Today that's usually NOT the literal top-2 by importance —
 * SOS (the #1 feature) is null for the entire current forecast season (a
 * real, pre-existing data-pipeline gap — see backend/AGENTS.md) — so this
 * shows an explicit on-chart caveat whenever the plotted axes aren't the true
 * top-2, rather than silently presenting them as if they were. That caveat
 * uses the "hollow/locked" treatment (border only, no fill) — it's describing
 * data that isn't available yet, not a status worth the accent color.
 *
 * Points are real click (and keyboard) targets, not hover-only — clicking or
 * pressing Enter/Space on one calls onSelectTeam, syncing back to the team
 * selector/forecast card above. The selected point is colored with that
 * team's own safe accent color (identity), not the site's amber (status) —
 * every other point stays neutral/muted so 30 simultaneous team colors don't
 * turn the chart into noise.
 */
export function FeatureScatterChart({
  predictions,
  metadata,
  selectedTeam,
  onSelectTeam,
}: {
  predictions: TeamPrediction[];
  metadata: ModelMetadata;
  selectedTeam?: string;
  onSelectTeam?: (team: string) => void;
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
      <div className="card--hollow text-sm text-ink-muted">
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
    <div className="card">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-headline text-xl">
          {xFeature} <span className="text-ink-muted">vs.</span> {yFeature}
        </h3>
        <span className="text-label text-[10px] text-ink-muted">Click a point to select · size = predicted wins</span>
      </div>

      {!axisChoice.isTrueTop2 && (
        <p className="prose-narrow mb-4 rounded-md border border-line/20 bg-transparent p-3 text-xs text-ink-muted">
          Showing <strong className="text-ink">{xFeature}</strong> vs.{" "}
          <strong className="text-ink">{yFeature}</strong>, not the true top-2 by importance (
          {axisChoice.topTwoByImportance.join(", ")}) — one or both aren&apos;t available for
          every team right now. See{" "}
          <strong className="text-ink">
            {metadata.feature_notes[axisChoice.topTwoByImportance[0]]
              ? axisChoice.topTwoByImportance[0]
              : "the methodology panel"}
          </strong>{" "}
          for why.
        </p>
      )}

      <svg width={WIDTH} height={HEIGHT} role="img" aria-label={`Scatter of ${xFeature} vs ${yFeature} by team`}>
        <line
          x1={PADDING.left}
          y1={PADDING.top + plotHeight}
          x2={PADDING.left + plotWidth}
          y2={PADDING.top + plotHeight}
          stroke={LINE_COLOR}
          strokeOpacity={0.15}
        />
        <line
          x1={PADDING.left}
          y1={PADDING.top}
          x2={PADDING.left}
          y2={PADDING.top + plotHeight}
          stroke={LINE_COLOR}
          strokeOpacity={0.15}
        />
        <text
          x={PADDING.left + plotWidth / 2}
          y={HEIGHT - 6}
          textAnchor="middle"
          fill={INK_MUTED_COLOR}
          fontFamily="var(--font-mono)"
          letterSpacing="0.05em"
          fontSize={10}
        >
          {xFeature.toUpperCase()}
        </text>
        <text
          x={14}
          y={PADDING.top + plotHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${PADDING.top + plotHeight / 2})`}
          fill={INK_MUTED_COLOR}
          fontFamily="var(--font-mono)"
          letterSpacing="0.05em"
          fontSize={10}
        >
          {yFeature.toUpperCase()}
        </text>

        {points.map((p) => {
          const isSelected = p.team === selectedTeam;
          const selectedFill = isSelected ? getSafeTeamAccentColor(p.team) : INK_MUTED_COLOR;
          return (
            <circle
              key={p.team}
              cx={scaleX(p.x)}
              cy={scaleY(p.y)}
              r={scaleRadius(p.predictedWins)}
              fill={selectedFill}
              fillOpacity={isSelected ? 1 : 0.35}
              stroke={isSelected ? selectedFill : "none"}
              strokeOpacity={0.3}
              strokeWidth={isSelected ? 5 : 0}
              className="cursor-pointer outline-none transition-[fill-opacity,stroke-width] duration-200 ease-out focus-visible:stroke-accent focus-visible:stroke-2"
              tabIndex={0}
              role="button"
              aria-label={`${p.team}: ${xFeature} ${p.x.toFixed(2)}, ${yFeature} ${p.y.toFixed(2)}, predicted wins ${p.predictedWins.toFixed(1)}`}
              aria-pressed={isSelected}
              onClick={() => onSelectTeam?.(p.team)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectTeam?.(p.team);
                }
              }}
              onMouseEnter={() => setHovered(p.team)}
              onMouseLeave={() => setHovered((h) => (h === p.team ? null : h))}
              onFocus={() => setHovered(p.team)}
              onBlur={() => setHovered((h) => (h === p.team ? null : h))}
            />
          );
        })}
      </svg>

      <div className="text-label mt-2 h-5 text-[11px] text-ink-muted">
        {hoveredPoint &&
          `${hoveredPoint.team} — ${xFeature}: ${hoveredPoint.x.toFixed(2)}, ${yFeature}: ${hoveredPoint.y.toFixed(2)}, PRED WINS: ${hoveredPoint.predictedWins.toFixed(1)}`}
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import type { ModelMetadata, TeamPrediction } from "@/lib/types";
import { getSafeTeamAccentColor } from "@/lib/teamColors";
import { teamLogoUrl } from "@/lib/teamIds";

const WIDTH = 560;
const HEIGHT = 380;
const PADDING = { top: 16, right: 16, bottom: 40, left: 56 };

const LINE_COLOR = "#f2ede0";
const INK_MUTED_COLOR = "#a89f8e";

// "Small, 24-32px" per spec: unselected logos sit at the low end so a cluster
// of teams plotted close together stays legible; the selected (or hovered)
// team gets the high end plus a colored halo behind it, and is always drawn
// last (SVG paints in DOM order — there's no z-index for siblings) so it
// sits on top of anything it overlaps rather than getting buried.
const LOGO_SIZE = 24;
const EMPHASIZED_LOGO_SIZE = 32;

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
 * Points are each team's real logo (cdn.nba.com), not a plain dot — falls
 * back to a colored dot (lib/teamColors.ts) for any team ID whose logo fails
 * to load, tracked per-team via each <image>'s onError. Real click (and
 * keyboard) targets, not hover-only — clicking or pressing Enter/Space on one
 * calls onSelectTeam, syncing back to the team selector/forecast card above.
 * The selected team's logo is drawn larger, at full opacity, on top of
 * everything else (last in paint order), with a colored halo behind it using
 * that team's own safe accent color (identity, not the site's amber status
 * color) — every other logo stays small and dimmed so a cluster of teams
 * plotted close together doesn't turn illegible.
 */
export function FeatureScatterChart({
  predictions,
  metadata,
  selectedTeam,
  onSelectTeam,
}: {
  predictions: TeamPrediction[];
  metadata: ModelMetadata;
  selectedTeam?: string | null;
  onSelectTeam?: (team: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [failedLogos, setFailedLogos] = useState<Set<string>>(new Set());

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

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const scaleX = (v: number) =>
    PADDING.left + (xMax === xMin ? plotWidth / 2 : ((v - xMin) / (xMax - xMin)) * plotWidth);
  const scaleY = (v: number) =>
    PADDING.top + plotHeight - (yMax === yMin ? plotHeight / 2 : ((v - yMin) / (yMax - yMin)) * plotHeight);

  const hoveredPoint = points.find((p) => p.team === hovered);
  // Emphasized (larger, full-opacity, drawn last so it's never buried under a
  // neighbor) team is whichever the user is actively interacting with —
  // hover takes priority for immediate feedback, falling back to the
  // sitewide selection.
  const emphasizedTeam = hovered ?? selectedTeam ?? null;
  // Draw order: emphasized team last (SVG has no z-index for siblings —
  // paint order is the only way to guarantee it sits on top of anything it
  // overlaps).
  const orderedPoints = [...points].sort((a, b) =>
    a.team === emphasizedTeam ? 1 : b.team === emphasizedTeam ? -1 : 0
  );

  return (
    <div className="card">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-headline text-xl">
          {xFeature} <span className="text-ink-muted">vs.</span> {yFeature}
        </h3>
        <span className="text-label text-[10px] text-ink-muted">Click a logo to select</span>
      </div>

      {!axisChoice.isTrueTop2 && (
        <p className="prose-narrow mb-4 rounded-md border border-line/20 bg-transparent p-3 text-xs text-ink-muted">
          We&apos;d rather plot <strong className="text-ink">{axisChoice.topTwoByImportance.join(" and ")}</strong>{" "}
          — the two features that actually matter most — but at least one of them isn&apos;t
          available for every team right now, so this chart shows{" "}
          <strong className="text-ink">{xFeature}</strong> vs.{" "}
          <strong className="text-ink">{yFeature}</strong> instead. See{" "}
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

        {orderedPoints.map((p) => {
          const isSelected = p.team === selectedTeam;
          const isEmphasized = p.team === emphasizedTeam;
          const cx = scaleX(p.x);
          const cy = scaleY(p.y);
          const size = isEmphasized ? EMPHASIZED_LOGO_SIZE : LOGO_SIZE;
          const half = size / 2;
          const accentColor = getSafeTeamAccentColor(p.team);
          const logoUrl = teamLogoUrl(p.team);
          const showFallbackDot = !logoUrl || failedLogos.has(p.team);

          return (
            <g
              key={p.team}
              className="cursor-pointer outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
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
            >
              {isSelected && (
                // Colored halo behind the selected team's logo — carries the
                // same "team identity color" cue the old plain-dot version
                // had, and helps the selected point read clearly even where
                // several logos cluster close together.
                <circle cx={cx} cy={cy} r={half + 6} fill={accentColor} fillOpacity={0.25} />
              )}
              {showFallbackDot ? (
                <circle
                  cx={cx}
                  cy={cy}
                  r={half}
                  fill={isEmphasized ? accentColor : INK_MUTED_COLOR}
                  fillOpacity={isEmphasized ? 1 : 0.45}
                  className="transition-[fill-opacity] duration-200 ease-out"
                />
              ) : (
                <image
                  href={logoUrl}
                  x={cx - half}
                  y={cy - half}
                  width={size}
                  height={size}
                  opacity={isEmphasized ? 1 : 0.55}
                  className="transition-opacity duration-200 ease-out"
                  onError={() => setFailedLogos((prev) => new Set(prev).add(p.team))}
                />
              )}
              {/* Larger invisible hit target — the visible logo/dot can be
                  smaller than a comfortable click/tap area. */}
              <circle cx={cx} cy={cy} r={Math.max(half, 16)} fill="transparent" />
            </g>
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

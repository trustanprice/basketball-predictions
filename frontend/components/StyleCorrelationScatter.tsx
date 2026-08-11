"use client";

import { useMemo, useState } from "react";
import type { CoachTeamSeason } from "@/lib/types";
import { getSafeTeamAccentColor } from "@/lib/teamColors";
import { useTeamTheme } from "./TeamThemeProvider";

const WIDTH = 560;
const HEIGHT = 340;
const PADDING = { top: 16, right: 16, bottom: 40, left: 56 };
const LINE_COLOR = "#f2ede0";
const INK_MUTED_COLOR = "#a89f8e";

type StyleMetric = "pace" | "ast_pct" | "three_pa_rate";

const METRIC_LABELS: Record<StyleMetric, string> = {
  pace: "Pace (possessions/48 min)",
  ast_pct: "Assist %",
  three_pa_rate: "3PA Rate",
};

/**
 * One dot per real coach-season: a team-style metric (pace / assist% / 3PA
 * rate — see backend/ratings/team_style.py) on the X axis, wins-above-
 * expectation on the Y axis. Explicitly a correlation/association view, not
 * a causal claim — the caption says so plainly, not just by omission, same
 * discipline as the predictions page's feature scatter and its dynamic
 * axis-availability caveat.
 *
 * "Opponent restricted-area shot rate" (mentioned as a candidate X-axis
 * metric) isn't wired in here yet — it would need aggregating every team-
 * season's defensive shot-heatmap cells (see TeamShotHeatmap.tsx), which
 * this project only fetches on demand for one team at a time today, not
 * pre-aggregated across history. Left as a real, named gap, not silently
 * omitted.
 */
export function StyleCorrelationScatter({ teamSeasons }: { teamSeasons: CoachTeamSeason[] }) {
  const { selectedTeam } = useTeamTheme();
  const [metric, setMetric] = useState<StyleMetric>("pace");
  const [hovered, setHovered] = useState<string | null>(null);

  const points = useMemo(
    () =>
      teamSeasons
        .filter((ts) => typeof ts[metric] === "number" && !Number.isNaN(ts[metric]))
        .map((ts) => ({
          key: `${ts.season}-${ts.team}`,
          team: ts.team,
          season: ts.season,
          coach: ts.coach,
          x: ts[metric] as number,
          y: ts.wins_above_expectation,
        })),
    [teamSeasons, metric]
  );

  if (points.length === 0) {
    return (
      <div className="card--hollow text-sm text-ink-muted">
        No team-style data available yet — run{" "}
        <code className="text-label text-[11px]">python -m backend.ratings.refresh_team_style</code>.
      </div>
    );
  }

  const xValues = points.map((p) => p.x);
  const yValues = points.map((p) => p.y);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const scaleX = (v: number) => PADDING.left + (xMax === xMin ? plotWidth / 2 : ((v - xMin) / (xMax - xMin)) * plotWidth);
  const scaleY = (v: number) =>
    PADDING.top + plotHeight - (yMax === yMin ? plotHeight / 2 : ((v - yMin) / (yMax - yMin)) * plotHeight);

  const hoveredPoint = points.find((p) => p.key === hovered);

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-headline text-xl">
          {METRIC_LABELS[metric]} <span className="text-ink-muted">vs.</span> Wins Above Expectation
        </h3>
        <div className="flex gap-1">
          {(Object.keys(METRIC_LABELS) as StyleMetric[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMetric(m)}
              aria-pressed={metric === m}
              className={`text-label rounded-md border px-2 py-1 text-[10px] transition-colors duration-200 ease-out ${
                metric === m ? "border-accent/40 text-ink" : "border-line/15 text-ink-muted hover:border-line/25"
              }`}
            >
              {m === "pace" ? "Pace" : m === "ast_pct" ? "AST%" : "3PA Rate"}
            </button>
          ))}
        </div>
      </div>

      <p className="prose-narrow mb-4 rounded-md border border-line/20 bg-transparent p-3 text-xs text-ink-muted">
        <strong className="text-ink">Correlation, not causation.</strong> This shows association
        only — a team playing at a certain pace or shot profile alongside over/under-performing
        its roster-talent-implied win% is not evidence that style caused the outcome. Sample size
        per point is one team-season; read trends cautiously.
      </p>

      <svg width={WIDTH} height={HEIGHT} role="img" aria-label={`Scatter of ${METRIC_LABELS[metric]} vs wins above expectation`}>
        <line x1={PADDING.left} y1={PADDING.top + plotHeight} x2={PADDING.left + plotWidth} y2={PADDING.top + plotHeight} stroke={LINE_COLOR} strokeOpacity={0.15} />
        <line x1={PADDING.left} y1={PADDING.top} x2={PADDING.left} y2={PADDING.top + plotHeight} stroke={LINE_COLOR} strokeOpacity={0.15} />
        {yMin < 0 && yMax > 0 && (
          <line
            x1={PADDING.left}
            y1={scaleY(0)}
            x2={PADDING.left + plotWidth}
            y2={scaleY(0)}
            stroke={LINE_COLOR}
            strokeOpacity={0.25}
            strokeDasharray="4 3"
          />
        )}
        <text x={PADDING.left + plotWidth / 2} y={HEIGHT - 6} textAnchor="middle" fill={INK_MUTED_COLOR} fontFamily="var(--font-mono)" letterSpacing="0.05em" fontSize={10}>
          {METRIC_LABELS[metric].toUpperCase()}
        </text>
        <text x={14} y={PADDING.top + plotHeight / 2} textAnchor="middle" transform={`rotate(-90, 14, ${PADDING.top + plotHeight / 2})`} fill={INK_MUTED_COLOR} fontFamily="var(--font-mono)" letterSpacing="0.05em" fontSize={10}>
          WAE
        </text>

        {points.map((p) => {
          const isHovered = p.key === hovered;
          const isSitewideSelection = p.team === selectedTeam;
          const isEmphasized = isHovered || isSitewideSelection;
          const color = isEmphasized ? getSafeTeamAccentColor(p.team) : INK_MUTED_COLOR;
          return (
            <circle
              key={p.key}
              cx={scaleX(p.x)}
              cy={scaleY(p.y)}
              r={isEmphasized ? 6 : 4}
              fill={color}
              fillOpacity={isEmphasized ? 1 : 0.4}
              className="cursor-pointer outline-none transition-[fill-opacity,r] duration-200 ease-out focus-visible:stroke-accent focus-visible:stroke-2"
              tabIndex={0}
              role="img"
              aria-label={`${p.team} ${p.season}, coach ${p.coach}: ${METRIC_LABELS[metric]} ${p.x.toFixed(2)}, WAE ${(p.y * 100).toFixed(1)}%`}
              onMouseEnter={() => setHovered(p.key)}
              onMouseLeave={() => setHovered((h) => (h === p.key ? null : h))}
              onFocus={() => setHovered(p.key)}
              onBlur={() => setHovered((h) => (h === p.key ? null : h))}
            />
          );
        })}
      </svg>

      <div className="text-label mt-2 h-5 text-[11px] text-ink-muted">
        {hoveredPoint &&
          `${hoveredPoint.team} ${hoveredPoint.season} (${hoveredPoint.coach}) — ${METRIC_LABELS[metric]}: ${hoveredPoint.x.toFixed(2)}, WAE: ${(hoveredPoint.y * 100).toFixed(1)}%`}
      </div>
    </div>
  );
}

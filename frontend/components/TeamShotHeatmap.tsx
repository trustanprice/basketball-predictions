"use client";

import { useEffect, useState } from "react";
import type { ShotHeatmap, ShotHeatmapCell } from "@/lib/types";

const TEAMS = [
  "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
  "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons",
  "Golden State Warriors", "Houston Rockets", "Indiana Pacers", "Los Angeles Clippers",
  "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat", "Milwaukee Bucks",
  "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks", "Oklahoma City Thunder",
  "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
  "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards",
];

const WIDTH = 260;
const HEIGHT = 280;
// Real half-court shot-chart coordinate bounds (LOC_X/LOC_Y, nba_api units —
// roughly feet x 10, hoop near the origin) — see backend/ratings/team_style.py.
const X_RANGE: [number, number] = [-250, 250];
const Y_RANGE: [number, number] = [-50, 470];

function scaleX(x: number) {
  return ((x - X_RANGE[0]) / (X_RANGE[1] - X_RANGE[0])) * WIDTH;
}
function scaleY(y: number) {
  // Flip: increasing LOC_Y (further from the hoop) should draw upward.
  return HEIGHT - ((y - Y_RANGE[0]) / (Y_RANGE[1] - Y_RANGE[0])) * HEIGHT;
}

function HalfCourtHeatmap({ title, cells, maxAttempts }: { title: string; cells: ShotHeatmapCell[]; maxAttempts: number }) {
  const cellSize = WIDTH / 25;
  return (
    <div>
      <p className="text-label mb-2 text-[11px] text-ink-muted">{title}</p>
      <svg width={WIDTH} height={HEIGHT} role="img" aria-label={`${title} shot heatmap`} className="rounded-md bg-page">
        {/* Hoop + restricted-area arc, orientation reference only */}
        <circle cx={scaleX(0)} cy={scaleY(0)} r={3} fill="none" stroke="#a89f8e" strokeOpacity={0.4} />
        {cells.map((c, i) => {
          const intensity = maxAttempts > 0 ? c.attempts / maxAttempts : 0;
          return (
            <rect
              key={i}
              x={scaleX(c.x) - cellSize / 2}
              y={scaleY(c.y) - cellSize / 2}
              width={cellSize}
              height={cellSize}
              fill="#e2933f"
              fillOpacity={Math.min(0.15 + intensity * 0.85, 1)}
            >
              <title>
                {c.attempts} attempts, {(c.fg_pct * 100).toFixed(0)}% made
              </title>
            </rect>
          );
        })}
      </svg>
    </div>
  );
}

/**
 * Real shot-location heatmaps for one team/season — the team's own offense
 * (its shots) and its defense (shots allowed, via ShotChartDetail's
 * opponent_team_id — see backend/live_client/endpoints/stats/shot_chart.py).
 * Fetched on demand through /api/shot-heatmap (a Next.js Route Handler
 * proxy, not lib/api.ts — this is the one view on the site that's
 * genuinely per-user-selection rather than knowable at request/build time,
 * see that route's own comment for why it still doesn't expose the backend
 * URL to the browser).
 */
export function TeamShotHeatmap({ defaultTeam, seasons }: { defaultTeam: string; seasons: string[] }) {
  const [team, setTeam] = useState(defaultTeam);
  const [season, setSeason] = useState(seasons[0] ?? "");
  const [data, setData] = useState<ShotHeatmap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!team || !season) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/shot-heatmap?team=${encodeURIComponent(team)}&season=${encodeURIComponent(season)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json();
      })
      .then((body: ShotHeatmap) => {
        if (!cancelled) setData(body);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load shot data for this team/season.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [team, season]);

  const maxAttempts = data
    ? Math.max(1, ...data.offense_cells.map((c) => c.attempts), ...data.defense_cells.map((c) => c.attempts))
    : 1;

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          className="text-label rounded-md border border-line/20 bg-card px-3 py-1.5 text-xs text-ink"
        >
          {TEAMS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={season}
          onChange={(e) => setSeason(e.target.value)}
          className="text-label rounded-md border border-line/20 bg-card px-3 py-1.5 text-xs text-ink"
        >
          {seasons.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {loading && <span className="text-label text-[11px] text-ink-muted">Loading real shot data…</span>}
      </div>

      {error && <div className="card--hollow text-sm text-ink-muted">{error}</div>}

      {data && !loading && (
        <>
          <div className="flex flex-wrap gap-8">
            <HalfCourtHeatmap title={`Offense (${data.n_offense_shots} shots)`} cells={data.offense_cells} maxAttempts={maxAttempts} />
            <HalfCourtHeatmap title={`Defense — shots allowed (${data.n_defense_shots} shots)`} cells={data.defense_cells} maxAttempts={maxAttempts} />
          </div>
          <p className="prose-narrow mt-4 text-xs text-ink-muted">
            Darker cells = more shot attempts from that spot on the floor. Real logged shot
            locations for {data.team}, {data.season} — not an illustrative diagram.
          </p>
        </>
      )}
    </div>
  );
}

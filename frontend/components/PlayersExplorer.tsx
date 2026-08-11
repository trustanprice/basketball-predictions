"use client";

import { useState } from "react";
import type { RatingBreakdown } from "@/lib/types";
import { getSafeTeamAccentColor } from "@/lib/teamColors";
import { RatingBreakdownCard } from "./RatingBreakdownCard";
import { SectionHeading } from "./SectionHeading";
import { useTeamTheme } from "./TeamThemeProvider";

type TabId = "offense" | "defense" | "projected-offense" | "projected-defense";

const SHOW_COUNTS = [5, 10, 25, 50];

export interface ProjectedLeaders {
  offense: RatingBreakdown[];
  defense: RatingBreakdown[];
  note: string;
}

/**
 * Client island for the players page: tab panels (Offense, Defense, and —
 * once backend/ratings/refresh_player_projections.py has run — Projected
 * Offense/Defense) sharing one "show top N" control, instead of separate
 * always-visible sections. Tabs, not routes (/players/offense etc.): one
 * server-side fetch already brings back every list together, and a tab
 * switch is a pure client-state toggle rather than a full navigation — see
 * frontend/AGENTS.md.
 *
 * `projected` is optional and renders no tabs for it when null — that
 * pipeline depends on a live current-roster fetch that isn't always
 * available in every environment; a missing projection is an expected
 * state, not an error, same as the players page's own top-level "not
 * available yet."
 */
export function PlayersExplorer({
  offense,
  defense,
  projected,
}: {
  offense: RatingBreakdown[];
  defense: RatingBreakdown[];
  projected: ProjectedLeaders | null;
}) {
  const { selectedTeam } = useTeamTheme();
  const teamColor = selectedTeam ? getSafeTeamAccentColor(selectedTeam) : undefined;
  const [tab, setTab] = useState<TabId>("offense");
  const [showCount, setShowCount] = useState(5);

  const tabs: { id: TabId; number: string; label: string; list: RatingBreakdown[]; isProjected?: boolean }[] = [
    { id: "offense", number: "01", label: "Offense", list: offense },
    { id: "defense", number: "02", label: "Defense", list: defense },
    ...(projected
      ? [
          { id: "projected-offense" as TabId, number: "03", label: "Projected Offense", list: projected.offense, isProjected: true },
          { id: "projected-defense" as TabId, number: "04", label: "Projected Defense", list: projected.defense, isProjected: true },
        ]
      : []),
  ];
  const active = tabs.find((t) => t.id === tab) ?? tabs[0];
  const visible = active.list.slice(0, showCount);

  return (
    <div>
      <div role="tablist" aria-label="Player rankings view" className="mb-8 flex flex-wrap gap-1 border-b border-line/10">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={t.id === active.id}
            onClick={() => setTab(t.id)}
            style={t.id === active.id ? { borderColor: teamColor ?? "var(--color-accent)" } : undefined}
            className={`text-label -mb-px border-b-2 px-4 py-2.5 text-xs transition-colors duration-200 ease-out focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              t.id === active.id
                ? "text-ink"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <SectionHeading number={active.number} id={active.id} title={active.label} />

      {active.isProjected && projected && (
        <p className="prose-narrow mb-6 rounded-md border border-accent/30 bg-transparent p-4 text-sm text-ink-muted">
          {projected.note}
        </p>
      )}

      <div className="mb-5 flex items-center gap-2">
        <span className="text-label text-[11px] text-ink-muted">Show</span>
        {SHOW_COUNTS.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setShowCount(n)}
            aria-pressed={showCount === n}
            style={showCount === n ? { borderColor: teamColor ? `${teamColor}66` : undefined } : undefined}
            className={`text-label rounded-md border px-2.5 py-1 text-[11px] transition-colors duration-200 ease-out focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              showCount === n
                ? teamColor ? "text-ink" : "border-accent/40 text-ink"
                : "border-line/15 text-ink-muted hover:border-line/25"
            }`}
          >
            Top {n}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="card--hollow text-sm text-ink-muted">Nothing to show for this view yet.</div>
      ) : (
        <div className="space-y-3">
          {visible.map((b, i) => (
            <RatingBreakdownCard key={b.subject_id} rank={i + 1} breakdown={b} />
          ))}
        </div>
      )}
    </div>
  );
}

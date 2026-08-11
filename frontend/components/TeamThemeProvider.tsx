"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getSiteThemeOverrides } from "@/lib/teamColors";

const STORAGE_KEY = "selectedTeam";

// The three globals.css tokens this provider is allowed to override. Kept as
// a single list so the "apply" and "clear" paths can't drift out of sync —
// see the effect below.
const OVERRIDABLE_VARS = ["--color-page", "--color-card", "--color-accent"] as const;

interface TeamThemeContextValue {
  selectedTeam: string | null;
  setSelectedTeam: (team: string | null) => void;
}

const TeamThemeContext = createContext<TeamThemeContextValue | undefined>(undefined);

/**
 * Site-wide selected-team state — PURELY a visual choice. This is the one
 * thing that changed here: selectedTeam used to double as "which team's data
 * is on screen" on the predictions page; it no longer drives what any page
 * displays, only how the whole site is recolored (see the effect below).
 * PredictionsExplorer.tsx has its own separate local state for "which
 * forecast is showing" now — the two are intentionally independent, so a
 * user can theme the site Cavaliers while viewing the Lakers' forecast.
 *
 * Persisted to localStorage so the selection survives navigation and
 * reloads. Starts at null (no team, the default amber/charcoal theme)
 * rather than defaulting to some team — read from localStorage only after
 * mount (useEffect, not the useState initializer) so server and first
 * client render always agree on null, avoiding a hydration mismatch; the
 * real value (and the recolor it triggers) applies a moment later.
 *
 * The recolor itself: whenever selectedTeam changes, getSiteThemeOverrides
 * (lib/teamColors.ts) computes a contrast-checked {page, card, accent} for
 * that team and this effect writes them as inline custom-property overrides
 * on <html>. Because globals.css's body/.card/.text-accent/etc. already
 * reference var(--color-page)/var(--color-card)/var(--color-accent), that's
 * the entire mechanism — no page or component needs to know theming exists.
 * Only those three tokens are ever touched: --color-positive (green,
 * live/validated) and --color-line (the hollow/locked-card border, and
 * every other card's border) are never in OVERRIDABLE_VARS, so status
 * meaning stays legible and distinct from team identity no matter which
 * team is selected.
 */
export function TeamThemeProvider({ children }: { children: ReactNode }) {
  const [selectedTeam, setSelectedTeamState] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setSelectedTeamState(stored);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const overrides = getSiteThemeOverrides(selectedTeam);
    if (!overrides) {
      OVERRIDABLE_VARS.forEach((name) => root.style.removeProperty(name));
      return;
    }
    root.style.setProperty("--color-page", overrides.page);
    root.style.setProperty("--color-card", overrides.card);
    root.style.setProperty("--color-accent", overrides.accent);
  }, [selectedTeam]);

  const setSelectedTeam = (team: string | null) => {
    setSelectedTeamState(team);
    if (team) {
      window.localStorage.setItem(STORAGE_KEY, team);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  };

  return (
    <TeamThemeContext.Provider value={{ selectedTeam, setSelectedTeam }}>{children}</TeamThemeContext.Provider>
  );
}

export function useTeamTheme(): TeamThemeContextValue {
  const ctx = useContext(TeamThemeContext);
  if (!ctx) throw new Error("useTeamTheme must be used within a TeamThemeProvider");
  return ctx;
}

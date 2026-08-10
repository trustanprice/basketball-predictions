"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "selectedTeam";

interface TeamThemeContextValue {
  selectedTeam: string | null;
  setSelectedTeam: (team: string | null) => void;
}

const TeamThemeContext = createContext<TeamThemeContextValue | undefined>(undefined);

/**
 * Site-wide selected-team state — drives the nav's team selector
 * (components/NavTeamSelector.tsx) and whatever team-color theming a given
 * page chooses to apply. Persisted to localStorage so the selection survives
 * navigation and reloads. Starts at null (no team, the neutral amber-only
 * theme) rather than defaulting to some team — read from localStorage only
 * after mount (useEffect, not the useState initializer) so server and first
 * client render always agree on null, avoiding a hydration mismatch; the
 * real value applies a moment later.
 */
export function TeamThemeProvider({ children }: { children: ReactNode }) {
  const [selectedTeam, setSelectedTeamState] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setSelectedTeamState(stored);
  }, []);

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

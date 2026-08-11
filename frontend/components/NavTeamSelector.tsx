"use client";

import { useEffect, useId, useRef, useState } from "react";
import { getTeamColors, isTextSafe, TEAM_COLORS } from "@/lib/teamColors";
import { useTeamTheme } from "./TeamThemeProvider";

const ALL_TEAMS = Object.keys(TEAM_COLORS).sort();

/**
 * The global site-theme picker: lives in the nav (available on every page,
 * see TeamThemeProvider/layout.tsx) — a compact button showing the current
 * selection (name + color dot) that opens a scrollable dropdown of all 30
 * teams. Picking a team here recolors the whole site (TeamThemeProvider);
 * it does NOT change what data any page shows — each page's own team
 * picker (e.g. PredictionsExplorer's dropdown) is a separate, independent
 * selection. Labeled "Site Theme" below specifically so that's not
 * ambiguous with a data filter.
 *
 * Not built on the shared Popover component: Popover has no "close on
 * selecting something inside it" hook, which a persistent global control
 * needs (its existing uses are all read-only info popovers, fine to leave
 * open until Escape/click-outside) — a small self-contained open/close
 * mirrors the same interaction (Escape, click-outside) but also closes
 * immediately on selection.
 */
export function NavTeamSelector() {
  const { selectedTeam, setSelectedTeam } = useTeamTheme();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [open]);

  const buttonPrimary = selectedTeam ? getTeamColors(selectedTeam).primary : undefined;
  const buttonTextColor = buttonPrimary && isTextSafe(buttonPrimary) ? buttonPrimary : undefined;

  return (
    <div ref={containerRef} className="relative ml-auto">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        title="Site color theme — doesn't change what data is shown on any page"
        className="text-label flex items-center gap-2 rounded-md border border-line/15 bg-card px-3 py-1.5 text-[11px] text-ink transition-colors duration-200 ease-out hover:border-line/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <span
          aria-hidden
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: buttonPrimary ?? "var(--color-ink-muted)" }}
        />
        <span style={buttonTextColor ? { color: buttonTextColor } : undefined}>
          {selectedTeam ? `Theme: ${selectedTeam}` : "Site Theme"}
        </span>
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-modal="false"
          className="card animate-popover-in absolute right-0 top-full z-50 mt-2 max-h-80 w-64 overflow-y-auto text-sm shadow-[0_8px_30px_rgba(0,0,0,0.4)]"
        >
          <p className="text-label mb-2 px-1 text-[10px] text-ink-muted">
            Recolors the whole site — doesn&apos;t change any page&apos;s data
          </p>
          {selectedTeam && (
            <button
              type="button"
              onClick={() => {
                setSelectedTeam(null);
                setOpen(false);
              }}
              className="text-label mb-2 block w-full rounded-md border border-line/10 px-3 py-2 text-left text-[11px] text-ink-muted transition-colors duration-200 ease-out hover:border-line/20"
            >
              Clear selection
            </button>
          )}
          <div className="space-y-1">
            {ALL_TEAMS.map((team) => {
              const { primary } = getTeamColors(team);
              const textColor = isTextSafe(primary) ? primary : undefined;
              const isSelected = team === selectedTeam;
              return (
                <button
                  key={team}
                  type="button"
                  onClick={() => {
                    setSelectedTeam(team);
                    setOpen(false);
                  }}
                  className={`text-label flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-[11px] transition-colors duration-200 ease-out ${
                    isSelected ? "border-accent/40 bg-page/60" : "border-transparent hover:border-line/15"
                  }`}
                >
                  <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: primary }} />
                  <span className="truncate" style={textColor ? { color: textColor } : undefined}>
                    {team}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

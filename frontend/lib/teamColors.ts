/**
 * Single source of truth for per-team color theming. Team color is IDENTITY,
 * not status — never reuse these for the amber (section/key-stat/button),
 * green (positive/validated), or hollow (locked/future) status meanings from
 * globals.css. Team colors apply to team-specific chrome only: a border/dot
 * next to a team's row or card, the selected team's scatter-chart point, a
 * team-specific section underline.
 *
 * Two colors per team (primary, secondary) even where NBA branding lists more
 * (Denver, Minnesota) — first two only, for consistency across all 30.
 */

export interface TeamColorPair {
  primary: string;
  secondary: string;
}

export const TEAM_COLORS: Record<string, TeamColorPair> = {
  "Atlanta Hawks": { primary: "#C8102E", secondary: "#FDB927" },
  "Boston Celtics": { primary: "#007A33", secondary: "#BA9653" },
  "Brooklyn Nets": { primary: "#000000", secondary: "#FFFFFF" },
  "Charlotte Hornets": { primary: "#1D1160", secondary: "#00788C" },
  "Chicago Bulls": { primary: "#CE1141", secondary: "#000000" },
  "Cleveland Cavaliers": { primary: "#860038", secondary: "#041E42" },
  "Dallas Mavericks": { primary: "#0053BC", secondary: "#00285E" },
  "Denver Nuggets": { primary: "#0E2240", secondary: "#FEC524" },
  "Detroit Pistons": { primary: "#C8102E", secondary: "#1D42BA" },
  "Golden State Warriors": { primary: "#1D428A", secondary: "#FFC72C" },
  "Houston Rockets": { primary: "#CE1141", secondary: "#000000" },
  "Indiana Pacers": { primary: "#002D62", secondary: "#FDBB30" },
  "Los Angeles Clippers": { primary: "#0C2340", secondary: "#C8102E" },
  "Los Angeles Lakers": { primary: "#552583", secondary: "#FDB927" },
  "Memphis Grizzlies": { primary: "#5D76A9", secondary: "#12173F" },
  "Miami Heat": { primary: "#98002E", secondary: "#F9A01B" },
  "Milwaukee Bucks": { primary: "#00471B", secondary: "#EEE1C6" },
  "Minnesota Timberwolves": { primary: "#0C2340", secondary: "#236192" },
  "New Orleans Pelicans": { primary: "#0C2340", secondary: "#C8102E" },
  "New York Knicks": { primary: "#006BB6", secondary: "#F58426" },
  "Oklahoma City Thunder": { primary: "#007AC1", secondary: "#002D62" },
  "Orlando Magic": { primary: "#0077C0", secondary: "#C4CED4" },
  "Philadelphia 76ers": { primary: "#006BB6", secondary: "#ED174C" },
  "Phoenix Suns": { primary: "#1D1160", secondary: "#E56020" },
  "Portland Trail Blazers": { primary: "#E03A3E", secondary: "#000000" },
  "Sacramento Kings": { primary: "#5A2D81", secondary: "#63727A" },
  "San Antonio Spurs": { primary: "#C4CED4", secondary: "#000000" },
  "Toronto Raptors": { primary: "#CE1141", secondary: "#000000" },
  "Utah Jazz": { primary: "#002B5C", secondary: "#00471B" },
  "Washington Wizards": { primary: "#002B49", secondary: "#E31837" },
};

// Matches --color-ink-muted in globals.css — the neutral fallback when a team
// name isn't in the map, or when neither of its colors is safe as text.
const NEUTRAL_FALLBACK = "#a89f8e";

// Matches --color-page in globals.css. Hardcoded here (not imported — this
// module has no CSS access) rather than left implicit, so the contrast math
// below is self-documenting about what it's actually checking against.
const PAGE_BACKGROUND = "#1b1815";

const MIN_TEXT_CONTRAST = 4.5; // WCAG AA, normal text

export function getTeamColors(team: string): TeamColorPair {
  return TEAM_COLORS[team] ?? { primary: NEUTRAL_FALLBACK, secondary: NEUTRAL_FALLBACK };
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const value = parseInt(clean, 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (c: number) => {
    const cs = c / 255;
    return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio between two hex colors, 1 (identical) to 21 (black/white). */
export function contrastRatio(hexA: string, hexB: string): number {
  const lA = relativeLuminance(hexToRgb(hexA));
  const lB = relativeLuminance(hexToRgb(hexB));
  const lighter = Math.max(lA, lB);
  const darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Whether `hex` is safe to render as readable text/fill against the page's
 * charcoal background. Most NBA primary colors are saturated-but-dark (built
 * for white jerseys and light backgrounds, not a dark page) — expect this to
 * fail for the large majority of primaries; that's real, measured contrast
 * math, not a bug. 29 of 30 teams' primary color fails this check; only ~12
 * of 30 secondaries pass. Use getSafeTeamAccentColor() for the fallback
 * chain rather than assuming primary is usable.
 */
export function isTextSafe(hex: string): boolean {
  return contrastRatio(hex, PAGE_BACKGROUND) >= MIN_TEXT_CONTRAST;
}

/**
 * Best team color for anywhere it needs to be READ (text, a filled shape
 * that must stay visible/legible) — primary, else secondary, else a neutral
 * fallback if neither clears contrast. For borders/dots/underlines, where
 * even a low-contrast color is still a legible accent against its shape and
 * position (not read as text), use raw getTeamColors().primary/.secondary
 * directly instead — don't gate those through this function.
 */
export function getSafeTeamAccentColor(team: string): string {
  const { primary, secondary } = getTeamColors(team);
  if (isTextSafe(primary)) return primary;
  if (isTextSafe(secondary)) return secondary;
  return NEUTRAL_FALLBACK;
}

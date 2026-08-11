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
// below is self-documenting about what it's actually checking against. This
// is the *default* background isTextSafe/getSafeTeamAccentColor check
// against when no background is given — callers operating inside an active
// sitewide team wash (see getSiteThemeOverrides below) pass the live washed
// background instead, since that's what the color will actually sit on.
const PAGE_BACKGROUND = "#1b1815";
const CARD_BACKGROUND = "#252019";
const INK = "#f2ede0"; // matches --color-ink — used as the lightening target in lightenUntilSafe
const INK_MUTED = "#a89f8e"; // dimmest text color in normal use — the real worst case to protect

const MIN_TEXT_CONTRAST = 4.5; // WCAG AA, normal text

export function getTeamColors(team: string): TeamColorPair {
  return TEAM_COLORS[team] ?? { primary: NEUTRAL_FALLBACK, secondary: NEUTRAL_FALLBACK };
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const value = parseInt(clean, 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  const toHex = (c: number) => Math.max(0, Math.min(255, Math.round(c))).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
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
 * Whether `hex` is safe to render as readable text/fill against `background`
 * (defaults to the static page charcoal, for existing per-row/per-point
 * decorative call sites that always sit on the plain page). Most NBA primary
 * colors are saturated-but-dark (built for white jerseys and light
 * backgrounds, not a dark page) — expect this to fail for the large majority
 * of primaries; that's real, measured contrast math, not a bug. 29 of 30
 * teams' primary color fails this check against the default background; only
 * ~12 of 30 secondaries pass. Use getSafeTeamAccentColor() for the fallback
 * chain rather than assuming primary is usable.
 */
export function isTextSafe(hex: string, background: string = PAGE_BACKGROUND): boolean {
  return contrastRatio(hex, background) >= MIN_TEXT_CONTRAST;
}

/**
 * Best team color for anywhere it needs to be READ (text, a filled shape
 * that must stay visible/legible) against `background` (defaults to the
 * static page charcoal) — primary, else secondary, else a neutral fallback
 * if neither clears contrast. For borders/dots/underlines, where even a
 * low-contrast color is still a legible accent against its shape and
 * position (not read as text), use raw getTeamColors().primary/.secondary
 * directly instead — don't gate those through this function.
 */
export function getSafeTeamAccentColor(team: string, background: string = PAGE_BACKGROUND): string {
  const { primary, secondary } = getTeamColors(team);
  if (isTextSafe(primary, background)) return primary;
  if (isTextSafe(secondary, background)) return secondary;
  return NEUTRAL_FALLBACK;
}

function mixHex(hexA: string, hexB: string, weightA: number): string {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const t = Math.max(0, Math.min(1, weightA));
  return rgbToHex([a[0] * t + b[0] * (1 - t), a[1] * t + b[1] * (1 - t), a[2] * t + b[2] * (1 - t)]);
}

/**
 * The largest team-color wash we can mix into `baseHex` while keeping
 * INK_MUTED (the dimmest text color still in normal use, e.g. small labels)
 * readable on top of it at WCAG AA. Scans downward from `maxPct` in 1%
 * steps and returns the first (= most saturated) mix that still clears
 * MIN_TEXT_CONTRAST — computed per-team rather than a single hardcoded
 * percentage, because team colors span a huge lightness range (Nets black to
 * Spurs silver to Bucks' cream secondary) and a fixed percentage would be
 * either invisible on the dark teams or unreadable on the light ones. This
 * is why near-black/near-white teams get a visibly milder wash than
 * saturated mid-tone teams (Cavs wine, Celtics green) automatically, with
 * no per-team special-casing: their raw color already fails contrast at a
 * lower mix percentage, so the search stops sooner.
 */
function largestSafeWash(teamHex: string, baseHex: string, maxPct: number): string {
  for (let pct = maxPct; pct >= 0; pct -= 0.01) {
    const mixed = mixHex(teamHex, baseHex, pct);
    if (contrastRatio(mixed, INK_MUTED) >= MIN_TEXT_CONTRAST) return mixed;
  }
  return baseHex;
}

/**
 * Lightens `teamHex` toward INK just enough to clear MIN_TEXT_CONTRAST
 * against EVERY background in `backgrounds` (the accent renders on both the
 * washed page and the washed card, and those are two different colors — see
 * getSiteThemeOverrides) — the sitewide accent's own fallback, used only
 * when neither the team's primary nor secondary is readable as-is (about
 * half the league: primaries are built for white jerseys, not a dark page,
 * and plenty of secondaries are just as dark — Cavaliers wine-on-navy,
 * Mavericks blue-on-navy). Rather than dropping to the generic neutral gray
 * getSafeTeamAccentColor()'s normal fallback chain uses (right for small
 * decorative dots/borders, where "hey, unusual color" would look odd once
 * washed out), this keeps the accent visibly *that team's* color family —
 * scans upward from pure primary so it returns the least amount of
 * lightening that still passes, i.e. the most saturated safe variant.
 */
function lightenUntilSafe(teamHex: string, backgrounds: string[]): string {
  for (let pct = 0; pct <= 1; pct += 0.02) {
    const lightened = mixHex(INK, teamHex, pct);
    if (backgrounds.every((bg) => contrastRatio(lightened, bg) >= MIN_TEXT_CONTRAST)) return lightened;
  }
  return INK;
}

export interface SiteThemeOverrides {
  page: string;
  card: string;
  accent: string;
}

/**
 * The full sitewide recolor for `team`: tinted page/card backgrounds plus a
 * contrast-safe accent, all derived from the same primary color so the whole
 * UI reads as one coherent team palette rather than several colors picked
 * independently. Backgrounds are capped lower than the accent's own
 * contrast requirement (30%/38% max wash vs. a full readable-text
 * threshold) — they sit *behind* body text, not as the text itself, so the
 * binding constraint is "ink-muted text stays legible on top," computed
 * per-team by largestSafeWash rather than assumed. The accent is checked
 * against the *already-washed* page color (not the static default) so the
 * existing bg-accent + text-page button pairing (see app/page.tsx) stays
 * guaranteed readable even once the page background itself has shifted. If
 * neither raw primary nor secondary clears that bar (roughly half the
 * league — see lightenUntilSafe), the accent is a lightened variant of the
 * team's own primary rather than getSafeTeamAccentColor()'s usual neutral-
 * gray fallback: this is the one color meant to visibly carry team identity
 * everywhere on the page, so it should never go generic.
 * Deliberately does not touch --color-positive (green, "live/validated") or
 * --color-line (the hollow/locked-card border) — those stay fixed regardless
 * of team so status meaning never gets swallowed by team identity.
 */
export function getSiteThemeOverrides(team: string | null): SiteThemeOverrides | null {
  if (!team) return null;
  const { primary, secondary } = getTeamColors(team);
  const page = largestSafeWash(primary, PAGE_BACKGROUND, 0.3);
  const card = largestSafeWash(primary, CARD_BACKGROUND, 0.38);
  const accent =
    isTextSafe(primary, page) && isTextSafe(primary, card)
      ? primary
      : isTextSafe(secondary, page) && isTextSafe(secondary, card)
        ? secondary
        : lightenUntilSafe(primary, [page, card]);
  return { page, card, accent };
}

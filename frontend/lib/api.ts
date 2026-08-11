import type {
  CoachCareerSummary,
  CoachTeamSeason,
  PlayerPowerRankings,
  PlayerProjectedLeaders,
  TeamPrediction,
} from "./types";

/**
 * All data fetching happens server-side (Server Components), so this reads a
 * plain (non-NEXT_PUBLIC_) env var — nothing here ever runs in the browser.
 * See frontend/AGENTS.md.
 */
const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    // Matches the backend's own staleness bound for anything that isn't a
    // per-request computation — see backend/AGENTS.md's refresh strategy.
    next: { revalidate: 3600 },
  });
  if (!res.ok) {
    throw new Error(`GET ${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getPredictions(): Promise<TeamPrediction[]> {
  return apiFetch<TeamPrediction[]>("/api/win-model/predictions");
}

export async function getMethodology() {
  return apiFetch<import("./types").ModelMetadata>("/api/win-model/methodology");
}

/**
 * Player power rankings depend on the API's background refresh loop having
 * completed at least once (see backend/AGENTS.md) — on a fresh deploy, or if
 * NBA.com is unreachable, this is a genuine "not yet available" state, not a
 * bug. Returns null instead of throwing so the page can render that state
 * without generic error-boundary machinery.
 *
 * Fetches at the API's max `n` (50) in this one server-side call; the
 * players page's "show more" control slices the already-fetched list
 * client-side rather than re-fetching per click — no client-side network
 * calls, per this file's own fetch-is-server-side convention.
 */
export async function getPlayerPowerRankings(): Promise<PlayerPowerRankings | null> {
  const res = await fetch(`${API_BASE_URL}/api/players/power-rankings?n=50`, {
    next: { revalidate: 3600 },
  });
  if (res.status === 503) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`GET /api/players/power-rankings -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<PlayerPowerRankings>;
}

/**
 * A PRESEASON PROJECTION (see PlayerProjectedLeaders.note) — depends on the
 * same kind of background refresh as power rankings, plus a live current-
 * roster fetch, so "not available yet" (503) is an expected state here too,
 * not a bug. Returns null rather than throwing, same as getPlayerPowerRankings.
 */
export async function getPlayerProjectedLeaders(): Promise<PlayerProjectedLeaders | null> {
  const res = await fetch(`${API_BASE_URL}/api/players/projected-leaders?n=50`, {
    next: { revalidate: 3600 },
  });
  if (res.status === 503) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`GET /api/players/projected-leaders -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<PlayerProjectedLeaders>;
}

export async function getCoachTeamSeasons(): Promise<CoachTeamSeason[]> {
  return apiFetch<CoachTeamSeason[]>("/api/coaches/wins-above-expectation");
}

export async function getCoachCareerSummary(): Promise<CoachCareerSummary[]> {
  return apiFetch<CoachCareerSummary[]>("/api/coaches/career-summary");
}

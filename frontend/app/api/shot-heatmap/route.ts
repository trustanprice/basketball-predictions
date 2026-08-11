import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

/**
 * The one exception to "all data fetching is server-side, no client-side
 * fetch" (see frontend/AGENTS.md): the shot heatmap is genuinely on-demand,
 * per user-selected team — it can't be prefetched for all 30 teams at
 * build/request time the way every other page's data is. A client
 * component still can't read API_BASE_URL directly (it's a plain, non-
 * NEXT_PUBLIC_ env var, deliberately hidden from the browser bundle — see
 * lib/api.ts), so this Route Handler is the server-side proxy that lets a
 * client component ask for one team's heatmap without exposing the backend
 * URL to the browser.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const team = searchParams.get("team");
  const season = searchParams.get("season");
  if (!team || !season) {
    return NextResponse.json({ detail: "team and season are required" }, { status: 400 });
  }

  const res = await fetch(
    `${API_BASE_URL}/api/coaches/shot-heatmap?team=${encodeURIComponent(team)}&season=${encodeURIComponent(season)}`,
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

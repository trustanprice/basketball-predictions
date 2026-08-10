/**
 * NBA.com's own CDN, no API key needed — confirmed working directly:
 * https://cdn.nba.com/headshots/nba/latest/1040x760/{PLAYER_ID}.png.
 * Some player IDs (recent draftees, players with no current headshot on
 * file) 404 — callers must handle that themselves (see
 * components/PlayerHeadshot.tsx), not assume every ID resolves.
 */
export function headshotUrl(playerId: number | string): string {
  return `https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`;
}

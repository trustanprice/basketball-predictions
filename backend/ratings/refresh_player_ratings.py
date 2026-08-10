"""backend/ratings/refresh_player_ratings.py

Scheduled refresh job: fetches live_client data, computes the player power
rankings, and writes them to a local JSON store that backend/api/ reads from.

This is the *only* place backend.ratings.player_power_rankings' live_client
dependency actually gets exercised. The API never calls live_client directly —
see backend/AGENTS.md's "Player ratings: refresh strategy" section for why
(NBA.com rate limits + request latency make a live call per API request wrong
for a request-serving API) and how this gets scheduled in production: an
in-process background loop in backend/api/main.py calls is_stale()/run_refresh()
on the *same* running web service, deliberately not a separate host-level cron
service — see that AGENTS.md section for why (filesystem isolation between
separate services on typical hosting tiers).

Run manually:  python -m backend.ratings.refresh_player_ratings
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.live_client.client import NBAStatsClient
from backend.live_client.endpoints.stats.advanced_metrics import PlayerAdvancedStats
from backend.live_client.endpoints.stats.season_totals import PlayerSeasonTotals

from .player_power_rankings import build_player_table, top_defensive_players, top_offensive_players

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "player_power_rankings.json"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60

METHODOLOGY_NOTE = (
    "Offense: True Shooting % + usage-adjusted scoring + AST% (playmaking) + "
    "TOV% (turnover rate, penalized). Defense: steal+block rate per 36 min + "
    "defensive rebound % + on-court defensive rating (penalized). 'Defended FG%' "
    "and a true on/off defensive rating split are not included — they require "
    "NBA.com tracking/matchup endpoints (leaguedashptdefend, "
    "teamplayeronoffdetails) that backend/live_client/ doesn't fetch yet. "
    "Every score is a z-scored, weighted composite over players meeting a "
    "minimum-playing-time filter — see backend/ratings/player_power_rankings.py."
)


def current_nba_season() -> str:
    """NBA seasons run Oct-June. Returns e.g. "2025-26" for any date from Oct
    2025 through Sep 2026. A simple, documented convention — not fetched from
    anywhere, since NBA.com doesn't expose "the current season" as its own value."""
    now = datetime.now(timezone.utc)
    start_year = now.year if now.month >= 10 else now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def is_stale(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> bool:
    """True if OUTPUT_FILE doesn't exist yet, is unreadable, or is older than
    max_age_seconds. Lets a caller (the API's background loop) decide whether a
    refresh is actually due, rather than unconditionally fetching."""
    if not OUTPUT_FILE.exists():
        return True
    try:
        payload = json.loads(OUTPUT_FILE.read_text())
        generated_at = datetime.fromisoformat(payload["generated_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return True
    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age_seconds > max_age_seconds


def run_refresh(season: str | None = None, top_n: int = 5, write_output: bool = True) -> dict:
    """Fetch this season's player data and compute top_n offense/defense rankings.

    Returns the same dict that gets written to OUTPUT_FILE, so callers (tests,
    an ad-hoc script) can inspect it without touching disk.
    """
    season = season or current_nba_season()

    with NBAStatsClient() as client:
        season_totals = PlayerSeasonTotals(season=season, per_mode="PerGame", client=client).fetch().to_dataframe()
        advanced_stats = PlayerAdvancedStats(season=season, client=client).fetch().to_dataframe()

    player_table = build_player_table(season_totals, advanced_stats)
    offense = [b.to_dict() for b in top_offensive_players(player_table, n=top_n)]
    defense = [b.to_dict() for b in top_defensive_players(player_table, n=top_n)]

    payload = {
        "season": season,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology_note": METHODOLOGY_NOTE,
        "n_qualified_players": int(len(player_table)),
        "offense": offense,
        "defense": defense,
    }

    if write_output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2, default=str))

    return payload


if __name__ == "__main__":
    result = run_refresh()
    print(f"Refreshed player power rankings for {result['season']} "
          f"({result['n_qualified_players']} qualified players)")
    print(f"Wrote {OUTPUT_FILE}")

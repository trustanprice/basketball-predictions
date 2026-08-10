"""backend/ratings/refresh_team_style.py

Scheduled refresh job for the coaching page's team style fingerprint
(pace, assist rate, 3PA rate) — one row per (Season, Team), covering the
same historical range coaching_eval.py's wins-above-expectation already
does, so every real coach-season can show style context alongside WAE.

Historical, not just current season: unlike refresh_player_projections.py
(which only needs *current* rosters), team style needs to cover every
season coaching_eval tracks (see backend/win_model's master_df) to sit
alongside real historical WAE data, not just the latest season.

Cheap regardless: two league-wide calls per season (TeamSeasonStats +
TeamAdvancedStats), not per-team or per-player.

Run manually: python -m backend.ratings.refresh_team_style
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.live_client.client import NBAStatsClient
from backend.live_client.endpoints.stats.team_season_stats import TeamAdvancedStats, TeamSeasonStats
from backend.ratings.team_style import build_style_fingerprint

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "team_style.json"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
REQUEST_PACING_SECONDS = 0.6

# Matches win_model's historical feature_seasons_used range (2016-2025) —
# see backend/win_model/data_loader.py. Season-start-year convention: 2016
# means the "2016-17" NBA season.
HISTORICAL_SEASON_START_YEARS = list(range(2016, 2026))


def is_stale(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> bool:
    if not OUTPUT_FILE.exists():
        return True
    try:
        payload = json.loads(OUTPUT_FILE.read_text())
        generated_at = datetime.fromisoformat(payload["generated_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return True
    return (datetime.now(timezone.utc) - generated_at).total_seconds() > max_age_seconds


def _season_string(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def run_refresh(start_years: list[int] = HISTORICAL_SEASON_START_YEARS, write_output: bool = True) -> dict:
    by_season_team: dict[str, dict] = {}

    with NBAStatsClient() as client:
        for i, start_year in enumerate(start_years):
            if i > 0:
                time.sleep(REQUEST_PACING_SECONDS)
            season = _season_string(start_year)
            try:
                totals = TeamSeasonStats(season=season, client=client).fetch().to_dataframe()
                advanced = TeamAdvancedStats(season=season, client=client).fetch().to_dataframe()
            except Exception:
                # A single missing/unreachable historical season shouldn't
                # blank out every other season already fetched -- same
                # "partial coverage beats none" principle as
                # refresh_roster_projection.py's per-team fallback.
                continue
            fingerprint = build_style_fingerprint(totals, advanced)
            for _, row in fingerprint.iterrows():
                by_season_team[f"{start_year}|{row['Team']}"] = {
                    "season": start_year,
                    "team": row["Team"],
                    "pace": float(row["Pace"]),
                    "ast_pct": float(row["AstPct"]),
                    "three_pa_rate": float(row["ThreePARate"]),
                }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seasons_covered": sorted({v["season"] for v in by_season_team.values()}),
        "n_team_seasons": len(by_season_team),
        "team_seasons": list(by_season_team.values()),
    }

    if write_output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2, default=str))

    return payload


if __name__ == "__main__":
    result = run_refresh()
    print(f"Refreshed team style for {len(result['seasons_covered'])} seasons ({result['n_team_seasons']} team-seasons)")
    print(f"Wrote {OUTPUT_FILE}")

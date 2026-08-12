"""backend/ratings/refresh_shot_heatmaps.py

Scheduled refresh job for the coaching page's shot-location heatmaps —
offense/defense binned shot data, one entry per (season, team, side),
covering the same historical range refresh_team_style.py does (10 seasons,
2016-2025 start years), at the default grid_cells (25) — the only
granularity the frontend actually requests (TeamShotHeatmap.tsx never
exposes grid_cells to the user; only team/season are selectable).

This is the fetch/cache half of what was the *one* API endpoint that still
called live_client directly on every request
(dependencies.get_team_shot_heatmap) — see that function's updated comment
before assuming a live-fetch exception still applies here. The old
"single ~1.5s call, disk-cached" justification held for a working network,
but on a host that can't reach stats.nba.com at all (Render — see
backend/AGENTS.md's "Player ratings: refresh strategy"), that same call
just hangs for minutes per request instead. This cache is the fix.

30 teams x 10 seasons x 2 sides (offense/defense) = 600 TeamShotChart calls
— a genuinely bigger job than refresh_team_style.py's 20 (2 calls/season),
paced the same way (REQUEST_PACING_SECONDS between every call, matching the
documented reason in backend/AGENTS.md's "Request pacing" note — volume
against a rate limit, not per-request flakiness). Expect ~20-25 minutes for
a full run, same order of magnitude as refresh_team_style.py's historical
pass.

Run manually: python -m backend.ratings.refresh_shot_heatmaps
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.live_client.client import NBAStatsClient
from backend.live_client.endpoints.stats.shot_chart import TeamShotChart
from backend.live_client.lookups.loader import load_teams
from backend.ratings.team_style import DEFAULT_GRID_CELLS, bin_shots_to_heatmap

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "shot_heatmaps.json"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
REQUEST_PACING_SECONDS = 0.6

# Matches refresh_team_style.py's historical range exactly — same
# season-start-year convention, same reason (win_model's feature_seasons_used).
HISTORICAL_SEASON_START_YEARS = list(range(2016, 2026))


def is_stale(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> bool:
    """Same contract as refresh_team_style.is_stale() — see that docstring."""
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


def _cache_key(start_year: int, team: str, side: str) -> str:
    return f"{start_year}|{team}|{side}"


def run_refresh(
    start_years: list[int] = HISTORICAL_SEASON_START_YEARS,
    grid_cells: int = DEFAULT_GRID_CELLS,
    write_output: bool = True,
) -> dict:
    teams = load_teams()
    by_key: dict[str, dict] = {}

    with NBAStatsClient() as client:
        first_call = True
        for start_year in start_years:
            season = _season_string(start_year)
            for _, team_row in teams.iterrows():
                team_name = team_row["full_name"]
                team_id = int(team_row["team_id"])
                for side, fetch_kwargs in (
                    ("offense", {"team_id": team_id}),
                    ("defense", {"opponent_team_id": team_id}),
                ):
                    if not first_call:
                        time.sleep(REQUEST_PACING_SECONDS)
                    first_call = False
                    try:
                        shots = (
                            TeamShotChart(season=season, client=client, **fetch_kwargs)
                            .fetch()
                            .to_dataframe()
                        )
                    except Exception:
                        # A single missing/unreachable team-season-side
                        # shouldn't blank out everything else already
                        # fetched — same "partial coverage beats none"
                        # principle as refresh_team_style.py.
                        continue
                    cells = bin_shots_to_heatmap(shots, grid_cells=grid_cells)
                    by_key[_cache_key(start_year, team_name, side)] = {
                        "season": start_year,
                        "team": team_name,
                        "side": side,
                        "cells": cells,
                        "n_shots": int(len(shots)),
                    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grid_cells": grid_cells,
        "seasons_covered": sorted({v["season"] for v in by_key.values()}),
        "n_entries": len(by_key),
        "heatmaps": list(by_key.values()),
    }

    if write_output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2, default=str))

    return payload


if __name__ == "__main__":
    result = run_refresh()
    print(
        f"Refreshed shot heatmaps for {len(result['seasons_covered'])} seasons "
        f"({result['n_entries']} team-season-sides)"
    )
    print(f"Wrote {OUTPUT_FILE}")

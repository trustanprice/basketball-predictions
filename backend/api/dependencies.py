"""backend/api/dependencies.py

Thin data-loading helpers used by the routers. This module orchestrates —
loads files, calls existing functions, reshapes results into the dict shapes
schemas.py expects — it does not reimplement any win_model/ratings logic.

backend/api/ is a repo-root-context module (like app.py): it's run via
`uvicorn backend.api.main:app` from the repo root, never imported from
notebooks, so it uses absolute `backend.X` imports throughout — see
backend/AGENTS.md's Imports section for why that's different from the
win_model/live_client/ratings convention.
"""

from __future__ import annotations

import functools

import pandas as pd
from fastapi import HTTPException, Query

from backend.ratings import coaching_eval
from backend.ratings.refresh_player_projections import OUTPUT_FILE as PLAYER_PROJECTIONS_FILE
from backend.ratings.refresh_player_ratings import MAX_N as PLAYER_RANKINGS_MAX_N
from backend.ratings.refresh_player_ratings import OUTPUT_FILE as PLAYER_RANKINGS_FILE
from backend.ratings.refresh_team_style import OUTPUT_FILE as TEAM_STYLE_FILE
from backend.win_model.data_loader import MASTER_DF_FILE, load_final_results, load_model_metadata


# ---- win_model ----

def get_predictions_df() -> pd.DataFrame:
    """Reads backend/win_model/train.py's results file directly — never retrains."""
    try:
        return load_final_results()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Win model results not found — run `python -m backend.win_model.train` first.",
        ) from exc


def get_model_metadata() -> dict:
    try:
        return load_model_metadata()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Model methodology not found — run `python -m backend.win_model.train` first.",
        ) from exc


# ---- player power rankings ----
# Deliberately NOT calling live_client here — see backend/AGENTS.md's "Player
# ratings: refresh strategy." This only ever reads the file the scheduled
# refresh job (backend/ratings/refresh_player_ratings.py) wrote.

def get_player_power_rankings(
    n: int = Query(5, ge=1, le=PLAYER_RANKINGS_MAX_N, description="How many ranked players per side to return."),
) -> dict:
    """`n` slices the already-cached top-`PLAYER_RANKINGS_MAX_N` list down to
    what this request asked for — the cache always stores the max, so "show
    more" is a response-shaping concern here, never a reason to refresh."""
    if not PLAYER_RANKINGS_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Player power rankings haven't been computed yet — run "
                "`python -m backend.ratings.refresh_player_ratings` (needs network access "
                "to NBA.com) or wait for the next scheduled refresh."
            ),
        )
    import json
    data = json.loads(PLAYER_RANKINGS_FILE.read_text())
    data["offense"] = data["offense"][:n]
    data["defense"] = data["defense"][:n]
    return data


# ---- projected player leaders (preseason) ----
# Same "only ever read the file a scheduled refresh wrote" rule as player
# power rankings above, and the same reason — see
# backend/ratings/refresh_player_projections.py.

def get_player_projections(
    n: int = Query(5, ge=1, le=50, description="How many projected players per side to return."),
) -> dict:
    if not PLAYER_PROJECTIONS_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Projected player leaders haven't been computed yet — run "
                "`python -m backend.ratings.refresh_player_projections` (needs network access "
                "to NBA.com) or wait for the next scheduled refresh."
            ),
        )
    import json
    data = json.loads(PLAYER_PROJECTIONS_FILE.read_text())
    data["offense"] = data["offense"][:n]
    data["defense"] = data["defense"][:n]
    return data


# ---- coaching evaluation ----
# Cheap, pure computation over static data (backend/win_model's master_df) —
# fine to compute per request, per the Phase 5 brief. Cached in-process anyway
# since master_df.csv doesn't change during a server's lifetime, and re-parsing
# + re-joining 300 rows on every request is pointless work.

@functools.lru_cache(maxsize=1)
def _team_season_talent_input() -> pd.DataFrame:
    if not MASTER_DF_FILE.exists():
        raise HTTPException(status_code=503, detail=f"{MASTER_DF_FILE} not found.")
    master_df = pd.read_csv(MASTER_DF_FILE)
    return (
        master_df.drop_duplicates(subset=["Season", "Team"])[list(coaching_eval.TEAM_SEASON_INPUT_COLUMNS)]
        .reset_index(drop=True)
    )


@functools.lru_cache(maxsize=1)
def _team_style_lookup() -> dict[tuple[int, str], dict]:
    """{(season_start_year, team): {pace, ast_pct, three_pa_rate}} — empty if
    refresh_team_style.py has never run here. A missing style lookup means
    every team-season's style fields come back null, not a 503: WAE itself
    is still fully computable without it (style is enrichment, not a
    dependency of the underlying number)."""
    if not TEAM_STYLE_FILE.exists():
        return {}
    import json
    payload = json.loads(TEAM_STYLE_FILE.read_text())
    return {(row["season"], row["team"]): row for row in payload["team_seasons"]}


@functools.lru_cache(maxsize=1)
def get_coach_team_seasons() -> pd.DataFrame:
    result = coaching_eval.coach_wins_above_expectation(_team_season_talent_input())
    style = _team_style_lookup()
    result = result.copy()
    result["pace"] = [style.get((s, t), {}).get("pace") for s, t in zip(result["Season"], result["Team"])]
    result["ast_pct"] = [style.get((s, t), {}).get("ast_pct") for s, t in zip(result["Season"], result["Team"])]
    result["three_pa_rate"] = [
        style.get((s, t), {}).get("three_pa_rate") for s, t in zip(result["Season"], result["Team"])
    ]
    return result


@functools.lru_cache(maxsize=1)
def get_coach_career_summary() -> pd.DataFrame:
    return coaching_eval.coach_career_summary(get_coach_team_seasons())


# ---- shot heatmaps (on demand, not a scheduled refresh) ----
# The one place in this API that calls live_client directly on a request —
# a deliberate, narrow exception to the "player ratings: refresh strategy"
# rule above, for reasons specific to this endpoint, not a reason to add
# more like it without re-reading this comment:
#   1. It's a single external call (one team's shot chart), not the ~30-90
#      call bulk fetch that made a live player-ratings call unacceptably
#      slow inside a request (~96s worst case, see backend/AGENTS.md).
#      Confirmed directly: a real TeamShotChart fetch takes ~1.5s.
#   2. live_client's DiskCache (see cache.py, never-expires by default) means
#      only the *first* request for a given team+season ever actually hits
#      NBA.com — everything after is a local disk read, same latency
#      profile as any other endpoint here.
#   3. This is a completed-season shot chart — there's no "current season"
#      staleness concern a scheduled refresh would even need to solve.
def get_team_shot_heatmap(
    team: str = Query(..., description="Full team name, e.g. 'Boston Celtics'"),
    season: str = Query(..., description="e.g. '2023-24'"),
    grid_cells: int = Query(25, ge=5, le=50),
) -> dict:
    from backend.live_client.client import NBAStatsClient
    from backend.live_client.endpoints.stats.shot_chart import TeamShotChart
    from backend.live_client.lookups.loader import load_teams
    from backend.ratings.team_style import bin_shots_to_heatmap

    teams = load_teams()
    match = teams.loc[teams["full_name"] == team, "team_id"]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team!r}")
    team_id = int(match.iloc[0])

    client = NBAStatsClient()
    try:
        offense = TeamShotChart(season=season, team_id=team_id, client=client).fetch().to_dataframe()
        defense = TeamShotChart(season=season, opponent_team_id=team_id, client=client).fetch().to_dataframe()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Couldn't fetch shot chart data for {team} ({season}): {exc}",
        ) from exc

    return {
        "team": team,
        "season": season,
        "offense_cells": bin_shots_to_heatmap(offense, grid_cells=grid_cells),
        "defense_cells": bin_shots_to_heatmap(defense, grid_cells=grid_cells),
        "n_offense_shots": int(len(offense)),
        "n_defense_shots": int(len(defense)),
    }

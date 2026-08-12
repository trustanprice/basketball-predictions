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
from backend.ratings.refresh_shot_heatmaps import OUTPUT_FILE as SHOT_HEATMAPS_FILE
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


# ---- shot heatmaps ----
# Used to be the one place in this API that called live_client directly on a
# request (a single ~1.5s TeamShotChart call, backed by live_client's own
# never-expiring disk cache — fine on a working network). That justification
# broke down on Render specifically: it can't reach stats.nba.com *at all*
# (see backend/AGENTS.md's "Player ratings: refresh strategy"), so instead of
# a fast disk-cache hit after the first request, every request hung for
# minutes before eventually 503ing. Now reads
# backend/ratings/refresh_shot_heatmaps.py's precomputed cache instead — same
# "only ever read the file a scheduled refresh wrote" rule as player power
# rankings/team style above. No live-fetch fallback on a cache miss
# (non-default grid_cells, or a season the refresh script hasn't covered):
# an immediate 503 is a strict improvement over a request that hangs for
# minutes and 503s anyway.

@functools.lru_cache(maxsize=1)
def _shot_heatmap_lookup() -> tuple[dict[tuple[int, str, str], dict], int | None]:
    """({(season_start_year, team, side): {cells, n_shots, ...}}, grid_cells)
    — grid_cells is None (and the dict empty) if refresh_shot_heatmaps.py has
    never run here, same "empty means never refreshed" convention as
    _team_style_lookup() above."""
    if not SHOT_HEATMAPS_FILE.exists():
        return {}, None
    import json
    payload = json.loads(SHOT_HEATMAPS_FILE.read_text())
    lookup = {(row["season"], row["team"], row["side"]): row for row in payload["heatmaps"]}
    return lookup, payload["grid_cells"]


def get_team_shot_heatmap(
    team: str = Query(..., description="Full team name, e.g. 'Boston Celtics'"),
    season: str = Query(..., description="e.g. '2023-24'"),
    grid_cells: int = Query(25, ge=5, le=50),
) -> dict:
    lookup, cached_grid_cells = _shot_heatmap_lookup()
    if not lookup:
        raise HTTPException(
            status_code=503,
            detail=(
                "Shot heatmaps haven't been computed yet — run "
                "`python -m backend.ratings.refresh_shot_heatmaps` (needs network access "
                "to NBA.com) or wait for the next scheduled refresh."
            ),
        )
    if grid_cells != cached_grid_cells:
        raise HTTPException(
            status_code=503,
            detail=f"Only grid_cells={cached_grid_cells} is cached; {grid_cells} was requested.",
        )
    try:
        start_year = int(season.split("-")[0])
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=f"Malformed season: {season!r}") from exc

    offense = lookup.get((start_year, team, "offense"))
    defense = lookup.get((start_year, team, "defense"))
    if offense is None or defense is None:
        raise HTTPException(
            status_code=503,
            detail=f"No cached shot data for {team} ({season}) — this team/season isn't covered yet.",
        )

    return {
        "team": team,
        "season": season,
        "offense_cells": offense["cells"],
        "defense_cells": defense["cells"],
        "n_offense_shots": offense["n_shots"],
        "n_defense_shots": defense["n_shots"],
    }

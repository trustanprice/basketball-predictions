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
from fastapi import HTTPException

from backend.ratings import coaching_eval
from backend.ratings.refresh_player_ratings import OUTPUT_FILE as PLAYER_RANKINGS_FILE
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

def get_player_power_rankings() -> dict:
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
    return json.loads(PLAYER_RANKINGS_FILE.read_text())


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
def get_coach_team_seasons() -> pd.DataFrame:
    return coaching_eval.coach_wins_above_expectation(_team_season_talent_input())


@functools.lru_cache(maxsize=1)
def get_coach_career_summary() -> pd.DataFrame:
    return coaching_eval.coach_career_summary(get_coach_team_seasons())

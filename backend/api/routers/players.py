"""backend/api/routers/players.py — player power rankings.

Reads the local JSON store backend/ratings/refresh_player_ratings.py writes.
Never calls backend.live_client directly — see backend/AGENTS.md's "Player
ratings: refresh strategy."
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api import schemas
from backend.api.dependencies import get_player_power_rankings, get_player_projections

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("/power-rankings", response_model=schemas.PlayerPowerRankings)
def power_rankings(data: dict = Depends(get_player_power_rankings)):
    """Top-5 offense / top-5 defense league-wide, each with a full RatingBreakdown
    (raw value, z-score, weight, contribution per component) — the transparency
    requirement is satisfied by the API response itself, not just how a frontend
    happens to render it."""
    return data


@router.get("/projected-leaders", response_model=schemas.PlayerProjectedLeaders)
def projected_leaders(data: dict = Depends(get_player_projections)):
    """PRESEASON PROJECTION — see schemas.PlayerProjectedLeaders and
    backend/ratings/refresh_player_projections.py. A distinct endpoint, not a
    query param on /power-rankings: genuinely different data (projected, not
    actual, stats) and methodology, not just a different filter on the same
    numbers."""
    return data

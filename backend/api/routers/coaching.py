"""backend/api/routers/coaching.py — coaching wins-above-expectation.

Cheap, pure computation over backend/win_model's static master_df — computed
per request (cached in-process, see backend/api/dependencies.py), not
precomputed to a file like the win-model or player-rankings endpoints.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from backend.api import schemas
from backend.api.dependencies import get_coach_career_summary, get_coach_team_seasons

router = APIRouter(prefix="/api/coaches", tags=["coaching"])


def _row_to_team_season(row) -> schemas.CoachTeamSeason:
    return schemas.CoachTeamSeason(
        season=int(row["Season"]),
        team=row["Team"],
        coach=row["Coach"],
        actual_win_pct=float(row["WIN%"]),
        implied_win_pct=float(row["implied_win_pct"]),
        wins_above_expectation=float(row["wins_above_expectation"]),
        talent_breakdown=row["talent_breakdown"],
    )


@router.get("/wins-above-expectation", response_model=list[schemas.CoachTeamSeason])
def wins_above_expectation(
    season: int | None = Query(None, description="Filter to one season, e.g. 2024"),
    team: str | None = Query(None, description="Filter to one team, e.g. 'Boston Celtics'"),
    df: pd.DataFrame = Depends(get_coach_team_seasons),
):
    """Actual WIN% vs. roster-talent-implied win%, per team-season, with the
    talent composite's full breakdown attached (same transparency requirement
    as player power rankings)."""
    if season is not None:
        df = df[df["Season"] == season]
    if team is not None:
        df = df[df["Team"] == team]
    return [_row_to_team_season(row) for _, row in df.iterrows()]


@router.get("/career-summary", response_model=list[schemas.CoachCareerSummary])
def career_summary(df: pd.DataFrame = Depends(get_coach_career_summary)):
    """One row per coach, aggregated across every team/season they appear in."""
    return [
        schemas.CoachCareerSummary(
            coach=row["Coach"],
            seasons_coached=int(row["seasons_coached"]),
            teams_coached=row["teams_coached"],
            n_teams=int(row["n_teams"]),
            avg_wins_above_expectation=float(row["avg_wins_above_expectation"]),
            avg_actual_win_pct=float(row["avg_actual_win_pct"]),
            avg_implied_win_pct=float(row["avg_implied_win_pct"]),
        )
        for _, row in df.iterrows()
    ]

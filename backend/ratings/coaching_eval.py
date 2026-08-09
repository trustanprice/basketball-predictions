"""backend/ratings/coaching_eval.py

"Wins above roster expectation": actual win% vs. a roster-talent-implied win%,
tracked per coach across teams and seasons. Same transparency requirement as
player_power_rankings.py — see ratings/core.py.

Baseline choice: this uses backend.win_model's historical talent features
(payroll, roster quality, age curve — full 2016-2025 coverage), not Phase 3's
player power rankings. Player ratings only cover whatever season live_client
fetches on demand; there's no historical backfill, so they can't support "tracked
... across teams and seasons," which needs multi-season history. See
backend/AGENTS.md — coaching_eval lives in ratings/ (not its own top-level
package) specifically because it's coupled to this module's z-score engine.

This module does not import backend.win_model or call live_client — callers
assemble the input table (documented in `TEAM_SEASON_INPUT_COLUMNS`) themselves,
typically from backend/win_model's master_df. Keeps this module testable against
known inputs, per backend/AGENTS.md's testing conventions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Component, compute_composite

# Columns compute_team_season_talent / coach_wins_above_expectation require in
# their input dataframe, and where each is expected to come from (backend.win_model
# terms, see backend/win_model/features.py and data_loader.py):
#   Season, Team, Coach   -- identifiers (data_loader.load_coaches)
#   WIN%                  -- actual same-season win percentage (master_df)
#   Payroll               -- data_loader.load_payroll
#   avg_pts_top10,
#   avg_production_score,
#   avg_age               -- data_loader.calculate_player_features
TEAM_SEASON_INPUT_COLUMNS = (
    "Season", "Team", "Coach", "WIN%", "Payroll", "avg_pts_top10", "avg_production_score", "avg_age",
)

# Deliberately excludes in-season/outcome stats (WIN%, PLUS_MINUS, Home_W, ...):
# those are partly a *product* of coaching, so including them in the "talent"
# side would make wins-above-expectation circular by construction. Every input
# here is a roster/financial fact independent of how the season played out.
TALENT_COMPONENTS = [
    Component("Payroll", "Payroll", weight=0.30, higher_is_better=True),
    Component("Top-10 Player Scoring (avg_pts_top10)", "avg_pts_top10", weight=0.30, higher_is_better=True),
    Component("Roster Production Score (avg_production_score)", "avg_production_score", weight=0.25, higher_is_better=True),
    Component("Roster Age Curve (age_factor)", "AGE_FACTOR", weight=0.15, higher_is_better=True),
]


def _age_factor(avg_age: pd.Series) -> pd.Series:
    """Distance from a 27-year-old prime, clipped to [0, 1] — the same formula
    backend/win_model/data_loader.py's load_schedule() uses for Strength_Score,
    reused here for consistency rather than inventing a second age transform."""
    return (1 - (avg_age - 27).abs() / 27).clip(lower=0, upper=1)


def compute_team_season_talent(team_seasons: pd.DataFrame):
    """Z-score roster-talent composite per team-season (does NOT touch WIN%).

    Returns (talent_z: pd.Series aligned to team_seasons.index, breakdowns: list[RatingBreakdown]).
    """
    df = team_seasons.copy()
    df["AGE_FACTOR"] = _age_factor(df["avg_age"])
    return compute_composite(df, TALENT_COMPONENTS, id_col="Team", name_col="Team")


def implied_win_pct(talent_z: pd.Series, actual_win_pct: pd.Series) -> pd.Series:
    """Maps a talent z-score onto a win% via a stated assumption, not a fitted
    regression (that would be exactly the black-box behavior ratings/ rules out):
    one standard deviation of roster talent is assumed to be worth one standard
    deviation of win%. Clipped to [0, 1] since win% can't leave that range.

        implied_win% = mean(actual_win%) + talent_z * std(actual_win%)
    """
    league_avg = actual_win_pct.mean()
    league_std = actual_win_pct.std(ddof=0)
    return (league_avg + talent_z * league_std).clip(lower=0, upper=1)


def coach_wins_above_expectation(team_seasons: pd.DataFrame) -> pd.DataFrame:
    """One row per team-season: actual WIN% vs. roster-talent-implied win%.

    `team_seasons` must have the columns in TEAM_SEASON_INPUT_COLUMNS, one row
    per (Season, Team).
    """
    missing = set(TEAM_SEASON_INPUT_COLUMNS) - set(team_seasons.columns)
    if missing:
        raise ValueError(f"team_seasons is missing columns: {sorted(missing)}")

    talent_z, breakdowns = compute_team_season_talent(team_seasons)
    implied = implied_win_pct(talent_z, team_seasons["WIN%"])

    result = team_seasons[["Season", "Team", "Coach", "WIN%"]].copy()
    result["talent_z_score"] = talent_z.values
    result["implied_win_pct"] = implied.values
    result["wins_above_expectation"] = result["WIN%"] - result["implied_win_pct"]
    result["talent_breakdown"] = [b.to_dict() for b in breakdowns]
    return result


def coach_career_summary(team_season_results: pd.DataFrame) -> pd.DataFrame:
    """Aggregates coach_wins_above_expectation()'s output to one row per coach,
    across every team and season they appear in — the "tracked ... across teams
    and seasons" view.
    """
    grouped = team_season_results.groupby("Coach")
    summary = grouped.agg(
        seasons_coached=("Season", "nunique"),
        teams_coached=("Team", lambda s: sorted(s.unique().tolist())),
        avg_wins_above_expectation=("wins_above_expectation", "mean"),
        avg_actual_win_pct=("WIN%", "mean"),
        avg_implied_win_pct=("implied_win_pct", "mean"),
    ).reset_index()
    summary["n_teams"] = summary["teams_coached"].apply(len)
    return summary.sort_values("avg_wins_above_expectation", ascending=False).reset_index(drop=True)

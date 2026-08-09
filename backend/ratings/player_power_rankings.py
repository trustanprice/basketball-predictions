"""backend/ratings/player_power_rankings.py

Top 5 offensive / top 5 defensive players league-wide: a transparent, weighted
z-score composite — not a black-box model. Every score here is reproducible by
hand from ratings/core.py's RatingBreakdown: raw value -> z-score -> weight ->
contribution -> composite.

Consumes dataframes already fetched by backend/live_client/ — this module makes
no HTTP calls itself (see backend/AGENTS.md: ratings/ is a consumer, not part of
the fetch layer).

Known data gaps (see DEFENSE_COMPONENTS below for the full explanation): "defended
FG%" isn't computed here at all — it requires an NBA.com tracking/matchup endpoint
(leaguedashptdefend) that backend/live_client/ doesn't build yet. "On/off defensive
rating" is approximated with on-court DEF_RATING rather than a true on/off split,
which needs teamplayeronoffdetails, also not built yet.
"""

from __future__ import annotations

import pandas as pd

from .core import Component, RatingBreakdown, compute_composite

# Playing-time qualifier — without it, a player with 4 minutes over 1 game can post
# a extreme rate stat and dominate a ranking built on z-scores. NBA.com's own
# "leaders" boards apply a similar filter.
MIN_GAMES_PLAYED = 20
MIN_MINUTES_PER_GAME = 15.0

OFFENSE_COMPONENTS = [
    Component("True Shooting %", "TS_PCT", weight=0.30, higher_is_better=True),
    # "Usage-adjusted scoring" has no single standard definition; this project's
    # choice (computed in build_player_table, not a raw NBA.com column): a
    # player's PTS/game restated at league-average usage, so a high-usage volume
    # scorer isn't automatically credited over an efficient lower-usage one purely
    # for having more plays run for them.
    Component("Usage-Adjusted Scoring", "USAGE_ADJ_PTS", weight=0.35, higher_is_better=True),
    Component("Playmaking (AST%)", "AST_PCT", weight=0.25, higher_is_better=True),
    Component("Turnover Rate (TOV%)", "TOV_PCT", weight=0.10, higher_is_better=False),
]

DEFENSE_COMPONENTS = [
    # Per-36-minute activity rate computed from raw counting stats (STL, BLK, MIN)
    # — a proxy for defensive activity/deterrence, not NBA.com's official
    # "defended FG%" (which needs the leaguedashptdefend tracking endpoint).
    Component("Steal+Block Rate (per 36 min)", "STL_BLK_PER36", weight=0.35, higher_is_better=True),
    Component("Defensive Rebound % (DREB%)", "DREB_PCT", weight=0.30, higher_is_better=True),
    # On-court team defensive rating — a one-sided proxy for "on/off defensive
    # rating" (the real on/off differential needs teamplayeronoffdetails, not yet
    # built). Lower DEF_RATING is better, hence higher_is_better=False.
    Component("On-Court Defensive Rating", "DEF_RATING", weight=0.35, higher_is_better=False),
]

_JOIN_COLS = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID"]
_REQUIRED_TOTALS_COLS = {"GP", "MIN", "PTS", "STL", "BLK"}
_REQUIRED_ADVANCED_COLS = {"USG_PCT", "TS_PCT", "AST_PCT", "TOV_PCT", "DREB_PCT", "DEF_RATING"}


def build_player_table(season_totals: pd.DataFrame, advanced_stats: pd.DataFrame) -> pd.DataFrame:
    """Join season totals with advanced stats and derive the two inputs that
    aren't raw NBA.com columns (USAGE_ADJ_PTS, STL_BLK_PER36).

    Parameters
    ----------
    season_totals : live_client.endpoints.stats.PlayerSeasonTotals.fetch() output,
        MUST have been fetched with per_mode="PerGame" — this function assumes
        PTS/MIN/STL/BLK are per-game averages, not season totals.
    advanced_stats : live_client.endpoints.stats.PlayerAdvancedStats.fetch()
        output (any per_mode — only rate stats are used).

    Returns a table restricted to qualified players (GP >= MIN_GAMES_PLAYED and
    MIN >= MIN_MINUTES_PER_GAME).
    """
    missing_totals = _REQUIRED_TOTALS_COLS - set(season_totals.columns)
    if missing_totals:
        raise ValueError(f"season_totals is missing columns: {sorted(missing_totals)}")
    missing_advanced = _REQUIRED_ADVANCED_COLS - set(advanced_stats.columns)
    if missing_advanced:
        raise ValueError(f"advanced_stats is missing columns: {sorted(missing_advanced)}")

    df = season_totals.merge(advanced_stats, on=_JOIN_COLS, suffixes=("", "_adv"))

    qualified = df[
        (df["GP"] >= MIN_GAMES_PLAYED) & (df["MIN"] >= MIN_MINUTES_PER_GAME)
    ].reset_index(drop=True).copy()

    if qualified.empty:
        raise ValueError(
            f"No players met the qualification filter (GP>={MIN_GAMES_PLAYED}, "
            f"MIN>={MIN_MINUTES_PER_GAME}) — check the input data."
        )

    league_avg_usage = qualified["USG_PCT"].mean()
    qualified["USAGE_ADJ_PTS"] = qualified["PTS"] * (league_avg_usage / qualified["USG_PCT"])
    qualified["STL_BLK_PER36"] = (qualified["STL"] + qualified["BLK"]) / qualified["MIN"] * 36

    return qualified


def _top_n(player_table: pd.DataFrame, components: list[Component], score_col: str, n: int) -> list[RatingBreakdown]:
    scores, breakdowns = compute_composite(player_table, components, "PLAYER_ID", "PLAYER_NAME")
    order = scores.sort_values(ascending=False).head(n).index
    breakdown_by_index = dict(zip(player_table.index, breakdowns))
    return [breakdown_by_index[i] for i in order]


def top_offensive_players(player_table: pd.DataFrame, n: int = 5) -> list[RatingBreakdown]:
    """Top `n` players league-wide by offense_score, each with a full breakdown."""
    return _top_n(player_table, OFFENSE_COMPONENTS, "offense_score", n)


def top_defensive_players(player_table: pd.DataFrame, n: int = 5) -> list[RatingBreakdown]:
    """Top `n` players league-wide by defense_score, each with a full breakdown."""
    return _top_n(player_table, DEFENSE_COMPONENTS, "defense_score", n)

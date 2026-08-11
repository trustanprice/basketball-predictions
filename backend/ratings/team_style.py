"""backend/ratings/team_style.py

Pure computation for the coaching page's "team style fingerprint" and shot
heatmaps — pace, 3PA rate, assist rate, and binned shot-location data.
Descriptive context alongside each coach's wins-above-expectation, never
presented as causal: a team's pace/shot profile is correlated with (or just
associated with) coaching outcomes at most, not a stated cause of them — see
backend/AGENTS.md and the frontend copy that renders this.

No live_client calls here — callers (refresh_team_style.py for the
historical fingerprint, backend/api/routers/coaching.py for the on-demand
shot heatmap) fetch the raw dataframes and hand them to the functions below,
same fetch/compute separation as the rest of ratings/.
"""

from __future__ import annotations

import pandas as pd

# Half-court shot chart coordinate bounds, in nba_api's LOC_X/LOC_Y units
# (roughly feet x 10, hoop at origin) — confirmed against real shot data:
# X spans about -250 to 250, Y about -50 to 470 for attempted shots.
_LOC_X_RANGE = (-250, 250)
_LOC_Y_RANGE = (-50, 470)
DEFAULT_GRID_CELLS = 25


def build_style_fingerprint(team_totals: pd.DataFrame, team_advanced: pd.DataFrame) -> pd.DataFrame:
    """Merges one season's TeamSeasonStats (Base) + TeamAdvancedStats
    (Advanced) into one row per team: Team, Pace, AstPct, ThreePARate.

    `three_pa_rate` isn't a raw NBA.com column -- computed here as FG3A/FGA,
    the same "what fraction of shots are 3s" reading as the players page's
    archetype classifier (see ratings/player_development.py), just at team
    level instead of player level.
    """
    merged = team_totals.merge(team_advanced, on=["TEAM_ID", "TEAM_NAME"], suffixes=("", "_adv"))
    return pd.DataFrame({
        "Team": merged["TEAM_NAME"],
        "Pace": merged["PACE"],
        "AstPct": merged["AST_PCT"],
        "ThreePARate": merged["FG3A"] / merged["FGA"].replace(0, 1),
    })


def bin_shots_to_heatmap(shots: pd.DataFrame, grid_cells: int = DEFAULT_GRID_CELLS) -> list[dict]:
    """Bins raw shot attempts (LOC_X, LOC_Y, SHOT_MADE_FLAG) into a
    `grid_cells` x `grid_cells` grid over the half court. Returns one dict
    per *non-empty* cell: {x, y (cell center, in LOC_X/LOC_Y units),
    attempts, makes, fg_pct} -- empty cells are omitted rather than padding
    the payload with zeros the frontend would just skip anyway.
    """
    if shots.empty:
        return []

    x_edges = pd.cut(shots["LOC_X"], bins=pd.interval_range(*_LOC_X_RANGE, periods=grid_cells))
    y_edges = pd.cut(shots["LOC_Y"], bins=pd.interval_range(*_LOC_Y_RANGE, periods=grid_cells))

    grouped = shots.groupby([x_edges, y_edges], observed=True)["SHOT_MADE_FLAG"].agg(["count", "sum"])
    grouped = grouped[grouped["count"] > 0]

    cells = []
    for (x_interval, y_interval), row in grouped.iterrows():
        attempts = int(row["count"])
        makes = int(row["sum"])
        cells.append({
            "x": round(float(x_interval.mid), 1),
            "y": round(float(y_interval.mid), 1),
            "attempts": attempts,
            "makes": makes,
            "fg_pct": round(makes / attempts, 4) if attempts else 0.0,
        })
    return cells

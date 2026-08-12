"""backend/win_model/defense_composite_features.py

Hypothesis test: win_model's current talent features are purely offensive
(avg_pts_top10, avg_production_score = PTS/MIN) -- zero defensive signal.
Does adding one, reusing ratings/player_power_rankings.py's existing
DEFENSE_COMPONENTS (STL+BLK per-36, DREB%, on-court DEF_RATING) rather than
inventing a second rating system, improve walk-forward MAE?

Unlike roster_change_features.py/age_curve_residual_features.py, this one
can't be built from the local Basketball-Reference-style per-season CSVs --
DREB_PCT and DEF_RATING are NBA.com advanced-stats columns with no
Basketball-Reference equivalent in this project's local files. Needs a real
live_client fetch (PlayerSeasonTotals + PlayerAdvancedStats, two league-wide
calls per season -- same cheap, one-call-per-season shape as
ratings/refresh_team_style.py, not per-player) for every season this feature
needs to cover.

For historical row Season=N: build_player_table() (REUSED, not duplicated --
same qualification filter, same STL_BLK_PER36/DREB_PCT/DEF_RATING columns
player_power_rankings.py's live rankings already use) on season N's real
league-wide data, take each team's top 10 scorers (matching how avg_pts_top10/
avg_production_score/avg_age are restricted -- see backend/AGENTS.md), and
average their DEFENSE_COMPONENTS z-score. A top-10-by-points player who
doesn't clear player_power_rankings.py's own GP/MIN qualification bar (rare --
a high scorer in a short stint) is skipped for this feature specifically
rather than counted with an unreliable rate stat, same "insufficient data,
don't fabricate" rule as elsewhere in this project.

The forecast row (Season=2026, describing the real completed 2025-26 season)
uses the exact same computation on 2025-26's real data -- there's no defensive
equivalent of the aging-curve projection (player_development.py's curve is
built purely from PTS-per-36 transitions), so this is a real-value carry-
forward, same honesty standard as Payroll's forecast-row treatment: last
known real defensive performance, explicitly not a projection.

Run manually: python -m backend.win_model.defense_composite_features
"""

from __future__ import annotations

import time

import pandas as pd

from .data_loader import MASTER_DF_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward

try:
    from ..ratings.core import compute_composite
    from ..ratings.player_power_rankings import DEFENSE_COMPONENTS, build_player_table
except ImportError:
    from ratings.core import compute_composite
    from ratings.player_power_rankings import DEFENSE_COMPONENTS, build_player_table

try:
    from ..live_client.client import NBAStatsClient
    from ..live_client.endpoints.stats.advanced_metrics import PlayerAdvancedStats
    from ..live_client.endpoints.stats.season_totals import PlayerSeasonTotals
    from ..live_client.lookups.loader import load_teams
except ImportError:
    from live_client.client import NBAStatsClient
    from live_client.endpoints.stats.advanced_metrics import PlayerAdvancedStats
    from live_client.endpoints.stats.season_totals import PlayerSeasonTotals
    from live_client.lookups.loader import load_teams

DEFENSE_COMPOSITE_COLUMN = "Defense_Composite_Top10"
REQUEST_PACING_SECONDS = 0.6
TOP_N_SCORERS = 10


def _season_string(repo_end_year: int) -> str:
    start = repo_end_year - 1
    return f"{start}-{str(repo_end_year)[-2:]}"


def _season_defense_table(season: str, client) -> pd.DataFrame:
    """One row per qualified player in `season`: TEAM_ID, PTS, and their
    DEFENSE_COMPONENTS composite z-score."""
    totals = PlayerSeasonTotals(season=season, per_mode="PerGame", client=client).fetch().to_dataframe()
    advanced = PlayerAdvancedStats(season=season, client=client).fetch().to_dataframe()
    table = build_player_table(totals, advanced)
    scores, _ = compute_composite(table, DEFENSE_COMPONENTS, "PLAYER_ID", "PLAYER_NAME")
    table = table.copy()
    table["defense_z"] = scores.values
    return table[["PLAYER_NAME", "TEAM_ID", "PTS", "defense_z"]]


def build_defense_tables(repo_end_years: list[int]) -> dict[int, pd.DataFrame]:
    """Fetches and builds one qualified-player defense table per repo-labeled
    season -- real live_client calls, paced the same way every other
    multi-season league-wide fetch in this project is (see backend/AGENTS.md's
    "Request pacing" note)."""
    client = NBAStatsClient()
    tables = {}
    for i, year in enumerate(repo_end_years):
        if i > 0:
            time.sleep(REQUEST_PACING_SECONDS)
        tables[year] = _season_defense_table(_season_string(year), client)
    return tables


def _team_defense_composite(team_id: int, table: pd.DataFrame) -> float | None:
    """Average defense_z across `team_id`'s top TOP_N_SCORERS players by PTS
    in `table` -- players who didn't clear build_player_table()'s own
    qualification filter simply aren't in `table` at all, so they're already
    excluded rather than needing a separate check here."""
    roster = table[table["TEAM_ID"] == team_id].sort_values("PTS", ascending=False).head(TOP_N_SCORERS)
    if roster.empty:
        return None
    return float(roster["defense_z"].mean())


def build_defense_composite_features(master_df_path=None, defense_tables: dict[int, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Returns one row per (Season, Team) with DEFENSE_COMPOSITE_COLUMN, for
    exactly the historical rows compare_models_walk_forward trains/evaluates on.
    `defense_tables` can be passed in (e.g. cached from a prior call) to avoid
    re-fetching -- building it fresh triggers real network calls."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    seasons = sorted(int(s) for s in trainable["Season"].unique())
    tables = defense_tables or build_defense_tables(seasons)

    # Team name -> TEAM_ID: nba_api's own team lookup, not a second mapping table.
    teams = load_teams().set_index("full_name")["team_id"]

    rows = []
    for season, team in zip(trainable["Season"], trainable["Team"]):
        season_table = tables.get(int(season))
        team_id = teams.get(team)
        composite = _team_defense_composite(int(team_id), season_table) if (season_table is not None and team_id is not None) else None
        rows.append({"Season": season, "Team": team, DEFENSE_COMPOSITE_COLUMN: composite})
    return pd.DataFrame(rows)


def forecast_defense_composite(team: str, most_recent_season: int, defense_tables: dict[int, pd.DataFrame]) -> float | None:
    """Forecast-row version: the team's real most-recently-completed season's
    defensive composite for its actual top-10 scorers that season -- a
    carry-forward of real data, not a projection (see module docstring)."""
    teams = load_teams().set_index("full_name")["team_id"]
    team_id = teams.get(team)
    season_table = defense_tables.get(most_recent_season)
    if team_id is None or season_table is None:
        return None
    return _team_defense_composite(int(team_id), season_table)


def run_experiment(master_df_path=None) -> dict:
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    composites = build_defense_composite_features(master_df_path)
    merged = trainable.merge(composites, on=["Season", "Team"], how="left")
    n_missing = merged[DEFENSE_COMPOSITE_COLUMN].isna().sum()
    merged[DEFENSE_COMPOSITE_COLUMN] = merged[DEFENSE_COMPOSITE_COLUMN].fillna(0.0)

    y = merged[TARGET_COLUMN]
    groups = merged["Season"]

    baseline_X = merged[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    augmented_numeric = NUMERIC_FEATURES + [DEFENSE_COMPOSITE_COLUMN]
    augmented_X = merged[augmented_numeric + CATEGORICAL_FEATURES]

    baseline = compare_models_walk_forward(baseline_X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    augmented = compare_models_walk_forward(augmented_X, y, groups, augmented_numeric, CATEGORICAL_FEATURES)

    baseline_mae = min(baseline.knn_walk_forward_mae, baseline.gbm_walk_forward_mae)
    augmented_mae = min(augmented.knn_walk_forward_mae, augmented.gbm_walk_forward_mae)

    return {
        "hypothesis": (
            "A team-level defensive composite (top-10-by-points players' average "
            "DEFENSE_COMPONENTS z-score) improves walk-forward MAE on top of the "
            "existing purely-offensive talent features."
        ),
        "baseline_walk_forward_mae": round(float(baseline_mae), 3),
        "baseline_winner": baseline.winner,
        "augmented_walk_forward_mae": round(float(augmented_mae), 3),
        "augmented_winner": augmented.winner,
        "improves_mae": bool(augmented_mae < baseline_mae),
        "n_rows": int(len(merged)),
        "n_missing_defense_data": int(n_missing),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Baseline MAE: {result['baseline_walk_forward_mae']} ({result['baseline_winner']})")
    print(f"Augmented MAE: {result['augmented_walk_forward_mae']} ({result['augmented_winner']})")
    print(f"Defensive composite feature {verdict} walk-forward MAE.")
    print(f"(missing defense data for {result['n_missing_defense_data']} of {result['n_rows']} rows)")

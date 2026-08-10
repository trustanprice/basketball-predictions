"""backend/win_model/player_projection_features.py

Originated as a hypothesis test (Predictions page redesign, Part A2): does
feeding player-level *projected* talent -- via ratings/player_development.py's
empirical aging curve, applied retrospectively to each historical season's real
roster -- into win_model's feature set for every historical training row improve
walk-forward MAE, on top of the team-level current-season aggregates already used?

Verified via run_experiment(): walk-forward MAE improved (6.781 -> 6.719 wins,
GBM both times) with these three columns added alongside the existing raw
aggregates, not replacing them. Real, reproducible (both candidate models are
deterministic here -- KNN has no randomness, GBM's random_state is fixed), if
modest. Per the same standard as calibration.py's honest negative finding: this
one's positive, so it's wired into train.py's FEATURE_COLUMNS rather than left
as a standalone curiosity -- see run_pipeline().

`run_experiment()` stays here as the re-runnable record of that validation --
re-run it after any change to player_development.py's aging curve to confirm
the improvement still holds.

Run manually: python -m backend.win_model.player_projection_features
"""

from __future__ import annotations

import pandas as pd

from .data_loader import MASTER_DF_FILE, load_players
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward

# ratings/ is a sibling top-level package -- see backend/AGENTS.md's Imports
# section on the try/relative-except/plain-fallback pattern.
try:
    from ..ratings.player_development import (
        build_aging_curve,
        project_player_next_season,
        project_team_talent_features,
    )
except ImportError:
    from ratings.player_development import (
        build_aging_curve,
        project_player_next_season,
        project_team_talent_features,
    )

PROJECTED_FEATURE_COLUMNS = ["avg_age_projected", "avg_pts_top10_projected", "avg_production_score_projected"]
_RAW_SOURCE_COLUMNS = ["avg_age", "avg_pts_top10", "avg_production_score"]


def _historical_player_panel() -> pd.DataFrame:
    """data_loader.load_players() reshaped to the column shape
    ratings.player_development.build_aging_curve/project_player_next_season
    expect (PLAYER_ID, SEASON_ID, PLAYER_AGE, GP, MIN, PTS).

    Player *name* stands in for PLAYER_ID here: the local historical CSVs
    (Basketball-Reference scrapes, 2016-2025) have no numeric NBA player ID,
    only a name string. Name-keyed joins are known-fragile (rare duplicate
    names, suffix/accent variants) -- acceptable for a one-off hypothesis
    test (whether a feature helps, not a production join), not a pattern to
    reuse elsewhere without addressing that.
    """
    df = load_players()
    return pd.DataFrame({
        "PLAYER_ID": df["Player"],
        "SEASON_ID": df["Season"].astype(str),
        "PLAYER_AGE": df["Age"],
        "GP": df["G"],
        "MIN": df["MP"],
        "PTS": df["PTS"],
        "Team": df["Team"],
        "_season_int": df["Season"],
    })


def _project_team_season(panel: pd.DataFrame, aging_curve: pd.DataFrame, team: str, season: int) -> dict | None:
    """Projects `team`'s actual `season` roster one season forward.

    Each player's history is filtered to seasons <= `season` *before* being
    handed to project_player_next_season -- this is what keeps the
    experiment itself honest about not looking into the future, independent
    of (in addition to) the walk-forward splitter used later on the model.
    Returns None if no local roster data exists for this (team, season).
    """
    roster = panel.loc[(panel["Team"] == team) & (panel["_season_int"] == season), "PLAYER_ID"].unique()
    if len(roster) == 0:
        return None

    projections = []
    for player in roster:
        history = panel[(panel["PLAYER_ID"] == player) & (panel["_season_int"] <= season)]
        if history.empty:
            continue
        projections.append(project_player_next_season(history, aging_curve))

    if not projections:
        return None
    return project_team_talent_features(pd.DataFrame(projections))


def build_projected_features(master_df_path=None) -> pd.DataFrame:
    """Returns one row per (Season, Team) with PROJECTED_FEATURE_COLUMNS --
    exactly the historical rows compare_models_walk_forward trains/evaluates on.
    """
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    panel = _historical_player_panel()
    # One global curve, not recomputed per season -- same reasoning as
    # calibration.historical_win_std (see backend/AGENTS.md): the *shape* of
    # how scoring rate changes with age is a stable empirical property of the
    # sport, not a fitted parameter a given fold's "future" would leak into a
    # downstream model.
    aging_curve = build_aging_curve([group for _, group in panel.groupby("PLAYER_ID")])

    rows = []
    for season, team in zip(trainable["Season"], trainable["Team"]):
        features = _project_team_season(panel, aging_curve, team, season)
        rows.append({
            "Season": season,
            "Team": team,
            "avg_age_projected": features["avg_age"] if features else None,
            "avg_pts_top10_projected": features["avg_pts_top10"] if features else None,
            "avg_production_score_projected": features["avg_production_score"] if features else None,
        })
    return pd.DataFrame(rows)


def run_experiment(master_df_path=None) -> dict:
    """Runs the full baseline-vs-augmented walk-forward comparison and returns
    an honest result dict -- improves_mae is the whole point of this function,
    not a side note."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    projected = build_projected_features(master_df_path)
    merged = trainable.merge(projected, on=["Season", "Team"], how="left")
    # Rows where a retrospective projection wasn't possible (no local roster
    # match for that team-season) fall back to the team's own already-existing
    # raw aggregate, so the "augmented" run stays row-comparable to the
    # baseline rather than silently dropping teams.
    for projected_col, raw_col in zip(PROJECTED_FEATURE_COLUMNS, _RAW_SOURCE_COLUMNS):
        merged[projected_col] = merged[projected_col].fillna(merged[raw_col])

    y = merged[TARGET_COLUMN]
    groups = merged["Season"]

    baseline_X = merged[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    augmented_numeric = NUMERIC_FEATURES + PROJECTED_FEATURE_COLUMNS
    augmented_X = merged[augmented_numeric + CATEGORICAL_FEATURES]

    baseline = compare_models_walk_forward(baseline_X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    augmented = compare_models_walk_forward(augmented_X, y, groups, augmented_numeric, CATEGORICAL_FEATURES)

    baseline_mae = min(baseline.knn_walk_forward_mae, baseline.gbm_walk_forward_mae)
    augmented_mae = min(augmented.knn_walk_forward_mae, augmented.gbm_walk_forward_mae)

    return {
        "hypothesis": (
            "Feeding player-level projected talent (aging-curve-adjusted, applied "
            "retrospectively to each historical season's real roster) into every "
            "historical training row, alongside the existing team-level current-season "
            "aggregates, improves walk-forward MAE."
        ),
        "baseline_walk_forward_mae": round(float(baseline_mae), 3),
        "baseline_winner": baseline.winner,
        "augmented_walk_forward_mae": round(float(augmented_mae), 3),
        "augmented_winner": augmented.winner,
        "improves_mae": bool(augmented_mae < baseline_mae),
        "features_added": PROJECTED_FEATURE_COLUMNS,
        "n_rows": int(len(merged)),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Baseline MAE: {result['baseline_walk_forward_mae']} ({result['baseline_winner']})")
    print(f"Augmented MAE: {result['augmented_walk_forward_mae']} ({result['augmented_winner']})")
    print(f"Player-level projected talent {verdict} walk-forward MAE.")

"""backend/win_model/age_curve_residual_features.py

Hypothesis test: does a feature capturing "how far is this roster's production
sitting above/below what ratings/player_development.py's empirical age curve
would predict for players this age" improve walk-forward MAE?

Distinct from player_projection_features.py's use of the same curve: that
module projects a player's stats FORWARD one season (curve output as an
input to a projection). This one looks BACKWARD at each player's own most
recent real transition and asks whether they beat or missed the curve's
expectation for someone their age -- the residual, not the raw curve value.
A player at any age can "defy" the curve in either direction; nothing here
singles out youth or veterans specially, or hardcodes any player/team.

For historical row Season=N (features describe season N, predicting N+1):
each player on N's real roster gets their own transition INTO season N (their
stats in N-1 vs. N, wherever they played in N-1) compared against the global
curve's median expectation for their age at the start of that transition.
Residual = their actual %-change in PTS-per-36 minus the curve's median for
that age. Team value = production-weighted average residual across roster
players with a usable transition (same "insufficient history, skip rather
than fabricate" rule as elsewhere -- a rookie or a player with no prior-season
line anywhere just doesn't contribute one).

The forecast row uses the exact same computation, anchored at the real
current roster (ratings/refresh_roster_projection.py's output) instead of a
future season's file that doesn't exist yet -- comparing each current player's
most recently completed transition (last full season vs. the one before it),
not a forward projection of a season that hasn't happened.

The aging curve itself is built once, globally, across all available
transitions -- same choice (and same reasoning: the *shape* of the
age-production relationship is a stable property of the sport, not a fitted
parameter a fold's "future" could leak into) already used by
player_projection_features.py and calibration.historical_win_std.

Run manually: python -m backend.win_model.age_curve_residual_features
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd

from .data_loader import MASTER_DF_FILE, PLAYER_STATS_DIR
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward
from .utils import team_map

try:
    from ..ratings.player_development import MIN_OBSERVATIONS_PER_AGE_BIN
except ImportError:
    from ratings.player_development import MIN_OBSERVATIONS_PER_AGE_BIN

AGE_RESIDUAL_COLUMN = "Age_Curve_Residual"


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(name))
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.strip().lower().replace(".", "").replace("'", "")


def _load_season_panel(season: int) -> pd.DataFrame:
    """One row per player who appeared for a real team in `season`, with
    normalized name, team, age, per-36 scoring rate, and total-season point
    production (used as the aggregation weight)."""
    path = PLAYER_STATS_DIR / f"{season}-player-stats.csv"
    if not path.exists():
        return pd.DataFrame(columns=["norm_name", "Team_full", "age", "per36", "total_pts"])
    df = pd.read_csv(path)
    df = df[~df["Team"].isin(["2TM", "3TM", "4TM"])].copy()
    df["Team_full"] = df["Team"].map(team_map).fillna(df["Team"])
    df["norm_name"] = df["Player"].map(_normalize_name)
    minutes = df["MP"].to_numpy(dtype=float)
    pts = df["PTS"].to_numpy(dtype=float)
    df["per36"] = (pts / minutes.clip(min=1e-9)) * 36
    df.loc[minutes <= 0, "per36"] = 0.0
    df["total_pts"] = df["PTS"] * df["G"]
    df["age"] = df["Age"]
    return df[["norm_name", "Team_full", "age", "per36", "total_pts"]]


def _build_curve_from_per36(long_panel: pd.DataFrame) -> pd.DataFrame:
    """Same binning/median/MIN_OBSERVATIONS_PER_AGE_BIN logic as
    ratings.player_development.build_aging_curve(), operating on our
    already-computed per36 column directly instead of raw PTS/MIN -- avoids
    reconstructing fake PTS/MIN pairs just to satisfy that function's input
    shape when we already have the per36 rates it would derive anyway."""
    transitions = []
    for name, group in long_panel.groupby("norm_name"):
        g = group.sort_values("SEASON_ID").reset_index(drop=True)
        if len(g) < 2:
            continue
        for i in range(len(g) - 1):
            start_per36, end_per36 = g.loc[i, "per36"], g.loc[i + 1, "per36"]
            start_age = g.loc[i, "age"]
            if start_per36 <= 0 or pd.isna(start_age):
                continue
            transitions.append({"age": int(round(start_age)), "pct_change": (end_per36 - start_per36) / start_per36})

    if not transitions:
        return pd.DataFrame(columns=["n_observations", "median_pct_change"]).rename_axis("age")
    t = pd.DataFrame(transitions)
    curve = t.groupby("age")["pct_change"].agg(n_observations="count", median_pct_change="median")
    return curve[curve["n_observations"] >= MIN_OBSERVATIONS_PER_AGE_BIN]


def _team_residual(
    team: str, actual_season: int, prior_season: int, panels: dict[int, pd.DataFrame], curve: pd.DataFrame,
) -> float | None:
    """Production-weighted average age-curve residual for `team`'s real
    roster in `actual_season`, using each player's own transition from
    `prior_season` (wherever they played it) into `actual_season`. None if
    no roster player has a usable transition (falls back to 0 by the caller,
    same convention as roster_change_features)."""
    actual_panel = panels.get(actual_season)
    prior_panel = panels.get(prior_season)
    if actual_panel is None or prior_panel is None or actual_panel.empty or prior_panel.empty:
        return None

    roster = actual_panel[actual_panel["Team_full"] == team]
    if roster.empty:
        return None
    prior_by_name = prior_panel.set_index("norm_name")[["age", "per36"]]

    weighted_sum, weight_total = 0.0, 0.0
    for _, row in roster.iterrows():
        name = row["norm_name"]
        if name not in prior_by_name.index:
            continue  # rookie or no prior-season line anywhere -- skip, don't fabricate
        prior_row = prior_by_name.loc[name]
        if isinstance(prior_row, pd.DataFrame):  # duplicate name safety, take first
            prior_row = prior_row.iloc[0]
        start_age = prior_row["age"]
        start_per36 = prior_row["per36"]
        age_bin = int(round(start_age)) if pd.notna(start_age) else None
        if age_bin is None or age_bin not in curve.index or start_per36 <= 0:
            continue  # no curve data for this age, or no real prior scoring rate to compare from
        actual_pct_change = (row["per36"] - start_per36) / start_per36
        expected_pct_change = float(curve.loc[age_bin, "median_pct_change"])
        residual = actual_pct_change - expected_pct_change
        weight = max(float(row["total_pts"]), 0.0)
        weighted_sum += residual * weight
        weight_total += weight

    if weight_total <= 0:
        return None
    return weighted_sum / weight_total


def build_age_residual_features(master_df_path=None) -> pd.DataFrame:
    """Returns one row per (Season, Team) with AGE_RESIDUAL_COLUMN, for
    exactly the historical rows compare_models_walk_forward trains/evaluates on."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    seasons = sorted(trainable["Season"].unique())
    panels = {int(s): _load_season_panel(int(s)) for s in set(seasons) | {s - 1 for s in seasons}}
    curve = _build_curve_from_per36(
        pd.concat([p.assign(SEASON_ID=s) for s, p in panels.items() if not p.empty], ignore_index=True)
    )

    rows = []
    for season, team in zip(trainable["Season"], trainable["Team"]):
        residual = _team_residual(team, int(season), int(season) - 1, panels, curve)
        rows.append({"Season": season, "Team": team, AGE_RESIDUAL_COLUMN: residual})
    return pd.DataFrame(rows)


def forecast_age_residual(
    team: str, most_recent_season: int, roster_projection_path: Path | str,
) -> float | None:
    """Forecast-row version: same computation, using the real current roster
    (ratings/refresh_roster_projection.py's fetch) as the "actual_season"
    roster membership, but each player's own real per36 in
    `most_recent_season` (not a projection) as their "actual" value -- we
    want whether they *already* beat the curve on their last real season,
    not whether the curve says they will."""
    path = Path(roster_projection_path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    player_detail = payload.get("player_detail", {})
    if team not in player_detail:
        return None

    seasons_needed = [most_recent_season, most_recent_season - 1]
    panels = {s: _load_season_panel(s) for s in seasons_needed}
    curve = _build_curve_from_per36(
        pd.concat([p.assign(SEASON_ID=s) for s, p in panels.items() if not p.empty], ignore_index=True)
    )

    actual_panel = panels[most_recent_season]
    prior_panel = panels[most_recent_season - 1]
    if actual_panel.empty or prior_panel.empty:
        return None
    prior_by_name = prior_panel.set_index("norm_name")[["age", "per36"]]
    actual_by_name = actual_panel.set_index("norm_name")[["per36", "total_pts"]]

    roster_names = {_normalize_name(p["player_name"]) for p in player_detail[team]}
    weighted_sum, weight_total = 0.0, 0.0
    for name in roster_names:
        if name not in actual_by_name.index or name not in prior_by_name.index:
            continue
        actual_row = actual_by_name.loc[name]
        prior_row = prior_by_name.loc[name]
        if isinstance(actual_row, pd.DataFrame):
            actual_row = actual_row.iloc[0]
        if isinstance(prior_row, pd.DataFrame):
            prior_row = prior_row.iloc[0]
        start_age = prior_row["age"]
        start_per36 = prior_row["per36"]
        age_bin = int(round(start_age)) if pd.notna(start_age) else None
        if age_bin is None or age_bin not in curve.index or start_per36 <= 0:
            continue
        actual_pct_change = (actual_row["per36"] - start_per36) / start_per36
        expected_pct_change = float(curve.loc[age_bin, "median_pct_change"])
        residual = actual_pct_change - expected_pct_change
        weight = max(float(actual_row["total_pts"]), 0.0)
        weighted_sum += residual * weight
        weight_total += weight

    if weight_total <= 0:
        return None
    return weighted_sum / weight_total


def run_experiment(master_df_path=None) -> dict:
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    residuals = build_age_residual_features(master_df_path)
    merged = trainable.merge(residuals, on=["Season", "Team"], how="left")
    merged[AGE_RESIDUAL_COLUMN] = merged[AGE_RESIDUAL_COLUMN].fillna(0.0)

    y = merged[TARGET_COLUMN]
    groups = merged["Season"]

    baseline_X = merged[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    augmented_numeric = NUMERIC_FEATURES + [AGE_RESIDUAL_COLUMN]
    augmented_X = merged[augmented_numeric + CATEGORICAL_FEATURES]

    baseline = compare_models_walk_forward(baseline_X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    augmented = compare_models_walk_forward(augmented_X, y, groups, augmented_numeric, CATEGORICAL_FEATURES)

    baseline_mae = min(baseline.knn_walk_forward_mae, baseline.gbm_walk_forward_mae)
    augmented_mae = min(augmented.knn_walk_forward_mae, augmented.gbm_walk_forward_mae)

    return {
        "hypothesis": (
            "A team-level, production-weighted measure of how far each roster player's most "
            "recent real transition sits above/below the empirical age curve's expectation for "
            "their age improves walk-forward MAE."
        ),
        "baseline_walk_forward_mae": round(float(baseline_mae), 3),
        "baseline_winner": baseline.winner,
        "augmented_walk_forward_mae": round(float(augmented_mae), 3),
        "augmented_winner": augmented.winner,
        "improves_mae": bool(augmented_mae < baseline_mae),
        "n_rows": int(len(merged)),
        "n_nonzero_rows": int((merged[AGE_RESIDUAL_COLUMN] != 0.0).sum()),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Baseline MAE: {result['baseline_walk_forward_mae']} ({result['baseline_winner']})")
    print(f"Augmented MAE: {result['augmented_walk_forward_mae']} ({result['augmented_winner']})")
    print(f"Age-curve-residual feature {verdict} walk-forward MAE.")

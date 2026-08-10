"""backend/win_model/train.py

Runs the full win-model pipeline end to end:
  load master_df -> dedupe + build true next-season target -> walk-forward-tune and
  benchmark KNN vs GBM -> attach prediction intervals to the live forecast -> write
  results + a methodology summary that app.py reads for the "how this was
  calculated" explanation.

Run from repo root:    python -m backend.win_model.train
Run from backend/:      python -m win_model.train
Both work because internal imports here are relative (see backend/AGENTS.md).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone

from .calibration import (
    TOTAL_SEASON_WINS,
    calibrate_season_predictions,
    historical_win_std,
    recenter_interval,
)
from .data_loader import MASTER_DF_FILE, METADATA_FILE, RESULTS_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import (
    bootstrap_residual_interval,
    compare_models_walk_forward,
    compute_feature_importance,
    gbm_quantile_interval,
)
from .validation import SeasonWalkForwardSplit

# ratings/ is a sibling top-level package, not a submodule of win_model, so
# neither pure-relative nor pure-absolute import works under both of this
# file's supported invocation roots (see backend/AGENTS.md's Imports
# section): relative (`..ratings...`) only resolves from repo-root context
# (`python -m backend.win_model.train`); plain top-level (`ratings...`) only
# resolves from the notebook-style root (`python -m win_model.train`, or
# tests, where backend/ itself is on sys.path). Try relative first, fall back
# to plain -- this is the first place win_model has needed to reach into a
# sibling package, so there's no earlier precedent to match beyond this.
try:
    from ..ratings.player_development import team_talent_composite
except ImportError:
    from ratings.player_development import team_talent_composite

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
INTERVAL_ALPHA = 0.2  # 80% interval (10th-90th percentile)

# Written by `python -m backend.ratings.refresh_roster_projection` -- real
# current rosters + the empirical aging curve, aggregated to the same
# avg_age/avg_pts_top10/avg_production_score shape calculate_player_features()
# produces from historical data. Read-only from here: train.py never calls
# live_client itself, matching every other refresh-script/consumer split in
# this project -- see backend/AGENTS.md.
ROSTER_PROJECTION_FILE = Path(__file__).resolve().parents[1] / "outputs" / "roster_projection.json"
ROSTER_PROJECTED_FEATURES = ("avg_age", "avg_pts_top10", "avg_production_score")
# How many top-importance features get their raw per-team value carried into the
# results file (not just named in metadata). 5, not just the 2 the frontend uses
# today, so a chart tweak doesn't require another backend change. Column names
# are whatever the top features actually are this run (e.g. "SOS", "E_L") — not
# hardcoded, since a retrain can change which features rank highest.
N_FEATURE_VALUES_TO_PERSIST = 5

# Plain-language notes for features that would otherwise be a bare, easy-to-
# misread column name in the API/UI. SOS is the one that actually matters here:
# it looks like it could be a third-party rating (the way ESPN/KenPom SOS
# numbers are), but it's entirely self-calculated by this project (see
# load_schedule() in data_loader.py) — worth being explicit about so nobody
# mistakes it for an external benchmark. Covers whatever's in
# feature_values_available; anything not listed here gets a generic fallback
# rather than silently no note at all.
FEATURE_NOTES = {
    "SOS": (
        "Strength of Schedule — self-calculated, not a third-party benchmark. "
        "Computed as the season average of each opponent's Strength_Score "
        "(0.5*WIN% + 0.3*PLUS_MINUS + 0.2*roster-age-curve), entirely within "
        "this project's own pipeline — see backend/win_model/data_loader.py's "
        "load_schedule(). Null for the current forecast season: it depends on "
        "next season's opponent data, which doesn't exist yet."
    ),
    "E_L": "Eastern Conference losses (part of the East/West conference win-loss split).",
    "W_W": "Western Conference wins (part of the East/West conference win-loss split).",
    "PLUS_MINUS": "Season point differential (points scored minus points allowed).",
    "Payroll": (
        "Total team payroll for the season, in dollars. For the current forecast "
        "row specifically, this is last season's known figure carried forward "
        "unchanged — nba_api has no payroll data, and trades/signings/waivers "
        "change actual payroll all through the offseason. See "
        "metadata.roster_projection for the rest of what is/isn't real current data."
    ),
    "avg_age": "Roster average age, weighted equally across all players.",
    "avg_pts_top10": "Average points-per-game of the team's top-10 scorers.",
    "avg_production_score": "Roster average of each player's (points per game / minutes per game).",
}
_DEFAULT_FEATURE_NOTE = "No additional note recorded for this feature yet."


def _apply_roster_projection(forecast_rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Overrides the forecast row's avg_age/avg_pts_top10/avg_production_score
    with backend/ratings/refresh_roster_projection.py's output (real current
    rosters, projected one season forward via the empirical aging curve) —
    scoped to the forecast row only, per backend/AGENTS.md: this never touches
    `trainable`, so how already-completed historical seasons are trained on is
    unchanged.

    Falls back to the existing stale carry-forward value, per team, whenever
    the projection file is missing or doesn't cover that team — this pipeline
    must keep working (with an honest metadata note) even before the refresh
    script has ever been run, exactly like is_stale()/run_refresh() elsewhere.

    Returns (forecast_rows with overrides applied, a metadata dict describing
    what happened — written into run_pipeline()'s "roster_projection" key).
    """
    forecast_rows = forecast_rows.copy()
    teams = list(forecast_rows["Team"])
    meta = {
        "available": False,
        "season": None,
        "generated_at": None,
        "features_overridden": list(ROSTER_PROJECTED_FEATURES),
        "teams_projected": [],
        "teams_fallback_stale": list(teams),
        "team_talent_composite": None,
        "note": (
            "No roster projection found — every forecast-row talent feature is "
            "the stale team-level carry-forward. Run "
            "`python -m backend.ratings.refresh_roster_projection` to generate one."
        ),
    }

    if not ROSTER_PROJECTION_FILE.exists():
        return forecast_rows, meta

    try:
        payload = json.loads(ROSTER_PROJECTION_FILE.read_text())
        team_features = payload["team_features"]
    except (json.JSONDecodeError, KeyError):
        meta["note"] = f"{ROSTER_PROJECTION_FILE} is unreadable/malformed — falling back to stale carry-forward for every team."
        return forecast_rows, meta

    projected_teams = []
    for idx, team in zip(forecast_rows.index, teams):
        features = team_features.get(team)
        if not features:
            continue
        for col in ROSTER_PROJECTED_FEATURES:
            forecast_rows.loc[idx, col] = features[col]
        projected_teams.append(team)

    meta["available"] = True
    meta["season"] = payload.get("season")
    meta["generated_at"] = payload.get("generated_at")
    meta["teams_projected"] = projected_teams
    meta["teams_fallback_stale"] = [t for t in teams if t not in projected_teams]
    meta["note"] = (
        f"avg_age, avg_pts_top10, and avg_production_score for the forecast row come from "
        f"{len(projected_teams)}/{len(teams)} teams' real current rosters (season "
        f"{meta['season']}), projected one season forward via the empirical age-based "
        "development curve in backend/ratings/player_development.py. "
        + (
            f"{len(meta['teams_fallback_stale'])} team(s) had no projection available and "
            f"fell back to the stale carry-forward value: {meta['teams_fallback_stale']}."
            if meta["teams_fallback_stale"] else
            "Every forecast-row team was covered."
        )
    )

    # Explainable "how this offseason's projected talent compares league-wide"
    # composite — reuses coaching_eval's z-score machinery (see
    # player_development.team_talent_composite), not a second parallel system.
    # This is a transparency artifact for the methodology panel only; it is
    # NOT fed into the GBM — the model reads the raw recomputed feature
    # columns above, the same columns it was already trained on.
    composite_input = forecast_rows.loc[forecast_rows["Team"].isin(projected_teams),
                                         ["Team", "avg_age", "avg_pts_top10", "avg_production_score", "Payroll"]]
    if len(composite_input) > 1:
        _, breakdowns = team_talent_composite(composite_input)
        meta["team_talent_composite"] = {b.subject_name: b.to_dict() for b in breakdowns}

    return forecast_rows, meta


def run_pipeline(master_df_path=None, write_output: bool = True):
    """Returns (results_df, metadata_dict); optionally writes both to disk."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)

    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)
    forecast_rows = table[table[TARGET_COLUMN].isna()].reset_index(drop=True)

    X = trainable[FEATURE_COLUMNS]
    y = trainable[TARGET_COLUMN]
    groups = trainable["Season"]

    comparison = compare_models_walk_forward(X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    winning_search = comparison.winning_search
    fitted_pipeline = winning_search.best_estimator_  # GridSearchCV refits on all of X, y by default

    splitter = SeasonWalkForwardSplit()

    # Computed here (not after oof/forecast, where it used to live) so the top
    # feature names are available to attach raw values to both result sets below.
    importance = compute_feature_importance(fitted_pipeline, X, y, FEATURE_COLUMNS)
    top_feature_names = list(importance.head(N_FEATURE_VALUES_TO_PERSIST).index)

    # Target spread for calibration (see calibration.py) — one fixed number
    # computed once from every real historical outcome, reused identically
    # across every walk-forward fold and the live forecast below. Not
    # recomputed per fold on an expanding window: the *spread* of real NBA
    # seasons isn't a fitted parameter a fold could leak from seeing "the
    # future" of, unlike a model coefficient — it's closer to a physical
    # constant of the sport (like TOTAL_SEASON_WINS itself) than something
    # walk-forward's no-future-leakage discipline is protecting against.
    historical_std = historical_win_std(trainable[TARGET_COLUMN])

    # ---- Out-of-fold walk-forward predictions across history, for backtest display ----
    oof_frames = []
    for train_idx, test_idx in splitter.split(X, y, groups):
        fold_model = clone(fitted_pipeline)
        fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
        preds_raw = fold_model.predict(X.iloc[test_idx])
        # Every row in one fold's test_idx is the same held-out season's full
        # set of teams (SeasonWalkForwardSplit's test set is always one whole
        # season) — exactly what calibrate_season_predictions needs to be
        # calibrating a complete season, not a partial one.
        preds_calibrated = calibrate_season_predictions(preds_raw, historical_std)
        fold_df = pd.DataFrame({
            "Season": trainable.iloc[test_idx]["Season"].to_numpy() + 1,
            "Team": trainable.iloc[test_idx]["Team"].to_numpy(),
            "W": trainable.iloc[test_idx][TARGET_COLUMN].to_numpy(),
            "Pred_Wins": preds_calibrated,
            "Pred_Wins_Raw": preds_raw,
            "Pred_Wins_Lower": np.nan,
            "Pred_Wins_Upper": np.nan,
        })
        for feat in top_feature_names:
            fold_df[feat] = trainable.iloc[test_idx][feat].to_numpy()
        oof_frames.append(fold_df)
    oof = pd.concat(oof_frames, ignore_index=True)
    oof["within_threshold"] = (oof["Pred_Wins"] - oof["W"]).abs() <= 5

    walk_forward_mae_uncalibrated = float((oof["Pred_Wins_Raw"] - oof["W"]).abs().mean())
    walk_forward_mae_calibrated = float((oof["Pred_Wins"] - oof["W"]).abs().mean())
    oof = oof.drop(columns=["Pred_Wins_Raw"])  # internal-only, for the MAE comparison above

    # ---- Live forecast: most recent season's completed stats, no known outcome yet ----
    # Talent-relevant features get overridden from the real-current-roster
    # projection where available (see _apply_roster_projection) before this
    # row is used for anything — trainable/X/y above are untouched.
    forecast_rows, roster_projection_meta = _apply_roster_projection(forecast_rows)
    X_forecast = forecast_rows[FEATURE_COLUMNS]
    forecast_point = fitted_pipeline.predict(X_forecast)

    if comparison.winner == "gbm":
        lower, upper = gbm_quantile_interval(
            comparison.gbm_search, X, y, X_forecast,
            lower_q=INTERVAL_ALPHA / 2, upper_q=1 - INTERVAL_ALPHA / 2,
        )
        interval_method = "GBM native quantile regression (refits the winning model at the 10th and 90th percentiles)"
    else:
        lower, upper = bootstrap_residual_interval(
            comparison.knn_search, X, y, groups, splitter, X_forecast, alpha=INTERVAL_ALPHA,
        )
        interval_method = "Bootstrap of pooled walk-forward out-of-fold residuals (1000 resamples per team)"

    # Independently-fit quantile models aren't guaranteed to stay on the correct side
    # of the point estimate on every row ("quantile crossing") — clip rather than trust it.
    lower = np.minimum(lower, forecast_point)
    upper = np.maximum(upper, forecast_point)

    # Same calibration applied to every walk-forward fold above, applied here
    # to the live forecast row — all 30 teams' forecast-season predictions are
    # exactly "one season's full set of teams," same shape calibrate_season_predictions
    # expects. The interval gets recentered by each team's own total
    # adjustment (recenter_interval), not recalibrated independently — an
    # interval calibrated separately from its own point estimate could stop
    # bracketing it.
    forecast_point_calibrated = calibrate_season_predictions(forecast_point, historical_std)
    lower, upper = recenter_interval(forecast_point, lower, upper, forecast_point_calibrated)

    forecast = pd.DataFrame({
        "Season": forecast_rows["Season"].to_numpy() + 1,
        "Team": forecast_rows["Team"].to_numpy(),
        "W": np.nan,
        "Pred_Wins": forecast_point_calibrated,
        "Pred_Wins_Lower": lower,
        "Pred_Wins_Upper": upper,
        "within_threshold": np.nan,
    })
    for feat in top_feature_names:
        forecast[feat] = forecast_rows[feat].to_numpy()

    results = pd.concat([oof, forecast], ignore_index=True).sort_values(["Season", "Team"]).reset_index(drop=True)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_method": (
            "Season-grouped walk-forward cross-validation: trained on all seasons <= N, "
            "validated on season N+1, rolled forward one season at a time across all "
            "available history. No random k-fold CV is used anywhere in this pipeline — "
            "see backend/win_model/validation.py."
        ),
        "target_definition": (
            "Next_W: a team's actual win total in the season following the feature row's "
            "season, built with an explicit groupby-shift on W. Not the same as the master_df "
            "NWins column, which is same-season W despite its name — see features.py."
        ),
        "model_comparison": {
            "candidates": ["KNeighborsRegressor", "HistGradientBoostingRegressor (monotonic)"],
            "knn_walk_forward_mae": round(float(comparison.knn_walk_forward_mae), 3),
            "gbm_walk_forward_mae": round(float(comparison.gbm_walk_forward_mae), 3),
            "winner": comparison.winner,
            "n_walk_forward_folds": splitter.get_n_splits(X, y, groups),
        },
        "calibration": {
            "description": (
                "Two post-processing corrections applied to every prediction (backtest and "
                "live forecast alike), on top of the winning model above: (1) each season's "
                "30 predictions are rescaled around that season's own mean to match the real "
                "historical spread of NBA win totals — raw regression output is compressed "
                "toward the mean more than real seasons actually are; (2) every team is then "
                "shifted by a constant so the season's predictions sum to exactly 1,230 wins — "
                "30 teams x 82 games each, but every real game involves two teams, so exactly "
                "1,230 games are actually played league-wide. Nothing about the model itself "
                "guarantees either property on its own."
            ),
            "historical_win_std": round(historical_std, 3),
            "target_season_total_wins": TOTAL_SEASON_WINS,
            "walk_forward_mae_uncalibrated": round(walk_forward_mae_uncalibrated, 3),
            "walk_forward_mae_calibrated": round(walk_forward_mae_calibrated, 3),
            "improves_backtest_mae": walk_forward_mae_calibrated < walk_forward_mae_uncalibrated,
            "note": (
                (
                    "Calibration reduces walk-forward MAE "
                    f"({walk_forward_mae_uncalibrated:.3f} -> {walk_forward_mae_calibrated:.3f} wins) "
                    "on top of the model-selection numbers above, which are measured before any "
                    "calibration is applied."
                ) if walk_forward_mae_calibrated < walk_forward_mae_uncalibrated else (
                    "Stated plainly: calibration does NOT improve the honest backtested MAE "
                    f"({walk_forward_mae_uncalibrated:.3f} -> {walk_forward_mae_calibrated:.3f} wins, "
                    "worse or unchanged). It is still applied — matching the real 1,230-game season "
                    "total and the real historical win-total spread are correctness properties "
                    "in their own right, independent of whether they happen to lower average "
                    "per-team error — but this should not be read as \"calibration helped.\""
                )
            ),
        },
        "winning_model": {
            "type": type(fitted_pipeline.steps[-1][1]).__name__,
            "best_params": {k.split("__")[-1]: v for k, v in winning_search.best_params_.items()},
            "monotonic_increasing_features": (
                sorted(m for m in ["WIN%", "PLUS_MINUS"]) if comparison.winner == "gbm" else None
            ),
        },
        "top_feature_importance": [
            {"feature": f, "importance_mae_increase": round(float(v), 4)}
            for f, v in importance.head(15).items()
        ],
        # Which of the above also have a raw per-team value attached to each row in
        # the results file (results has 15 ranked names above but only these have a
        # matching column — see N_FEATURE_VALUES_TO_PERSIST) — e.g. for a chart
        # plotting the top-2 features against each other, per team.
        "feature_values_available": top_feature_names,
        # Plain-language caveats for the features above — SOS in particular is
        # easy to mistake for a third-party rating; see FEATURE_NOTES.
        "feature_notes": {f: FEATURE_NOTES.get(f, _DEFAULT_FEATURE_NOTE) for f in top_feature_names},
        "prediction_interval": {
            "method": interval_method,
            "coverage": f"{int((1 - INTERVAL_ALPHA) * 100)}% ({int(INTERVAL_ALPHA / 2 * 100)}th-{int((1 - INTERVAL_ALPHA / 2) * 100)}th percentile)",
        },
        "n_training_rows": int(len(trainable)),
        "n_teams": int(trainable["Team"].nunique()),
        "feature_seasons_used": sorted(int(s) for s in trainable["Season"].unique()),
        "forecast_target_season": int(forecast["Season"].iloc[0]) if len(forecast) else None,
        # Which forecast-row talent inputs are real current data vs. projected
        # vs. known-stale — see _apply_roster_projection. Historical (trainable)
        # rows are entirely unaffected; this section only ever describes the
        # live forecast row.
        "roster_projection": roster_projection_meta,
    }

    if write_output:
        results.to_csv(RESULTS_FILE, index=False)
        METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    return results, metadata


if __name__ == "__main__":
    results_df, meta = run_pipeline()
    print(f"Winner: {meta['model_comparison']['winner']} "
          f"(KNN MAE={meta['model_comparison']['knn_walk_forward_mae']}, "
          f"GBM MAE={meta['model_comparison']['gbm_walk_forward_mae']})")
    print(f"Wrote {len(results_df)} rows to {RESULTS_FILE}")
    print(f"Wrote methodology to {METADATA_FILE}")

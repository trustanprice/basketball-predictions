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

import numpy as np
import pandas as pd
from sklearn.base import clone

from .data_loader import MASTER_DF_FILE, METADATA_FILE, RESULTS_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import (
    bootstrap_residual_interval,
    compare_models_walk_forward,
    compute_feature_importance,
    gbm_quantile_interval,
)
from .validation import SeasonWalkForwardSplit

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
INTERVAL_ALPHA = 0.2  # 80% interval (10th-90th percentile)
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
    "Payroll": "Total team payroll for the season, in dollars.",
}
_DEFAULT_FEATURE_NOTE = "No additional note recorded for this feature yet."


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

    # ---- Out-of-fold walk-forward predictions across history, for backtest display ----
    oof_frames = []
    for train_idx, test_idx in splitter.split(X, y, groups):
        fold_model = clone(fitted_pipeline)
        fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
        preds = fold_model.predict(X.iloc[test_idx])
        fold_df = pd.DataFrame({
            "Season": trainable.iloc[test_idx]["Season"].to_numpy() + 1,
            "Team": trainable.iloc[test_idx]["Team"].to_numpy(),
            "W": trainable.iloc[test_idx][TARGET_COLUMN].to_numpy(),
            "Pred_Wins": preds,
            "Pred_Wins_Lower": np.nan,
            "Pred_Wins_Upper": np.nan,
        })
        for feat in top_feature_names:
            fold_df[feat] = trainable.iloc[test_idx][feat].to_numpy()
        oof_frames.append(fold_df)
    oof = pd.concat(oof_frames, ignore_index=True)
    oof["within_threshold"] = (oof["Pred_Wins"] - oof["W"]).abs() <= 5

    # ---- Live forecast: most recent season's completed stats, no known outcome yet ----
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

    forecast = pd.DataFrame({
        "Season": forecast_rows["Season"].to_numpy() + 1,
        "Team": forecast_rows["Team"].to_numpy(),
        "W": np.nan,
        "Pred_Wins": forecast_point,
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

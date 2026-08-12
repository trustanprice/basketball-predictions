"""backend/win_model/ensemble_experiment.py

One-off, honestly-reported experiment (Predictions page redesign, Part A3):
does averaging GBM and KNN's predictions (a simple ensemble) beat the
walk-forward-selected single best model on walk-forward MAE?

Uses the same feature set train.py actually trains on, so this is a fair
comparison against the model currently shipped, not a stale baseline --
that set is plain NUMERIC_FEATURES + CATEGORICAL_FEATURES; the
player_projection_features.py augmentation this used to include was
unwired from train.py after re-validation showed it no longer helps (see
that module's docstring), so it's dropped here too, to keep matching
whatever train.py actually ships. Not wired into run_pipeline() unless the
result says to be -- see run_experiment()'s "improves_mae" and
backend/AGENTS.md.

Run manually: python -m backend.win_model.ensemble_experiment
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone

from .data_loader import MASTER_DF_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward
from .validation import SeasonWalkForwardSplit

EXTENDED_NUMERIC_FEATURES = NUMERIC_FEATURES
FEATURE_COLUMNS = EXTENDED_NUMERIC_FEATURES + CATEGORICAL_FEATURES


def run_experiment(master_df_path=None) -> dict:
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    X = trainable[FEATURE_COLUMNS]
    y = trainable[TARGET_COLUMN]
    groups = trainable["Season"]

    # Reuses compare_models_walk_forward purely to get each candidate's own
    # walk-forward-tuned hyperparameters (best_estimator_) -- the ensemble
    # comparison below refits both at those fixed hyperparameters per fold,
    # same walk-forward splitter, so this is an apples-to-apples comparison
    # against the single-model numbers already reported elsewhere.
    comparison = compare_models_walk_forward(X, y, groups, EXTENDED_NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    splitter = SeasonWalkForwardSplit()

    gbm_preds, knn_preds, actuals = [], [], []
    for train_idx, test_idx in splitter.split(X, y, groups):
        gbm_fold = clone(comparison.gbm_search.best_estimator_)
        knn_fold = clone(comparison.knn_search.best_estimator_)
        gbm_fold.fit(X.iloc[train_idx], y.iloc[train_idx])
        knn_fold.fit(X.iloc[train_idx], y.iloc[train_idx])
        gbm_preds.extend(gbm_fold.predict(X.iloc[test_idx]))
        knn_preds.extend(knn_fold.predict(X.iloc[test_idx]))
        actuals.extend(y.iloc[test_idx].to_numpy())

    gbm_preds = np.array(gbm_preds)
    knn_preds = np.array(knn_preds)
    actuals = np.array(actuals)
    ensemble_preds = (gbm_preds + knn_preds) / 2

    gbm_mae = float(np.mean(np.abs(gbm_preds - actuals)))
    knn_mae = float(np.mean(np.abs(knn_preds - actuals)))
    ensemble_mae = float(np.mean(np.abs(ensemble_preds - actuals)))
    single_best_name = "gbm" if gbm_mae <= knn_mae else "knn"
    single_best_mae = min(gbm_mae, knn_mae)

    return {
        "hypothesis": (
            "Averaging GBM and KNN's predictions (simple ensemble) beats the "
            "walk-forward-selected single best model."
        ),
        "gbm_walk_forward_mae": round(gbm_mae, 3),
        "knn_walk_forward_mae": round(knn_mae, 3),
        "ensemble_walk_forward_mae": round(ensemble_mae, 3),
        "single_best_model": single_best_name,
        "single_best_mae": round(single_best_mae, 3),
        "improves_mae": bool(ensemble_mae < single_best_mae),
        "n_rows": int(len(actuals)),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(
        f"GBM MAE: {result['gbm_walk_forward_mae']}, KNN MAE: {result['knn_walk_forward_mae']}, "
        f"Ensemble MAE: {result['ensemble_walk_forward_mae']}"
    )
    print(f"Ensemble {verdict} over single best ({result['single_best_model']}, {result['single_best_mae']}).")

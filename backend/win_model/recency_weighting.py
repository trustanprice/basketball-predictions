"""backend/win_model/recency_weighting.py

Task 8: does exponentially down-weighting older training rows (recency
weighting) improve walk-forward MAE, tuned via the existing walk-forward grid
search rather than a hand-picked decay rate?

weight = decay_rate ** seasons_ago, where seasons_ago is computed relative to
the season being predicted IN EACH WALK-FORWARD FOLD, not an absolute
calendar year -- see model.recency_sample_weight()'s docstring for exactly
why anchoring the formula to the max season present in whatever's actually
being fit (a GridSearchCV-internal fold slice, or a final full-data refit)
makes this automatically fold-relative, with no separate per-fold bookkeeping
needed here.

GBM-only mechanism: KNeighborsRegressor.fit(X, y) has no sample_weight
parameter at all (verified directly against its signature), so KNN keeps
competing unweighted, exactly as before -- Task 8 only changes how the GBM
candidate is trained, never KNN. Since GBM already beats KNN by a wide margin
in this project's history (8.3 vs 6.4 MAE), and GBM is the model actually
deployed, comparing decay-weighted GBM against plain (decay_rate=1.0) GBM,
both walk-forward-tuned the same way, is the honest apples-to-apples test --
not a comparison against KNN, which recency weighting can't touch.

Run manually: python -m backend.win_model.recency_weighting
"""

from __future__ import annotations

import pandas as pd

from .data_loader import MASTER_DF_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import DEFAULT_DECAY_RATES, build_preprocessor, tune_gbm_recency
from .roster_change_features import ROSTER_CHANGE_COLUMN, build_roster_change_features
from .validation import SeasonWalkForwardSplit


def _run_one(X, y, groups, numeric_features, decay_rates=DEFAULT_DECAY_RATES) -> dict:
    preprocessor = build_preprocessor(numeric_features, CATEGORICAL_FEATURES)
    splitter = SeasonWalkForwardSplit()
    results = tune_gbm_recency(preprocessor, X, y, groups, splitter, numeric_features, decay_rates)

    baseline = next(r for r in results if r.decay_rate == 1.0)
    best = min(results, key=lambda r: r.walk_forward_mae)

    return {
        "by_decay_rate": [
            {
                "decay_rate": r.decay_rate,
                "walk_forward_mae": round(r.walk_forward_mae, 3),
                "per_fold_mae": [round(m, 3) for m in r.per_fold_mae()],
                "best_params": {k.split("__")[-1]: v for k, v in r.search.best_params_.items()},
            }
            for r in results
        ],
        "baseline_decay_rate_1_0_mae": round(baseline.walk_forward_mae, 3),
        "best_decay_rate": best.decay_rate,
        "best_walk_forward_mae": round(best.walk_forward_mae, 3),
        "improves_mae": bool(best.walk_forward_mae < baseline.walk_forward_mae),
    }


def run_experiment(master_df_path=None, decay_rates=DEFAULT_DECAY_RATES) -> dict:
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    changes = build_roster_change_features(master_df_path or MASTER_DF_FILE)
    trainable = trainable.merge(changes, on=["Season", "Team"], how="left")
    trainable[ROSTER_CHANGE_COLUMN] = trainable[ROSTER_CHANGE_COLUMN].fillna(0.0)

    y = trainable[TARGET_COLUMN]
    groups = trainable["Season"]

    isolated_X = trainable[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    isolated = _run_one(isolated_X, y, groups, NUMERIC_FEATURES, decay_rates)

    stacked_numeric = NUMERIC_FEATURES + [ROSTER_CHANGE_COLUMN]
    stacked_X = trainable[stacked_numeric + CATEGORICAL_FEATURES]
    stacked = _run_one(stacked_X, y, groups, stacked_numeric, decay_rates)

    return {
        "hypothesis": (
            "Exponentially down-weighting older training rows (weight = decay_rate ** "
            "seasons_ago, fold-relative) improves GBM's walk-forward MAE, tuned via the "
            "existing walk-forward grid search rather than a hand-picked decay rate."
        ),
        "isolated": isolated,
        "stacked": stacked,
        "improves_mae": stacked["improves_mae"],
    }


if __name__ == "__main__":
    result = run_experiment()
    for label in ("isolated", "stacked"):
        section = result[label]
        print(f"--- {label} ---")
        for row in section["by_decay_rate"]:
            print(f"  decay_rate={row['decay_rate']}: MAE={row['walk_forward_mae']} "
                  f"per_fold={row['per_fold_mae']}")
        print(f"  baseline (decay_rate=1.0): {section['baseline_decay_rate_1_0_mae']}")
        print(f"  best: decay_rate={section['best_decay_rate']} MAE={section['best_walk_forward_mae']}")
        print(f"  improves: {section['improves_mae']}")
        print()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Recency weighting (stacked, the decisive test) {verdict} walk-forward MAE.")

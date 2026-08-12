"""backend/win_model/model.py

Two standalone regressors — KNN and a monotonic-constrained gradient-boosted tree —
are each hyperparameter-tuned via walk-forward CV and benchmarked against each
other on walk-forward MAE; the better one is kept as the deployed model.

The previous ElasticNet -> KNN handoff (linear-model coefficients repurposed as KNN
distance weights) is retired rather than kept as a third candidate: it's the
mechanism the project brief identifies as the likely source of the model's
regression-to-mean/over-optimism behavior, and there's no walk-forward-honest way
to keep "ElasticNet picks features -> KNN uses them" without re-selecting features
inside every fold, which is a lot of added complexity for a mechanism already
flagged as theoretically shaky. Feature selection is left to whichever model wins
(GBM does this natively via split gain; KNN uses the full feature set).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import make_column_transformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from .validation import SeasonWalkForwardSplit

# Features where a higher value should never translate into a *lower* predicted
# win total, all else equal. Guards the GBM against learning a locally spurious
# inverse relationship out of a small (~270-row), noisy dataset.
MONOTONIC_INCREASING_FEATURES = {"WIN%", "PLUS_MINUS"}


# ===========================
#   PREPROCESSOR BUILDER
# ===========================
def build_preprocessor(numeric_features, categorical_features=None):
    """Impute + robust-scale numeric features; one-hot encode categoricals, if any.

    Robust scaling (median/IQR) rather than standardization, since these inputs
    (payroll, counting stats) are outlier-prone. `categorical_features` is optional
    since the win model currently has none (see features.py for why `Season` was
    dropped as a modeled feature).
    """
    numeric_transformer = make_pipeline(
        SimpleImputer(strategy="mean"),
        RobustScaler()
    )
    transformers = [(numeric_transformer, numeric_features)]

    if categorical_features:
        categorical_transformer = make_pipeline(
            SimpleImputer(strategy="most_frequent"),
            OneHotEncoder(handle_unknown="infrequent_if_exist", drop="first")
        )
        transformers.append((categorical_transformer, categorical_features))

    return make_column_transformer(*transformers, remainder="drop")


def _monotonic_constraints(numeric_features):
    return [1 if f in MONOTONIC_INCREASING_FEATURES else 0 for f in numeric_features]


# ===========================
#   CANDIDATE MODELS
# ===========================
def build_knn(preprocessor, X, y, groups, splitter):
    """Grid-search a KNN regressor, tuned via walk-forward CV (not random folds)."""
    pipeline = make_pipeline(preprocessor, KNeighborsRegressor())
    param_grid = {
        "kneighborsregressor__n_neighbors": [3, 5, 7, 10, 15],
        "kneighborsregressor__weights": ["uniform", "distance"],
        "kneighborsregressor__metric": ["euclidean", "manhattan"],
    }
    search = GridSearchCV(
        pipeline, param_grid, cv=splitter, scoring="neg_mean_absolute_error", n_jobs=-1,
    )
    search.fit(X, y, groups=groups)
    return search


def build_gbm(preprocessor, X, y, groups, splitter, numeric_features):
    """Grid-search a monotonic-constrained HistGradientBoostingRegressor via walk-forward CV."""
    monotonic_cst = _monotonic_constraints(numeric_features)
    pipeline = make_pipeline(
        preprocessor,
        HistGradientBoostingRegressor(monotonic_cst=monotonic_cst, random_state=42),
    )
    param_grid = {
        "histgradientboostingregressor__max_leaf_nodes": [7, 15, 31],
        "histgradientboostingregressor__learning_rate": [0.03, 0.1, 0.2],
        "histgradientboostingregressor__min_samples_leaf": [5, 10, 20],
    }
    search = GridSearchCV(
        pipeline, param_grid, cv=splitter, scoring="neg_mean_absolute_error", n_jobs=-1,
    )
    search.fit(X, y, groups=groups)
    return search


# ===========================
#   RECENCY-WEIGHTED GBM (see recency_weighting.py for the full experiment)
# ===========================
# KNeighborsRegressor.fit(X, y) has no sample_weight parameter at all (verified
# directly against its signature -- this isn't a documentation gap, KNN
# structurally cannot be recency-weighted this way). Recency weighting is a
# GBM-only mechanism here; build_knn above is untouched and still competes on
# its own, unweighted, exactly as before.
DEFAULT_DECAY_RATES = (1.0, 0.95, 0.85, 0.7)  # 1.0 = no weighting -- today's behavior, a real candidate


def recency_sample_weight(seasons, decay_rate: float) -> np.ndarray:
    """weight = decay_rate ** seasons_ago, anchored to the max season actually
    present in `seasons` -- for a GridSearchCV-internal fold's sliced training
    rows, that max IS the fold's train_season_cutoff (the season right before
    the one being predicted), which is exactly "fold-relative, not absolute
    calendar year" recency: this formula never needs to know how many seasons
    exist in the full dataset, only what's in front of it in this specific fit.

    Precomputing one vector against the FULL season array and letting
    GridSearchCV auto-slice it per fold (rather than recomputing fresh inside
    each fold) still gives the right *relative* weights within any fold's
    slice -- the sliced values differ from a from-scratch fold-relative
    computation only by one constant multiplicative factor per fold (the
    global anchor vs. that fold's own cutoff), and a uniform rescale of every
    sample's weight within a single fit doesn't change what
    HistGradientBoostingRegressor learns with this project's default
    l2_regularization=0 (verified empirically: predictions identical to
    floating-point noise, ~1e-8, under an arbitrary 7.3x uniform rescale of
    otherwise-identical weights). Confirmed separately that GridSearchCV
    actually requires the `histgradientboostingregressor__sample_weight`
    step-prefixed form here -- a bare `sample_weight=` kwarg raises
    ValueError in this sklearn version (1.5.0), not a silent misroute, so a
    missing prefix fails loudly rather than fitting on unweighted data by
    accident.
    """
    seasons = np.asarray(seasons)
    return decay_rate ** (seasons.max() - seasons)


@dataclass
class RecencyGBMResult:
    decay_rate: float
    search: GridSearchCV
    walk_forward_mae: float

    def per_fold_mae(self) -> list[float]:
        """MAE on each walk-forward fold, for this result's own best
        hyperparameter combination -- lets a caller see whether an
        improvement is concentrated in a few folds or spread evenly, not just
        the aggregate `walk_forward_mae`."""
        cv_results = self.search.cv_results_
        n_splits = sum(1 for k in cv_results if k.startswith("split") and k.endswith("_test_score"))
        return [
            float(-cv_results[f"split{i}_test_score"][self.search.best_index_])
            for i in range(n_splits)
        ]


def tune_gbm_recency(
    preprocessor, X, y, groups, splitter, numeric_features, decay_rates=DEFAULT_DECAY_RATES,
) -> list[RecencyGBMResult]:
    """Same grid-searched GBM as build_gbm, tuned separately once per candidate
    `decay_rate` -- decay_rate itself can't be a literal GridSearchCV param
    (it controls a sample_weight vector computed outside the estimator, not a
    step hyperparameter), so it's selected the same way this project already
    picks between KNN and GBM: run the full walk-forward search per candidate,
    keep whichever has the best honest score. decay_rate=1.0 is included by
    default so "no weighting wins" is a real, expressible outcome.
    """
    monotonic_cst = _monotonic_constraints(numeric_features)
    pipeline = make_pipeline(
        preprocessor,
        HistGradientBoostingRegressor(monotonic_cst=monotonic_cst, random_state=42),
    )
    param_grid = {
        "histgradientboostingregressor__max_leaf_nodes": [7, 15, 31],
        "histgradientboostingregressor__learning_rate": [0.03, 0.1, 0.2],
        "histgradientboostingregressor__min_samples_leaf": [5, 10, 20],
    }
    results = []
    for decay_rate in decay_rates:
        weight = recency_sample_weight(groups, decay_rate)
        search = GridSearchCV(
            clone(pipeline), param_grid, cv=splitter, scoring="neg_mean_absolute_error", n_jobs=-1,
        )
        search.fit(X, y, groups=groups, histgradientboostingregressor__sample_weight=weight)
        results.append(RecencyGBMResult(decay_rate=decay_rate, search=search, walk_forward_mae=-search.best_score_))
    return results


@dataclass
class ModelComparison:
    winner: str  # "knn" or "gbm"
    knn_search: GridSearchCV
    gbm_search: GridSearchCV
    knn_walk_forward_mae: float
    gbm_walk_forward_mae: float

    @property
    def winning_search(self) -> GridSearchCV:
        return self.knn_search if self.winner == "knn" else self.gbm_search


def compare_models_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str] | None = None,
    min_train_seasons: int = 1,
) -> ModelComparison:
    """Tune KNN and GBM independently via walk-forward CV, and keep whichever has the
    lower walk-forward MAE (`best_score_` from GridSearchCV, evaluated only on
    held-out future seasons) — never in-sample fit."""
    splitter = SeasonWalkForwardSplit(min_train_seasons=min_train_seasons)
    preprocessor = build_preprocessor(numeric_features, categorical_features)

    knn_search = build_knn(preprocessor, X, y, groups, splitter)
    gbm_search = build_gbm(preprocessor, X, y, groups, splitter, numeric_features)

    knn_mae = -knn_search.best_score_
    gbm_mae = -gbm_search.best_score_
    winner = "knn" if knn_mae <= gbm_mae else "gbm"

    return ModelComparison(
        winner=winner,
        knn_search=knn_search,
        gbm_search=gbm_search,
        knn_walk_forward_mae=knn_mae,
        gbm_walk_forward_mae=gbm_mae,
    )


# ===========================
#   PREDICTION INTERVALS
# ===========================
def gbm_quantile_interval(gbm_search: GridSearchCV, X, y, X_predict, lower_q=0.1, upper_q=0.9, sample_weight=None):
    """Native quantile regression: refit the winning GBM's tuned pipeline at two
    quantiles instead of the mean, reusing its selected hyperparameters.

    `sample_weight`, if given, must already be aligned to X's rows (e.g. from
    recency_sample_weight()) -- only relevant if `gbm_search` was itself tuned
    with recency weighting, so both quantile refits stay consistent with how
    the point-estimate model was actually selected, not silently unweighted.
    """
    bounds = {}
    for name, q in [("lower", lower_q), ("upper", upper_q)]:
        pipeline = clone(gbm_search.best_estimator_)
        pipeline.set_params(
            histgradientboostingregressor__loss="quantile",
            histgradientboostingregressor__quantile=q,
        )
        fit_kwargs = {}
        if sample_weight is not None:
            fit_kwargs["histgradientboostingregressor__sample_weight"] = sample_weight
        pipeline.fit(X, y, **fit_kwargs)
        bounds[name] = pipeline.predict(X_predict)
    return bounds["lower"], bounds["upper"]


def bootstrap_residual_interval(
    search: GridSearchCV,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    splitter: SeasonWalkForwardSplit,
    X_predict: pd.DataFrame,
    n_bootstrap: int = 1000,
    alpha: float = 0.2,
    random_state: int = 42,
):
    """For a model without a native quantile mode (KNN): pool out-of-fold walk-forward
    residuals across every fold, bootstrap-resample them, and add the resampled
    residual to each point prediction to get an empirical interval."""
    rng = np.random.default_rng(random_state)
    residuals = []
    for train_idx, test_idx in splitter.split(X, y, groups):
        fold_model = clone(search.best_estimator_)
        fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
        preds = fold_model.predict(X.iloc[test_idx])
        residuals.extend((y.iloc[test_idx].to_numpy() - preds).tolist())
    residuals = np.array(residuals)

    point_preds = search.best_estimator_.predict(X_predict)
    lower = np.empty(len(point_preds))
    upper = np.empty(len(point_preds))
    for i, p in enumerate(point_preds):
        sim = p + rng.choice(residuals, size=n_bootstrap, replace=True)
        lower[i] = np.quantile(sim, alpha / 2)
        upper[i] = np.quantile(sim, 1 - alpha / 2)
    return lower, upper


# ===========================
#   EXPLAINABILITY
# ===========================
def compute_feature_importance(fitted_pipeline, X, y, feature_names, n_repeats=20, random_state=42):
    """Permutation importance against the training set. Used for both candidates —
    HistGradientBoostingRegressor doesn't expose `feature_importances_` the way
    tree-ensemble models like RandomForest do, so this is the one method that works
    identically regardless of which model wins."""
    result = permutation_importance(
        fitted_pipeline, X, y,
        n_repeats=n_repeats, random_state=random_state, scoring="neg_mean_absolute_error",
    )
    return pd.Series(result.importances_mean, index=feature_names).sort_values(ascending=False)

# src/model.py

from sklearn.pipeline import make_pipeline
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import GridSearchCV
import pandas as pd


# ===========================
#   PREPROCESSOR BUILDER
# ===========================
def build_preprocessor(numeric_features, categorical_features):
    """
    Create preprocessing pipeline for numeric and categorical features.
    - Numeric: impute mean, then robust scale (less sensitive to outliers).
    - Categorical: impute most frequent, then one-hot encode.
    """
    numeric_transformer = make_pipeline(
        SimpleImputer(strategy="mean"),
        RobustScaler()
    )

    categorical_transformer = make_pipeline(
        SimpleImputer(strategy="most_frequent"),
        OneHotEncoder(handle_unknown="infrequent_if_exist", drop="first")
    )

    preprocessor = make_column_transformer(
        (numeric_transformer, numeric_features),
        (categorical_transformer, categorical_features),
        remainder="drop"
    )
    return preprocessor


# ===========================
#   ELASTICNET MODEL
# ===========================
def build_elasticnet(preprocessor, X_train, y_train):
    """
    Build and tune ElasticNet regression model with preprocessing.
    Returns the fitted GridSearchCV object.
    """
    elasticnet = ElasticNet(max_iter=10000, random_state=42)

    param_grid = {
        "elasticnet__alpha": [0.01, 0.1, 1.0, 10.0],
        "elasticnet__l1_ratio": [0.1, 0.5, 0.9]
    }

    pipeline = make_pipeline(preprocessor, elasticnet)

    model = GridSearchCV(
        pipeline,
        param_grid,
        cv=10,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        verbose=1
    )

    model.fit(X_train, y_train)
    return model


def extract_feature_weights(elasticnet_model, feature_names):
    """
    Extract normalized absolute coefficients from a fitted ElasticNet model.
    Returns a dict: {feature: weight}.
    """
    coefs = elasticnet_model.best_estimator_[-1].coef_
    weights = dict(zip(feature_names, abs(coefs)))

    # Normalize to range 0–1
    max_w = max(weights.values()) if weights else 1.0
    weights = {k: v / max_w for k, v in weights.items()}
    return weights


# ===========================
#   KNN MODEL
# ===========================
def build_knn(preprocessor, X_train, y_train, feature_weights=None, recency_col=None):
    """
    Build and tune KNN regressor with preprocessing.
    - Supports optional feature weighting (dict from ElasticNet).
    - Supports optional recency weighting (higher weight for recent seasons).
    """
    X_train_mod = X_train.copy()

    # Apply feature weights if provided
    if feature_weights:
        for col, w in feature_weights.items():
            if col in X_train_mod.columns:
                X_train_mod[col] *= w

    # Build base KNN
    knn = KNeighborsRegressor()

    param_grid = {
        "kneighborsregressor__n_neighbors": [3, 5, 7, 10],
        "kneighborsregressor__weights": ["uniform", "distance"],
        "kneighborsregressor__metric": ["euclidean", "manhattan", "minkowski"],
        "kneighborsregressor__p": [1, 2]
    }

    pipeline = make_pipeline(preprocessor, knn)

    model = GridSearchCV(
        pipeline,
        param_grid,
        cv=5,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        verbose=1
    )

    # Build sample weights for recency if specified
    fit_kwargs = {}
    if recency_col and recency_col in X_train_mod.columns:
        # Linear scaling with year difference (e.g. 2016=1.0, 2025≈2.0)
        sample_weights = X_train_mod[recency_col].apply(lambda yr: 1 + 0.1 * (yr - X_train_mod[recency_col].min()))
        fit_kwargs["sample_weight"] = sample_weights

    model.fit(X_train_mod, y_train, **fit_kwargs)
    return model

# src/model.py

from sklearn.pipeline import make_pipeline
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import GridSearchCV

# --- Build Preprocessor ---
def build_preprocessor(numeric_features, categorical_features):
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


# --- ElasticNet Model (full features) ---
def build_elasticnet(preprocessor, X_train, y_train):
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


# --- KNN Model (reduced features) ---
def build_knn(preprocessor, X_train, y_train):
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
        cv=10,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        verbose=1
    )

    model.fit(X_train, y_train)
    return model

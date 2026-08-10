import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api import dependencies
from backend.api.main import app

PREDICTIONS_DF = pd.DataFrame([
    {"Season": 2025, "Team": "Boston Celtics", "W": 61.0, "Pred_Wins": 58.5, "Pred_Wins_Lower": 50.0, "Pred_Wins_Upper": 65.0, "within_threshold": True, "SOS": 0.02, "E_L": 15.0},
    {"Season": 2025, "Team": "Miami Heat", "W": 37.0, "Pred_Wins": 40.0, "Pred_Wins_Lower": 32.0, "Pred_Wins_Upper": 48.0, "within_threshold": True, "SOS": -0.01, "E_L": 22.0},
    # 2026 rows mirror a real, pre-existing data gap: SOS is NaN for the current
    # forecast season (see backend/AGENTS.md) — deliberately included here so
    # tests catch a regression in the missing-value handling, not just the happy path.
    {"Season": 2026, "Team": "Boston Celtics", "W": np.nan, "Pred_Wins": 47.0, "Pred_Wins_Lower": 36.0, "Pred_Wins_Upper": 58.0, "within_threshold": np.nan, "SOS": np.nan, "E_L": 13.0},
    {"Season": 2026, "Team": "Miami Heat", "W": np.nan, "Pred_Wins": 42.0, "Pred_Wins_Lower": 33.0, "Pred_Wins_Upper": 51.0, "within_threshold": np.nan, "SOS": np.nan, "E_L": 24.0},
])

MODEL_METADATA = {
    "generated_at": "2026-08-08T23:10:07+00:00",
    "validation_method": "Season-grouped walk-forward cross-validation...",
    "target_definition": "Next_W: a team's actual win total in the season following...",
    "model_comparison": {
        "candidates": ["KNeighborsRegressor", "HistGradientBoostingRegressor (monotonic)"],
        "knn_walk_forward_mae": 8.283,
        "gbm_walk_forward_mae": 6.781,
        "winner": "gbm",
        "n_walk_forward_folds": 8,
    },
    "winning_model": {
        "type": "HistGradientBoostingRegressor",
        "best_params": {"learning_rate": 0.1, "max_leaf_nodes": 7, "min_samples_leaf": 10},
        "monotonic_increasing_features": ["PLUS_MINUS", "WIN%"],
    },
    "top_feature_importance": [{"feature": "SOS", "importance_mae_increase": 6.62}],
    "prediction_interval": {"method": "GBM native quantile regression", "coverage": "80%"},
    "n_training_rows": 270,
    "n_teams": 30,
    "feature_seasons_used": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024],
    "forecast_target_season": 2026,
    "feature_values_available": ["SOS", "E_L"],
    "feature_notes": {
        "SOS": "Strength of Schedule — self-calculated, not a third-party benchmark.",
        "E_L": "Eastern Conference losses.",
    },
}

_SAMPLE_COMPONENT = {
    "name": "True Shooting %", "column": "TS_PCT", "raw_value": 0.61,
    "z_score": 1.2, "weight": 0.3, "higher_is_better": True, "contribution": 0.36,
}

PLAYER_POWER_RANKINGS = {
    "season": "2025-26",
    "generated_at": "2026-08-08T00:00:00+00:00",
    "methodology_note": "Offense: TS% + usage-adjusted scoring + AST% + TOV%...",
    "n_qualified_players": 150,
    "offense": [
        {"subject_id": 1, "subject_name": "Player One", "composite_score": 2.1, "components": [_SAMPLE_COMPONENT]},
    ],
    "defense": [
        {"subject_id": 2, "subject_name": "Player Two", "composite_score": 1.8, "components": [_SAMPLE_COMPONENT]},
    ],
}

COACH_TEAM_SEASONS = pd.DataFrame([
    {
        "Season": 2016, "Team": "San Antonio Spurs", "Coach": "Gregg Popovich", "WIN%": 0.817,
        "talent_z_score": -1.33, "implied_win_pct": 0.304, "wins_above_expectation": 0.513,
        "talent_breakdown": {"subject_id": "San Antonio Spurs", "subject_name": "San Antonio Spurs", "composite_score": -1.33, "components": [_SAMPLE_COMPONENT]},
    },
    {
        "Season": 2017, "Team": "San Antonio Spurs", "Coach": "Gregg Popovich", "WIN%": 0.744,
        "talent_z_score": -0.81, "implied_win_pct": 0.381, "wins_above_expectation": 0.363,
        "talent_breakdown": {"subject_id": "San Antonio Spurs", "subject_name": "San Antonio Spurs", "composite_score": -0.81, "components": [_SAMPLE_COMPONENT]},
    },
])

COACH_CAREER_SUMMARY = pd.DataFrame([
    {
        "Coach": "Gregg Popovich", "seasons_coached": 2, "teams_coached": ["San Antonio Spurs"],
        "n_teams": 1, "avg_wins_above_expectation": 0.438, "avg_actual_win_pct": 0.7805, "avg_implied_win_pct": 0.3425,
    },
])


@pytest.fixture
def client():
    app.dependency_overrides[dependencies.get_predictions_df] = lambda: PREDICTIONS_DF
    app.dependency_overrides[dependencies.get_model_metadata] = lambda: MODEL_METADATA
    app.dependency_overrides[dependencies.get_player_power_rankings] = lambda: PLAYER_POWER_RANKINGS
    app.dependency_overrides[dependencies.get_coach_team_seasons] = lambda: COACH_TEAM_SEASONS
    app.dependency_overrides[dependencies.get_coach_career_summary] = lambda: COACH_CAREER_SUMMARY
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()

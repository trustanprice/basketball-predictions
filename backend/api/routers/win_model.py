"""backend/api/routers/win_model.py — team win predictions + methodology.

Reads backend/win_model/train.py's already-written output (test_results.csv,
model_metadata.json). Never retrains or recomputes a prediction per request.
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from backend.api import schemas
from backend.api.dependencies import get_model_metadata, get_predictions_df

router = APIRouter(prefix="/api/win-model", tags=["win-model"])


def _none_if_nan(value):
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else value


def _row_to_prediction(row, feature_names: list[str]) -> schemas.TeamPrediction:
    return schemas.TeamPrediction(
        team=row["Team"],
        season=int(row["Season"]),
        predicted_wins=float(row["Pred_Wins"]),
        predicted_wins_lower=_none_if_nan(row.get("Pred_Wins_Lower")),
        predicted_wins_upper=_none_if_nan(row.get("Pred_Wins_Upper")),
        actual_wins=_none_if_nan(row.get("W")),
        top_features={f: float(row[f]) for f in feature_names if f in row and not math.isnan(row[f])},
    )


@router.get("/predictions", response_model=list[schemas.TeamPrediction])
def list_predictions(
    df: pd.DataFrame = Depends(get_predictions_df),
    metadata: dict = Depends(get_model_metadata),
):
    """All 30 teams' predictions for the latest available season (no full
    methodology attached — see /predictions/{team} for that — but each team's
    top_features IS included, since that's what a cross-team chart needs)."""
    feature_names = metadata.get("feature_values_available", [])
    latest_season = df["Season"].max()
    latest = df[df["Season"] == latest_season]
    return [_row_to_prediction(row, feature_names) for _, row in latest.iterrows()]


@router.get("/predictions/{team}", response_model=schemas.TeamPredictionDetail)
def get_team_prediction(
    team: str,
    df: pd.DataFrame = Depends(get_predictions_df),
    metadata: dict = Depends(get_model_metadata),
):
    """One team's latest-season prediction plus the full 'how this was
    calculated' explanation — self-contained, no second call needed."""
    latest_season = df["Season"].max()
    match = df[(df["Season"] == latest_season) & (df["Team"] == team)]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"No prediction found for team {team!r}")

    feature_names = metadata.get("feature_values_available", [])
    prediction = _row_to_prediction(match.iloc[0], feature_names)
    return schemas.TeamPredictionDetail(**prediction.model_dump(), methodology=metadata)


@router.get("/methodology", response_model=schemas.ModelMetadata)
def get_methodology(metadata: dict = Depends(get_model_metadata)):
    """The win model's methodology on its own, for clients that don't need it
    duplicated inline with every team."""
    return metadata

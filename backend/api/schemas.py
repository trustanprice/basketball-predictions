"""backend/api/schemas.py

Pydantic response models. Field names are deliberately reshaped from the
internal dataframe/dict column names (e.g. "WIN%" -> actual_win_pct) into
JSON-friendly snake_case — this is presentation shaping, not logic duplication;
the values themselves come straight from backend.win_model / backend.ratings.
"""

from __future__ import annotations

from pydantic import BaseModel


class ModelMetadata(BaseModel):
    """Mirrors backend/win_model/train.py's model_metadata.json verbatim."""
    generated_at: str
    validation_method: str
    target_definition: str
    model_comparison: dict
    winning_model: dict
    top_feature_importance: list[dict]
    prediction_interval: dict
    n_training_rows: int
    n_teams: int
    feature_seasons_used: list[int]
    forecast_target_season: int | None = None
    feature_values_available: list[str] = []
    feature_notes: dict[str, str] = {}
    roster_projection: dict = {}
    calibration: dict = {}
    backtest_accuracy: dict = {}


class TeamPrediction(BaseModel):
    """One row of backend/win_model's results table — no methodology attached
    (see TeamPredictionDetail for that). Used in the list endpoint so a 30-team
    response isn't carrying the ~2KB methodology blob 30 times over.

    top_features holds the raw per-team value of whichever features rank highest
    by permutation importance this run (names given by ModelMetadata.top_feature_importance
    / feature_values_available — not hardcoded, since a retrain can change which
    features rank highest). Intended for exactly this: a chart plotting a team's
    most-influential inputs against each other, without claiming to show the
    full ~48-feature explanation — see backend/AGENTS.md before assuming these
    two names are stable."""
    team: str
    season: int
    predicted_wins: float
    predicted_wins_lower: float | None = None
    predicted_wins_upper: float | None = None
    actual_wins: float | None = None
    top_features: dict[str, float] = {}


class TeamPredictionDetail(TeamPrediction):
    """Single-team view: the prediction plus the full "how this was calculated"
    explanation, per the transparency requirement — self-contained, no second
    API call needed to explain the number."""
    methodology: ModelMetadata


class RatingComponent(BaseModel):
    """One weighted input into a composite score — reproducible by hand from
    these five fields, per backend/AGENTS.md's ratings/ transparency requirement."""
    name: str
    column: str
    raw_value: float | int | str
    z_score: float
    weight: float
    higher_is_better: bool
    contribution: float


class RatingBreakdown(BaseModel):
    subject_id: int | str
    subject_name: str
    composite_score: float
    components: list[RatingComponent]


class PlayerPowerRankings(BaseModel):
    season: str
    generated_at: str
    methodology_note: str
    n_qualified_players: int
    offense: list[RatingBreakdown]
    defense: list[RatingBreakdown]


class PlayerProjectedLeaders(BaseModel):
    """A PRESEASON PROJECTION, not a live in-season ranking — `note` states
    that plainly and must always be surfaced alongside these numbers, not
    just carried in the payload. Same RatingBreakdown shape/composite as
    PlayerPowerRankings (see backend/ratings/refresh_player_projections.py:
    projected numbers run through the exact same top_offensive_players/
    top_defensive_players composite, not a second ranking system)."""
    season: str
    generated_at: str
    note: str
    historical_seasons_used: list[str]
    n_players_projected: int
    n_qualified_players: int
    offense: list[RatingBreakdown]
    defense: list[RatingBreakdown]


class CoachTeamSeason(BaseModel):
    """One team-season: actual win% vs. roster-talent-implied win%, with the
    talent composite's full breakdown attached."""
    season: int
    team: str
    coach: str
    actual_win_pct: float
    implied_win_pct: float
    wins_above_expectation: float
    talent_breakdown: RatingBreakdown


class CoachCareerSummary(BaseModel):
    coach: str
    seasons_coached: int
    teams_coached: list[str]
    n_teams: int
    avg_wins_above_expectation: float
    avg_actual_win_pct: float
    avg_implied_win_pct: float

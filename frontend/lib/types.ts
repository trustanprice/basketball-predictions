/**
 * Mirrors backend/api/schemas.py field-for-field. Keep these two in sync by
 * hand — there's no shared schema generation between the two projects yet.
 */

export interface ModelMetadata {
  generated_at: string;
  validation_method: string;
  target_definition: string;
  model_comparison: {
    candidates: string[];
    knn_walk_forward_mae: number;
    gbm_walk_forward_mae: number;
    winner: string;
    n_walk_forward_folds: number;
  };
  winning_model: {
    type: string;
    best_params: Record<string, unknown>;
    monotonic_increasing_features: string[] | null;
  };
  top_feature_importance: { feature: string; importance_mae_increase: number }[];
  prediction_interval: { method: string; coverage: string };
  n_training_rows: number;
  n_teams: number;
  feature_seasons_used: number[];
  forecast_target_season: number | null;
  feature_values_available: string[];
  feature_notes: Record<string, string>;
  calibration: {
    description: string;
    historical_win_std: number;
    target_season_total_wins: number;
    walk_forward_mae_uncalibrated: number;
    walk_forward_mae_calibrated: number;
    improves_backtest_mae: boolean;
    note: string;
  };
  roster_projection: {
    available: boolean;
    season: string | null;
    generated_at: string | null;
    features_overridden: string[];
    teams_projected: string[];
    teams_fallback_stale: string[];
    team_talent_composite: Record<string, RatingBreakdown> | null;
    note: string;
  };
}

export interface TeamPrediction {
  team: string;
  season: number;
  predicted_wins: number;
  predicted_wins_lower: number | null;
  predicted_wins_upper: number | null;
  actual_wins: number | null;
  top_features: Record<string, number>;
}

export interface TeamPredictionDetail extends TeamPrediction {
  methodology: ModelMetadata;
}

export interface RatingComponent {
  name: string;
  column: string;
  raw_value: number | string;
  z_score: number;
  weight: number;
  higher_is_better: boolean;
  contribution: number;
}

export interface RatingBreakdown {
  subject_id: number | string;
  subject_name: string;
  composite_score: number;
  components: RatingComponent[];
}

export interface PlayerPowerRankings {
  season: string;
  generated_at: string;
  methodology_note: string;
  n_qualified_players: number;
  offense: RatingBreakdown[];
  defense: RatingBreakdown[];
}

export interface CoachTeamSeason {
  season: number;
  team: string;
  coach: string;
  actual_win_pct: number;
  implied_win_pct: number;
  wins_above_expectation: number;
  talent_breakdown: RatingBreakdown;
  /** Descriptive team-style context (backend/ratings/team_style.py), null
   * when refresh_team_style.py hasn't covered this team-season. Correlation/
   * association with wins_above_expectation at most — never render as cause. */
  pace: number | null;
  ast_pct: number | null;
  three_pa_rate: number | null;
}

export interface ShotHeatmapCell {
  x: number;
  y: number;
  attempts: number;
  makes: number;
  fg_pct: number;
}

export interface ShotHeatmap {
  team: string;
  season: string;
  offense_cells: ShotHeatmapCell[];
  defense_cells: ShotHeatmapCell[];
  n_offense_shots: number;
  n_defense_shots: number;
}

export interface CoachCareerSummary {
  coach: string;
  seasons_coached: number;
  teams_coached: string[];
  n_teams: number;
  avg_wins_above_expectation: number;
  avg_actual_win_pct: number;
  avg_implied_win_pct: number;
}

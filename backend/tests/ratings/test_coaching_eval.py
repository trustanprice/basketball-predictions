import pandas as pd
import pytest

from ratings.coaching_eval import (
    _age_factor,
    coach_career_summary,
    coach_wins_above_expectation,
    compute_team_season_talent,
    implied_win_pct,
)

# Coach X moves from Team A to Team B in season 3 — the cross-team tracking case.
TEAM_SEASONS = pd.DataFrame([
    {"Season": 1, "Team": "Team A", "Coach": "Coach X", "WIN%": 0.7, "Payroll": 100e6, "avg_pts_top10": 20.0, "avg_production_score": 0.50, "avg_age": 27.0},
    {"Season": 2, "Team": "Team A", "Coach": "Coach X", "WIN%": 0.3, "Payroll": 50e6, "avg_pts_top10": 10.0, "avg_production_score": 0.20, "avg_age": 20.0},
    {"Season": 2, "Team": "Team B", "Coach": "Coach Y", "WIN%": 0.5, "Payroll": 75e6, "avg_pts_top10": 15.0, "avg_production_score": 0.35, "avg_age": 30.0},
    {"Season": 3, "Team": "Team B", "Coach": "Coach X", "WIN%": 0.6, "Payroll": 90e6, "avg_pts_top10": 18.0, "avg_production_score": 0.45, "avg_age": 25.0},
])


def test_age_factor_peak_age_is_one():
    assert _age_factor(pd.Series([27.0])).iloc[0] == pytest.approx(1.0)


def test_age_factor_known_values():
    ages = pd.Series([20.0, 30.0, 25.0])
    expected = pd.Series([1 - 7 / 27, 1 - 3 / 27, 1 - 2 / 27])
    pd.testing.assert_series_equal(_age_factor(ages), expected, check_names=False)


def test_age_factor_clips_to_zero_for_extreme_age():
    assert _age_factor(pd.Series([60.0])).iloc[0] == 0.0
    assert _age_factor(pd.Series([-5.0])).iloc[0] == 0.0


def test_implied_win_pct_zero_z_score_is_league_average():
    actual = pd.Series([0.3, 0.5, 0.7])
    talent_z = pd.Series([0.0, 0.0, 0.0])
    result = implied_win_pct(talent_z, actual)
    assert result.sub(actual.mean()).abs().max() < 1e-9


def test_implied_win_pct_is_clipped_to_valid_range():
    actual = pd.Series([0.3, 0.5, 0.7])
    talent_z = pd.Series([100.0, -100.0])
    result = implied_win_pct(talent_z, actual.iloc[:2])
    assert result.iloc[0] <= 1.0
    assert result.iloc[1] >= 0.0


def test_compute_team_season_talent_excludes_win_pct_from_inputs():
    talent_z, breakdowns = compute_team_season_talent(TEAM_SEASONS)
    assert len(talent_z) == len(TEAM_SEASONS)
    columns_used = {c["column"] for b in breakdowns for c in b.components}
    assert "WIN%" not in columns_used
    assert "AGE_FACTOR" in columns_used


def test_missing_required_column_raises():
    bad = TEAM_SEASONS.drop(columns=["Payroll"])
    with pytest.raises(ValueError, match="Payroll"):
        coach_wins_above_expectation(bad)


def test_wins_above_expectation_equals_actual_minus_implied():
    result = coach_wins_above_expectation(TEAM_SEASONS)
    diff = result["WIN%"] - result["implied_win_pct"]
    pd.testing.assert_series_equal(diff, result["wins_above_expectation"], check_names=False)


def test_wins_above_expectation_has_one_row_per_input_row():
    result = coach_wins_above_expectation(TEAM_SEASONS)
    assert len(result) == len(TEAM_SEASONS)
    assert "talent_breakdown" in result.columns
    assert set(result.iloc[0]["talent_breakdown"].keys()) == {"subject_id", "subject_name", "composite_score", "components"}


def test_coach_career_summary_tracks_coach_across_teams():
    team_season_results = coach_wins_above_expectation(TEAM_SEASONS)
    summary = coach_career_summary(team_season_results).set_index("Coach")

    coach_x = summary.loc["Coach X"]
    assert coach_x["seasons_coached"] == 3
    assert coach_x["n_teams"] == 2
    assert coach_x["teams_coached"] == ["Team A", "Team B"]

    coach_y = summary.loc["Coach Y"]
    assert coach_y["seasons_coached"] == 1
    assert coach_y["n_teams"] == 1


def test_coach_career_summary_avg_matches_hand_calculation():
    team_season_results = coach_wins_above_expectation(TEAM_SEASONS)
    summary = coach_career_summary(team_season_results).set_index("Coach")

    coach_x_rows = team_season_results[team_season_results["Coach"] == "Coach X"]
    expected_avg = coach_x_rows["wins_above_expectation"].mean()
    assert summary.loc["Coach X", "avg_wins_above_expectation"] == pytest.approx(expected_avg)

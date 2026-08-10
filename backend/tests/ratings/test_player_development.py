import pandas as pd
import pytest

from ratings.player_development import (
    MIN_TOTAL_SEASONS_FOR_ADJUSTMENT,
    build_aging_curve,
    project_player_next_season,
    project_team_talent_features,
)


def _career(player_id: int, ages: list[float], per36: list[float], gp: int = 70, min_per_game: float = 30.0) -> pd.DataFrame:
    """A synthetic PlayerCareerStats-shaped dataframe (PerGame mode) for one
    player -- PTS is derived from per36 so build_aging_curve's own per-36
    computation reproduces exactly `per36`, letting the engineered trend be
    hand-checked precisely."""
    rows = []
    for i, (age, rate) in enumerate(zip(ages, per36)):
        rows.append({
            "PLAYER_ID": player_id,
            "SEASON_ID": f"20{10 + i}-{11 + i}",
            "PLAYER_AGE": age,
            "GP": gp,
            "MIN": min_per_game,
            "PTS": rate * min_per_game / 36,
        })
    return pd.DataFrame(rows)


# Five players, identical engineered career shape: flat scoring rate at ages
# 24->25 and 25->26 (0% change), then an exact -10% drop at 26->27. Five
# observations per age bin exactly meets MIN_OBSERVATIONS_PER_AGE_BIN (5), so
# every bin below is populated and its median is hand-computable: 0.0, 0.0,
# and -0.10 respectively -- not just "roughly negative with age," an exact
# recovered number.
FIVE_PLAYER_CAREERS = [
    _career(player_id=100 + i, ages=[24, 25, 26, 27], per36=[20.0, 20.0, 20.0, 18.0])
    for i in range(5)
]


def test_build_aging_curve_recovers_engineered_flat_transitions():
    curve = build_aging_curve(FIVE_PLAYER_CAREERS)
    assert curve.loc[24, "median_pct_change"] == pytest.approx(0.0)
    assert curve.loc[24, "n_observations"] == 5
    assert curve.loc[25, "median_pct_change"] == pytest.approx(0.0)


def test_build_aging_curve_recovers_engineered_decline():
    curve = build_aging_curve(FIVE_PLAYER_CAREERS)
    assert curve.loc[26, "median_pct_change"] == pytest.approx(-0.10)
    assert curve.loc[26, "n_observations"] == 5


def test_build_aging_curve_drops_bins_below_minimum_observations():
    # Only 2 careers -> every age bin has 2 observations, below the
    # MIN_OBSERVATIONS_PER_AGE_BIN=5 threshold -- none should survive.
    curve = build_aging_curve(FIVE_PLAYER_CAREERS[:2])
    assert curve.empty


def test_build_aging_curve_ignores_low_gp_seasons():
    # A "transition" built entirely from sub-MIN_GP_FOR_CURVE seasons (e.g.
    # 3 games) must not contribute a wild swing to the curve.
    injury_career = _career(player_id=999, ages=[24, 25], per36=[45.0, 5.0], gp=3)
    curve = build_aging_curve(FIVE_PLAYER_CAREERS + [injury_career])
    # Still exactly 5 real observations at age 24 -- the 6th (low-GP) career
    # contributed nothing.
    assert curve.loc[24, "n_observations"] == 5


def test_build_aging_curve_empty_input_returns_empty_frame():
    curve = build_aging_curve([])
    assert curve.empty


def test_project_player_next_season_applies_age_bin_median():
    curve = build_aging_curve(FIVE_PLAYER_CAREERS)
    # A 6th player with the same 3-prior-seasons shape, currently age 26.
    career = _career(player_id=200, ages=[24, 25, 26], per36=[20.0, 20.0, 20.0])
    result = project_player_next_season(career, curve)

    assert result["development_adjustment_applied"] is True
    assert result["development_pct_change"] == pytest.approx(-0.10)
    assert result["projected_age"] == pytest.approx(27.0)
    # last_per36 (20) * (1 - 0.10) = 18 per-36 -> back to per-game at the
    # same (carried-forward) minutes: 18 * 30/36 = 15.0.
    assert result["projected_pts"] == pytest.approx(18.0 * 30.0 / 36.0)
    assert result["projected_min"] == pytest.approx(30.0)


def test_project_player_next_season_no_adjustment_for_thin_history():
    curve = build_aging_curve(FIVE_PLAYER_CAREERS)
    # Exactly at the "0-1 prior seasons" boundary: 2 total seasons recorded.
    assert MIN_TOTAL_SEASONS_FOR_ADJUSTMENT == 3
    career = _career(player_id=300, ages=[25, 26], per36=[20.0, 20.0])
    result = project_player_next_season(career, curve)

    assert result["development_adjustment_applied"] is False
    assert result["development_pct_change"] is None
    # Unadjusted: projected stats equal the actual most recent season exactly.
    assert result["projected_pts"] == pytest.approx(20.0 * 30.0 / 36.0)
    assert "not enough personal history" in result["development_note"]


def test_project_player_next_season_no_adjustment_for_missing_age_bin():
    curve = build_aging_curve(FIVE_PLAYER_CAREERS)
    # 3+ prior seasons, but at an age (45) with zero real transitions in the curve.
    career = _career(player_id=400, ages=[43, 44, 45], per36=[10.0, 10.0, 10.0])
    result = project_player_next_season(career, curve)

    assert result["development_adjustment_applied"] is False
    assert result["projected_pts"] == pytest.approx(10.0 * 30.0 / 36.0)
    assert "No league-wide aging-curve data" in result["development_note"]


def test_project_player_next_season_requires_at_least_one_season():
    with pytest.raises(ValueError):
        project_player_next_season(pd.DataFrame(), pd.DataFrame())


def test_project_team_talent_features_matches_hand_calculation():
    projected = pd.DataFrame([
        {"projected_age": 25.0, "projected_pts": 20.0, "projected_min": 32.0, "development_adjustment_applied": True},
        {"projected_age": 27.0, "projected_pts": 15.0, "projected_min": 28.0, "development_adjustment_applied": True},
        {"projected_age": 30.0, "projected_pts": 5.0, "projected_min": 12.0, "development_adjustment_applied": False},
    ])
    features = project_team_talent_features(projected)

    assert features["avg_age"] == pytest.approx((25.0 + 27.0 + 30.0) / 3)
    # Fewer than 10 players -> avg_pts_top10 is just the mean of all of them.
    assert features["avg_pts_top10"] == pytest.approx((20.0 + 15.0 + 5.0) / 3)
    expected_prod = ((20.0 / 32.0) + (15.0 / 28.0) + (5.0 / 12.0)) / 3
    assert features["avg_production_score"] == pytest.approx(expected_prod)
    assert features["n_players"] == 3
    assert features["n_players_adjusted"] == 2
    assert features["n_players_unadjusted"] == 1


def test_project_team_talent_features_top10_excludes_bench_scorers():
    rows = [{"projected_age": 25.0, "projected_pts": float(20 - i), "projected_min": 30.0, "development_adjustment_applied": True} for i in range(15)]
    projected = pd.DataFrame(rows)
    features = project_team_talent_features(projected)
    top10_expected = sum(20 - i for i in range(10)) / 10
    assert features["avg_pts_top10"] == pytest.approx(top10_expected)


def test_project_team_talent_features_empty_roster_raises():
    with pytest.raises(ValueError):
        project_team_talent_features(pd.DataFrame())

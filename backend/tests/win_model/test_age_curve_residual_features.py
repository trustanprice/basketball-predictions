import pandas as pd
import pytest

from win_model.age_curve_residual_features import (
    AGE_RESIDUAL_COLUMN,
    _build_curve_from_per36,
    _team_residual,
)


def _panel(rows: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["norm_name", "Team_full", "age", "per36"])


def test_team_residual_hand_computed():
    """Player transitions from per36=20 at age 25 to per36=24 at age 26 --
    a real +20% change. If the league-wide curve says age-25 players see a
    median +5% change, this player's residual is +20% - +5% = +15%, weighted
    fully since they're the only roster player with a usable transition."""
    prior = _panel([("player a", "Test Team", 25.0, 20.0)]).assign(SEASON_ID=2020, total_pts=1000.0)
    actual = _panel([("player a", "Test Team", 26.0, 24.0)]).assign(SEASON_ID=2021, total_pts=1200.0)
    panels = {2020: prior, 2021: actual}

    # Curve built from a separate, larger synthetic sample at age 25 so the
    # test's own single transition doesn't define its own expectation.
    curve_sample = pd.concat([
        _panel([(f"filler {i}", "Other", 25.0, 10.0) for i in range(5)]).assign(
            SEASON_ID=2020, total_pts=0.0
        ),
        _panel([(f"filler {i}", "Other", 25.0, 10.5) for i in range(5)]).assign(
            SEASON_ID=2021, total_pts=0.0
        ),
    ], ignore_index=True)
    curve = _build_curve_from_per36(curve_sample)
    assert 25 in curve.index
    assert curve.loc[25, "median_pct_change"] == pytest.approx(0.05)

    residual = _team_residual("Test Team", 2021, 2020, panels, curve)
    assert residual == pytest.approx(0.20 - 0.05)


def test_team_residual_no_curve_data_for_age_skips_player():
    prior = _panel([("player a", "Test Team", 99.0, 20.0)]).assign(SEASON_ID=2020, total_pts=1000.0)
    actual = _panel([("player a", "Test Team", 100.0, 24.0)]).assign(SEASON_ID=2021, total_pts=1200.0)
    panels = {2020: prior, 2021: actual}
    empty_curve = pd.DataFrame(columns=["n_observations", "median_pct_change"]).rename_axis("age")

    assert _team_residual("Test Team", 2021, 2020, panels, empty_curve) is None


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run -- slower than the rest of the suite, but this is
    the actual validation this module's docstring cites, so it needs to keep
    working, not just its pure-function pieces."""
    from win_model.age_curve_residual_features import run_experiment

    result = run_experiment()
    assert result["baseline_walk_forward_mae"] > 0
    assert result["augmented_walk_forward_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding in isolation (vs. plain NUMERIC_FEATURES)
    # at the time this was written. Worth noting this is NOT the decisive
    # test -- stacked on top of the already-validated Roster_Change feature
    # (the real deployment scenario), this feature actually hurts (6.425 ->
    # 6.528 walk-forward MAE); see backend/win_model/train.py's comments and
    # this session's report for that comparison. Not wired into
    # FEATURE_COLUMNS. If a future change flips either result, the honest
    # thing is to update the finding, not treat this assertion as sacred.
    assert result["improves_mae"] is True

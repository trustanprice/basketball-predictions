import pandas as pd
import pytest

from win_model.coach_quality_features import (
    COACH_QUALITY_COLUMN,
    CURRENT_SEASON_COACHES,
    _career_avg_wae,
)
from win_model.data_loader import MASTER_DF_FILE
from ratings.player_development import MIN_TOTAL_SEASONS_FOR_ADJUSTMENT


def _wae_table(rows: list[tuple[str, int, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Coach", "Season", "wins_above_expectation"])


def test_career_avg_wae_hand_computed():
    table = _wae_table([
        ("Coach A", 2020, 0.10),
        ("Coach A", 2021, -0.20),
        ("Coach A", 2022, 0.30),
        ("Coach B", 2022, 0.50),  # different coach, must not leak in
    ])
    # Exactly MIN_TOTAL_SEASONS_FOR_ADJUSTMENT seasons for Coach A through 2022.
    assert MIN_TOTAL_SEASONS_FOR_ADJUSTMENT == 3
    result = _career_avg_wae("Coach A", 2022, table)
    assert result == pytest.approx((0.10 - 0.20 + 0.30) / 3)


def test_career_avg_wae_excludes_future_seasons():
    """A coach's row for Season > as_of_season must not leak into the
    average -- this is the exact discipline TARGET_COLUMN's Next_W shift and
    SOS's prior-season-only construction already enforce elsewhere."""
    table = _wae_table([
        ("Coach A", 2020, 0.10),
        ("Coach A", 2021, -0.20),
        ("Coach A", 2022, 0.30),
        ("Coach A", 2023, 999.0),  # would blow up the average if it leaked in
    ])
    result = _career_avg_wae("Coach A", 2022, table)
    assert result == pytest.approx((0.10 - 0.20 + 0.30) / 3)


def test_career_avg_wae_below_minimum_seasons_returns_none():
    table = _wae_table([("Coach A", 2022, 0.10)])  # 1 season, first-year coach
    assert _career_avg_wae("Coach A", 2022, table) is None


def test_current_season_coaches_covers_all_30_teams():
    from win_model.data_loader import load_team_records  # any real 30-team list

    real_teams = set(pd.read_csv(MASTER_DF_FILE)["Team"].unique())
    assert set(CURRENT_SEASON_COACHES.keys()) == real_teams


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run -- slower than the rest of the suite, but this is
    the actual validation this module's docstring cites, so it needs to keep
    working, not just its pure-function pieces."""
    from win_model.coach_quality_features import run_experiment

    result = run_experiment()
    assert result["baseline_walk_forward_mae"] > 0
    assert result["augmented_walk_forward_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding in isolation (vs. plain NUMERIC_FEATURES)
    # at the time this was written -- NOT the decisive test. Stacked on top
    # of the already-validated Roster_Change feature (the real deployment
    # scenario), this feature actually hurts (6.418 -> 6.486 walk-forward
    # MAE); see this session's report for that comparison. Not wired into
    # FEATURE_COLUMNS. If a future change flips either result, the honest
    # thing is to update the finding, not treat this assertion as sacred.
    assert result["improves_mae"] is True

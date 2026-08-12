import pandas as pd
import pytest

from win_model.roster_change_features import (
    ROSTER_CHANGE_COLUMN,
    _normalize_name,
    _roster_change_for_team_season,
    forecast_roster_change,
)


def test_normalize_name_strips_accents_and_punctuation():
    assert _normalize_name("Nikola Jokić") == _normalize_name("Nikola Jokic")
    assert _normalize_name("A.J. Lawson") == _normalize_name("AJ Lawson")


def _panel(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["norm_name", "Team_full", "total_pts"])


def test_roster_change_hand_computed():
    """Team keeps Player A, loses Player B (200 pts), gains Player C (150 pts,
    who scored those 150 pts on a DIFFERENT team last season) -- net change
    should be exactly 150 - 200 = -50, using each mover's own prior production,
    not their new team's."""
    season_n = _panel([
        ("player a", "Test Team", 300.0),
        ("player b", "Test Team", 200.0),
        ("player c", "Other Team", 150.0),
    ])
    season_n_plus_1 = _panel([
        ("player a", "Test Team", 0.0),  # value on the later panel is irrelevant to this function
        ("player c", "Test Team", 0.0),
    ])
    panels = {2020: season_n, 2021: season_n_plus_1}

    change = _roster_change_for_team_season(2020, "Test Team", panels)
    assert change == pytest.approx(150.0 - 200.0)


def test_roster_change_missing_panel_returns_none():
    panels = {2020: _panel([("player a", "Test Team", 100.0)])}
    assert _roster_change_for_team_season(2020, "Test Team", panels) is None  # no 2021 panel at all
    assert _roster_change_for_team_season(1999, "Test Team", panels) is None  # no 1999 panel either


def test_roster_change_rookie_arrival_contributes_zero():
    """An arriving player absent from the prior season's panel entirely
    (rookie, no top-line stat row) contributes 0, not a fabricated value."""
    season_n = _panel([("player a", "Test Team", 300.0)])
    season_n_plus_1 = _panel([("player a", "Test Team", 0.0), ("rookie", "Test Team", 0.0)])
    panels = {2020: season_n, 2021: season_n_plus_1}

    change = _roster_change_for_team_season(2020, "Test Team", panels)
    assert change == pytest.approx(0.0 - 0.0)  # rookie arrival = 0, nobody departed


def test_forecast_roster_change_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    assert forecast_roster_change("Some Team", 2026, missing) is None


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run (walk-forward-tunes two model families twice) --
    slower than the rest of the suite, but this is the actual validation this
    module's docstring cites, so it needs to keep working, not just its
    pure-function pieces."""
    from win_model.roster_change_features import run_experiment

    result = run_experiment()
    assert result["baseline_walk_forward_mae"] > 0
    assert result["augmented_walk_forward_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding at the time this was written -- if a future
    # change flips this, the honest thing is to update the finding (both here
    # and in train.py's metadata), not to treat this assertion as sacred.
    assert result["improves_mae"] is True

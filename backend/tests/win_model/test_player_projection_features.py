import pandas as pd
import pytest

from win_model.player_projection_features import (
    PROJECTED_FEATURE_COLUMNS,
    _historical_player_panel,
    _project_team_season,
)
from ratings.player_development import build_aging_curve


def test_historical_player_panel_has_expected_columns():
    panel = _historical_player_panel()
    assert set(["PLAYER_ID", "SEASON_ID", "PLAYER_AGE", "GP", "MIN", "PTS", "Team", "_season_int"]) <= set(
        panel.columns
    )
    assert len(panel) > 0


def test_project_team_season_only_uses_seasons_up_to_and_including_target():
    # Two synthetic seasons for one player on one team: a real transition at
    # age 25 (flat scoring rate), then a huge, obviously-fabricated jump in a
    # *later* season that must NOT leak into a projection made as of the
    # earlier season.
    panel = pd.DataFrame([
        {"PLAYER_ID": "Test Player", "SEASON_ID": "2016", "PLAYER_AGE": 24, "GP": 70, "MIN": 30.0, "PTS": 15.0, "Team": "Test Team", "_season_int": 2016},
        {"PLAYER_ID": "Test Player", "SEASON_ID": "2017", "PLAYER_AGE": 25, "GP": 70, "MIN": 30.0, "PTS": 15.0, "Team": "Test Team", "_season_int": 2017},
        # A future season (2020) with an extreme rate -- must be invisible
        # when projecting *from* 2017.
        {"PLAYER_ID": "Test Player", "SEASON_ID": "2020", "PLAYER_AGE": 28, "GP": 70, "MIN": 30.0, "PTS": 90.0, "Team": "Test Team", "_season_int": 2020},
    ])
    aging_curve = build_aging_curve([panel])  # trivial curve from this same panel

    result_2017 = _project_team_season(panel, aging_curve, "Test Team", 2017)
    assert result_2017 is not None
    # Nowhere near the fabricated 90-PTS season's influence -- proves the
    # 2020 row was excluded from the 2017-based projection.
    assert result_2017["avg_pts_top10"] < 30.0


def test_project_team_season_returns_none_for_unknown_team_season():
    panel = _historical_player_panel()
    assert _project_team_season(panel, build_aging_curve([]), "Not A Real Team", 1900) is None


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run (walk-forward-tunes two model families twice) --
    slower than the rest of the suite, but this is the actual validation this
    module's docstring cites, so it needs to keep working, not just its
    pure-function pieces."""
    from win_model.player_projection_features import run_experiment

    result = run_experiment()
    assert result["baseline_walk_forward_mae"] > 0
    assert result["augmented_walk_forward_mae"] > 0
    assert set(result["features_added"]) == set(PROJECTED_FEATURE_COLUMNS)
    assert isinstance(result["improves_mae"], bool)

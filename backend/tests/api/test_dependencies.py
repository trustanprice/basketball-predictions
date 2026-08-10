"""Tests the dependency functions directly against the REAL data files this repo
already has (win_model's committed test_results.csv/model_metadata.json, and
master_df.csv for coaching) — a real integration check, not mocks. The one
dependency that can't be exercised for real here is player power rankings: its
source file is only ever produced by a live NBA.com fetch (refresh_player_ratings.py),
and this environment has no network access — so that one is a 503-path test only.
"""

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.api import dependencies


def test_get_predictions_df_reads_real_output():
    df = dependencies.get_predictions_df()
    assert isinstance(df, pd.DataFrame)
    assert {"Season", "Team", "W", "Pred_Wins"} <= set(df.columns)
    assert len(df) > 0


def test_get_model_metadata_reads_real_output():
    metadata = dependencies.get_model_metadata()
    assert metadata["model_comparison"]["winner"] in {"knn", "gbm"}
    assert "validation_method" in metadata


def test_get_coach_team_seasons_computes_from_real_master_df():
    df = dependencies.get_coach_team_seasons()
    assert {"Season", "Team", "Coach", "wins_above_expectation"} <= set(df.columns)
    assert len(df) == 300  # 30 teams x 10 seasons, per Phase 4's validated run


def test_get_coach_career_summary_computes_from_real_master_df():
    df = dependencies.get_coach_career_summary()
    assert "Gregg Popovich" in df["Coach"].values
    # sorted descending by avg_wins_above_expectation, per coach_career_summary()
    assert df["avg_wins_above_expectation"].is_monotonic_decreasing


def test_get_player_power_rankings_503s_when_never_refreshed():
    """No network in this environment, so refresh_player_ratings.py has never
    run here and the output file genuinely doesn't exist — this documents the
    real current state, not a simulated one."""
    if dependencies.PLAYER_RANKINGS_FILE.exists():
        pytest.skip("player_power_rankings.json exists in this environment — nothing to assert here")
    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_player_power_rankings()
    assert exc_info.value.status_code == 503


def test_get_player_projections_503s_when_never_refreshed():
    if dependencies.PLAYER_PROJECTIONS_FILE.exists():
        pytest.skip("player_projections.json exists in this environment — nothing to assert here")
    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_player_projections()
    assert exc_info.value.status_code == 503


def test_get_player_projections_reads_real_output_when_present():
    """This environment's network access varies run to run (see module
    docstring) — when refresh_player_projections.py has actually run here,
    exercise the real file instead of skipping past it."""
    if not dependencies.PLAYER_PROJECTIONS_FILE.exists():
        pytest.skip("player_projections.json not present in this environment")
    data = dependencies.get_player_projections(n=3)
    assert "PRESEASON PROJECTION" in data["note"]
    assert len(data["offense"]) <= 3
    assert len(data["defense"]) <= 3


def test_get_player_power_rankings_n_slices_the_cached_max(monkeypatch, tmp_path):
    """The cache always stores up to MAX_N players per side (see
    refresh_player_ratings.py); `n` trims that down at request time rather
    than triggering a re-fetch — this is pure response-shaping, testable
    without any real cache file or network access."""
    import json

    fake_file = tmp_path / "player_power_rankings.json"
    fake_file.write_text(json.dumps({
        "season": "2025-26",
        "generated_at": "2026-08-08T00:00:00+00:00",
        "methodology_note": "...",
        "n_qualified_players": 10,
        "offense": [{"subject_id": i, "subject_name": f"Player {i}"} for i in range(10)],
        "defense": [{"subject_id": i, "subject_name": f"Player {i}"} for i in range(10)],
    }))
    monkeypatch.setattr(dependencies, "PLAYER_RANKINGS_FILE", fake_file)

    result = dependencies.get_player_power_rankings(n=3)
    assert len(result["offense"]) == 3
    assert len(result["defense"]) == 3
    assert [p["subject_id"] for p in result["offense"]] == [0, 1, 2]

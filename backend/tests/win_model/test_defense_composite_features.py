"""Unlike roster_change_features.py/age_curve_residual_features.py, this
module has no local-file equivalent for DREB_PCT/DEF_RATING -- every test
here needs a real live_client fetch. Skips cleanly (doesn't fail the suite)
if stats.nba.com isn't reachable, same pattern as
tests/live_client/test_integration_real_network.py.
"""

import socket

import pandas as pd
import pytest

from win_model.defense_composite_features import DEFENSE_COMPOSITE_COLUMN, _team_defense_composite


def _nba_stats_reachable() -> bool:
    try:
        with socket.create_connection(("stats.nba.com", 443), timeout=5):
            return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _nba_stats_reachable(), reason="stats.nba.com not reachable from this environment",
)


def test_team_defense_composite_hand_computed():
    """Pure function, no network needed -- averages defense_z across a
    team's top-N scorers by PTS in an already-built table."""
    table = pd.DataFrame({
        "TEAM_ID": [1, 1, 1, 2],
        "PTS": [20.0, 15.0, 10.0, 99.0],
        "defense_z": [1.0, -0.5, 0.5, 100.0],
    })
    # TOP_N_SCORERS defaults to 10, so all 3 of team 1's players count.
    result = _team_defense_composite(1, table)
    assert result == pytest.approx((1.0 - 0.5 + 0.5) / 3)


def test_team_defense_composite_no_roster_returns_none():
    table = pd.DataFrame({"TEAM_ID": [1], "PTS": [20.0], "defense_z": [1.0]})
    assert _team_defense_composite(999, table) is None


@requires_network
def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run (real live_client fetches across 11 seasons, then
    walk-forward-tunes two model families twice) -- the slowest test in this
    suite, but this is the actual validation this module's docstring cites."""
    from win_model.defense_composite_features import run_experiment

    result = run_experiment()
    assert result["baseline_walk_forward_mae"] > 0
    assert result["augmented_walk_forward_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    assert result["n_missing_defense_data"] == 0
    # Documents the actual finding in isolation (vs. plain NUMERIC_FEATURES)
    # at the time this was written -- NOT the decisive test. Stacked on top
    # of the already-validated Roster_Change feature (the real deployment
    # scenario), this feature actually hurts (6.425 -> 6.618 walk-forward
    # MAE) despite being this session's own leading hypothesis; see this
    # session's report for that comparison. Not wired into FEATURE_COLUMNS.
    # If a future change flips either result, the honest thing is to update
    # the finding, not treat this assertion as sacred.
    assert result["improves_mae"] is True

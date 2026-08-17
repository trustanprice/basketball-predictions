"""Unlike roster_change_features.py, schedule_simulation.py's core math (log5,
home-court calibration, Monte Carlo simulation) is pure and needs no network --
only fetch_regular_season_schedule() does. Same requires_network pattern as
test_defense_composite_features.py / tests/live_client/test_integration_real_network.py.
"""

import socket

import pandas as pd
import pytest

from win_model.schedule_simulation import (
    game_win_probability,
    home_court_edge_from_history,
    log5,
    simulate_season,
)


def _nba_stats_reachable() -> bool:
    try:
        with socket.create_connection(("stats.nba.com", 443), timeout=5):
            return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _nba_stats_reachable(), reason="stats.nba.com not reachable from this environment",
)


def test_log5_equal_teams_is_a_coin_flip():
    assert log5(0.5, 0.5) == pytest.approx(0.5)


def test_log5_better_team_favored():
    assert log5(0.7, 0.3) > 0.5


def test_log5_symmetric():
    assert log5(0.65, 0.4) == pytest.approx(1 - log5(0.4, 0.65))


def test_log5_handles_zero_denominator_without_raising():
    # win_pct_a + win_pct_b - 2*a*b == 0 when both are exactly 0 or both are 1.
    assert log5(0.0, 0.0) == 0.5
    assert log5(1.0, 1.0) == 0.5


def test_home_court_edge_matches_hand_computed_ratio():
    master_df = pd.DataFrame({
        "Season": [2020, 2021, 2022],
        "Home_W": [24, 23, 25],
        "Home_L": [17, 18, 16],
    })
    edge = home_court_edge_from_history(master_df)
    total_wins, total_games = 24 + 23 + 25, (24 + 17) + (23 + 18) + (25 + 16)
    assert edge == pytest.approx(total_wins / total_games - 0.5)


def test_home_court_edge_excludes_seasons_at_or_after_cutoff():
    master_df = pd.DataFrame({
        "Season": [2020, 2026],
        "Home_W": [41, 82],  # 2026 alone would push the edge far higher
        "Home_L": [41, 0],
    })
    edge = home_court_edge_from_history(master_df, before_season=2026)
    assert edge == pytest.approx(0.0)  # only the 41-41 season counts


def test_game_win_probability_is_clipped_away_from_certainty():
    # An extreme rating gap plus a large home-court edge shouldn't produce
    # a mathematically certain outcome -- real NBA games always have variance.
    prob = game_win_probability(0.95, 0.05, home_court_edge=0.5)
    assert prob <= 0.98


def test_simulate_season_unrated_team_raises():
    schedule = pd.DataFrame({"home_team": ["A"], "away_team": ["B"]})
    with pytest.raises(ValueError, match="No win percentage supplied"):
        simulate_season(schedule, {"A": 0.5}, home_court_edge=0.05, n_simulations=10)


def test_simulate_season_equal_ratings_converge_to_half_the_games_each():
    # A round-robin where A and B each play the other 100 times at equal
    # ratings and no home-court edge: each should win ~50% of its own games.
    schedule = pd.DataFrame({
        "home_team": ["A"] * 50 + ["B"] * 50,
        "away_team": ["B"] * 50 + ["A"] * 50,
    })
    result = simulate_season(schedule, {"A": 0.5, "B": 0.5}, home_court_edge=0.0,
                              n_simulations=20000, seed=7)
    row_a = result.loc[result["Team"] == "A", "sim_mean_wins"].iloc[0]
    assert row_a == pytest.approx(50, abs=1.5)


def test_simulate_season_every_game_is_won_by_exactly_one_team():
    # Expectation of total league-wide wins must equal the number of games
    # simulated, regardless of ratings -- every game has exactly one winner.
    schedule = pd.DataFrame({
        "home_team": ["A", "B", "A"],
        "away_team": ["B", "A", "C"],
    })
    result = simulate_season(schedule, {"A": 0.7, "B": 0.4, "C": 0.5},
                              home_court_edge=0.05, n_simulations=5000, seed=3)
    assert result["sim_mean_wins"].sum() == pytest.approx(len(schedule), abs=0.05)


@requires_network
def test_fetch_regular_season_schedule_returns_real_games():
    from win_model.schedule_simulation import fetch_regular_season_schedule

    schedule = fetch_regular_season_schedule("2025-26")
    assert len(schedule) == 1230  # completed season, full slate known
    assert set(schedule.columns) == {"gameId", "home_team", "away_team"}
    assert schedule["home_team"].nunique() == 30


@requires_network
def test_schedule_simulation_backtest_reports_a_real_comparison():
    from win_model.schedule_simulation_backtest import run_backtest

    result = run_backtest(n_simulations=2000)
    assert result["n_team_seasons"] > 0
    assert result["plain_model_mae"] > 0
    assert result["schedule_sim_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding at the time this was written, pooled across
    # every backtestable season (2017-18 through 2025-26) -- NOT a single-season
    # sample, which was tried first and rejected as too weak a test either way.
    # 6.835 -> 6.768 walk-forward MAE: real but modest, and it clearly hurts in
    # both pandemic-disrupted seasons (2019-20, 2020-21) while helping in most
    # normal ones. If a future change flips this, the honest thing is to update
    # the finding, not treat this assertion as sacred.
    assert result["improves_mae"] is True

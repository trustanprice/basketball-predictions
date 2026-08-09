import pandas as pd
import pytest

from ratings.player_power_rankings import (
    DEFENSE_COMPONENTS,
    OFFENSE_COMPONENTS,
    build_player_table,
    top_defensive_players,
    top_offensive_players,
)

# Player Three is a qualification-filter tripwire (GP=10 < 20, MIN=8 < 15) — must
# never appear in build_player_table's output.
SEASON_TOTALS = pd.DataFrame([
    {"PLAYER_ID": 1, "PLAYER_NAME": "Player One", "TEAM_ID": 100, "GP": 70, "MIN": 30, "PTS": 25, "STL": 1.0, "BLK": 0.5},
    {"PLAYER_ID": 2, "PLAYER_NAME": "Player Two", "TEAM_ID": 101, "GP": 75, "MIN": 32, "PTS": 15, "STL": 2.0, "BLK": 1.5},
    {"PLAYER_ID": 3, "PLAYER_NAME": "Player Three", "TEAM_ID": 102, "GP": 10, "MIN": 8, "PTS": 30, "STL": 0.1, "BLK": 0.0},
    {"PLAYER_ID": 4, "PLAYER_NAME": "Player Four", "TEAM_ID": 100, "GP": 60, "MIN": 20, "PTS": 10, "STL": 0.5, "BLK": 0.2},
    {"PLAYER_ID": 5, "PLAYER_NAME": "Player Five", "TEAM_ID": 103, "GP": 82, "MIN": 35, "PTS": 20, "STL": 1.5, "BLK": 2.0},
])

ADVANCED_STATS = pd.DataFrame([
    {"PLAYER_ID": 1, "PLAYER_NAME": "Player One", "TEAM_ID": 100, "USG_PCT": 0.30, "TS_PCT": 0.60, "AST_PCT": 0.25, "TOV_PCT": 0.10, "DREB_PCT": 0.15, "DEF_RATING": 110},
    {"PLAYER_ID": 2, "PLAYER_NAME": "Player Two", "TEAM_ID": 101, "USG_PCT": 0.18, "TS_PCT": 0.55, "AST_PCT": 0.15, "TOV_PCT": 0.08, "DREB_PCT": 0.25, "DEF_RATING": 100},
    {"PLAYER_ID": 3, "PLAYER_NAME": "Player Three", "TEAM_ID": 102, "USG_PCT": 0.35, "TS_PCT": 0.70, "AST_PCT": 0.05, "TOV_PCT": 0.05, "DREB_PCT": 0.05, "DEF_RATING": 120},
    {"PLAYER_ID": 4, "PLAYER_NAME": "Player Four", "TEAM_ID": 100, "USG_PCT": 0.15, "TS_PCT": 0.50, "AST_PCT": 0.10, "TOV_PCT": 0.12, "DREB_PCT": 0.10, "DEF_RATING": 115},
    {"PLAYER_ID": 5, "PLAYER_NAME": "Player Five", "TEAM_ID": 103, "USG_PCT": 0.22, "TS_PCT": 0.58, "AST_PCT": 0.20, "TOV_PCT": 0.09, "DREB_PCT": 0.30, "DEF_RATING": 95},
])


def test_qualification_filter_excludes_low_minutes_players():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    assert 3 not in table["PLAYER_ID"].tolist()
    assert set(table["PLAYER_ID"]) == {1, 2, 4, 5}


def test_usage_adjusted_scoring_matches_hand_calculation():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    # league_avg_usage among the 4 qualified players = mean(0.30, 0.18, 0.15, 0.22) = 0.2125
    league_avg_usage = (0.30 + 0.18 + 0.15 + 0.22) / 4
    row = table.set_index("PLAYER_ID").loc[1]
    expected = 25 * (league_avg_usage / 0.30)
    assert row["USAGE_ADJ_PTS"] == pytest.approx(expected, abs=1e-9)


def test_steal_block_per36_matches_hand_calculation():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    row = table.set_index("PLAYER_ID").loc[2]
    expected = (2.0 + 1.5) / 32 * 36
    assert row["STL_BLK_PER36"] == pytest.approx(expected, abs=1e-9)


def test_missing_required_column_raises():
    bad_totals = SEASON_TOTALS.drop(columns=["STL"])
    with pytest.raises(ValueError, match="STL"):
        build_player_table(bad_totals, ADVANCED_STATS)


def test_all_players_filtered_out_raises():
    tiny_minutes = SEASON_TOTALS.copy()
    tiny_minutes["MIN"] = 1
    with pytest.raises(ValueError, match="qualification filter"):
        build_player_table(tiny_minutes, ADVANCED_STATS)


def test_top_offensive_players_returns_requested_count_in_descending_order():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    top = top_offensive_players(table, n=2)
    assert len(top) == 2
    assert top[0].composite_score >= top[1].composite_score
    assert {b.subject_id for b in top} <= {1, 2, 4, 5}


def test_top_defensive_players_returns_requested_count_in_descending_order():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    top = top_defensive_players(table, n=3)
    assert len(top) == 3
    scores = [b.composite_score for b in top]
    assert scores == sorted(scores, reverse=True)


def test_breakdown_components_match_declared_weights():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    top = top_offensive_players(table, n=1)
    names_in_breakdown = {c["name"] for c in top[0].components}
    assert names_in_breakdown == {c.name for c in OFFENSE_COMPONENTS}


def test_defense_breakdown_matches_declared_components():
    table = build_player_table(SEASON_TOTALS, ADVANCED_STATS)
    top = top_defensive_players(table, n=1)
    names_in_breakdown = {c["name"] for c in top[0].components}
    assert names_in_breakdown == {c.name for c in DEFENSE_COMPONENTS}

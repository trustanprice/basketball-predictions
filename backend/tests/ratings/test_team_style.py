import pandas as pd
import pytest

from ratings.team_style import bin_shots_to_heatmap, build_style_fingerprint

TEAM_TOTALS = pd.DataFrame([
    {"TEAM_ID": 1, "TEAM_NAME": "Team A", "FGA": 90.0, "FG3A": 45.0},
    {"TEAM_ID": 2, "TEAM_NAME": "Team B", "FGA": 80.0, "FG3A": 20.0},
])
TEAM_ADVANCED = pd.DataFrame([
    {"TEAM_ID": 1, "TEAM_NAME": "Team A", "PACE": 100.0, "AST_PCT": 0.65},
    {"TEAM_ID": 2, "TEAM_NAME": "Team B", "PACE": 95.0, "AST_PCT": 0.55},
])


def test_build_style_fingerprint_hand_computed():
    result = build_style_fingerprint(TEAM_TOTALS, TEAM_ADVANCED).set_index("Team")
    assert result.loc["Team A", "ThreePARate"] == pytest.approx(0.5)  # 45/90
    assert result.loc["Team B", "ThreePARate"] == pytest.approx(0.25)  # 20/80
    assert result.loc["Team A", "Pace"] == 100.0
    assert result.loc["Team A", "AstPct"] == 0.65


def test_bin_shots_to_heatmap_hand_computed():
    # Two makes and one miss, all in the same corner cell (near (-240, -40));
    # one make far away near center court -- should land in a different cell.
    shots = pd.DataFrame([
        {"LOC_X": -240, "LOC_Y": -40, "SHOT_MADE_FLAG": 1},
        {"LOC_X": -238, "LOC_Y": -38, "SHOT_MADE_FLAG": 1},
        {"LOC_X": -239, "LOC_Y": -39, "SHOT_MADE_FLAG": 0},
        {"LOC_X": 0, "LOC_Y": 200, "SHOT_MADE_FLAG": 1},
    ])
    cells = bin_shots_to_heatmap(shots, grid_cells=25)

    total_attempts = sum(c["attempts"] for c in cells)
    total_makes = sum(c["makes"] for c in cells)
    assert total_attempts == 4
    assert total_makes == 3

    corner_cell = max(cells, key=lambda c: c["attempts"])
    assert corner_cell["attempts"] == 3
    assert corner_cell["makes"] == 2
    assert corner_cell["fg_pct"] == pytest.approx(2 / 3, abs=1e-4)


def test_bin_shots_to_heatmap_empty_input():
    assert bin_shots_to_heatmap(pd.DataFrame(columns=["LOC_X", "LOC_Y", "SHOT_MADE_FLAG"])) == []

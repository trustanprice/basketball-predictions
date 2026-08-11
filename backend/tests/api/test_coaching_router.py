def test_wins_above_expectation_unfiltered_returns_all_rows(client):
    resp = client.get("/api/coaches/wins-above-expectation")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all(row["coach"] == "Gregg Popovich" for row in body)
    assert "talent_breakdown" in body[0]
    assert body[0]["talent_breakdown"]["components"][0]["name"] == "True Shooting %"


def test_wins_above_expectation_filter_by_season(client):
    resp = client.get("/api/coaches/wins-above-expectation", params={"season": 2016})
    body = resp.json()
    assert len(body) == 1
    assert body[0]["season"] == 2016


def test_wins_above_expectation_filter_by_team(client):
    resp = client.get("/api/coaches/wins-above-expectation", params={"team": "San Antonio Spurs"})
    body = resp.json()
    assert len(body) == 2
    assert all(row["team"] == "San Antonio Spurs" for row in body)


def test_wins_above_expectation_no_match_returns_empty_list(client):
    resp = client.get("/api/coaches/wins-above-expectation", params={"season": 1999})
    assert resp.status_code == 200
    assert resp.json() == []


def test_career_summary(client):
    resp = client.get("/api/coaches/career-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["coach"] == "Gregg Popovich"
    assert body[0]["teams_coached"] == ["San Antonio Spurs"]
    assert body[0]["n_teams"] == 1


def test_wins_above_expectation_style_fields_default_to_null(client):
    """The fixture's COACH_TEAM_SEASONS has no pace/ast_pct/three_pa_rate
    columns (simulating refresh_team_style.py never having run) — the route
    must still return 200 with those fields null, not 500."""
    resp = client.get("/api/coaches/wins-above-expectation")
    body = resp.json()
    assert body[0]["pace"] is None
    assert body[0]["ast_pct"] is None
    assert body[0]["three_pa_rate"] is None


def test_shot_heatmap_shape(client):
    from backend.api import dependencies
    from backend.api.main import app

    fake_heatmap = {
        "team": "Boston Celtics",
        "season": "2023-24",
        "offense_cells": [{"x": 0.0, "y": 0.0, "attempts": 10, "makes": 5, "fg_pct": 0.5}],
        "defense_cells": [{"x": 10.0, "y": 10.0, "attempts": 8, "makes": 3, "fg_pct": 0.375}],
        "n_offense_shots": 7000,
        "n_defense_shots": 7200,
    }
    app.dependency_overrides[dependencies.get_team_shot_heatmap] = lambda: fake_heatmap
    try:
        resp = client.get("/api/coaches/shot-heatmap", params={"team": "Boston Celtics", "season": "2023-24"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["team"] == "Boston Celtics"
        assert body["offense_cells"][0]["attempts"] == 10
    finally:
        del app.dependency_overrides[dependencies.get_team_shot_heatmap]

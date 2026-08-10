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

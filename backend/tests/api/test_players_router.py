def test_power_rankings_shape(client):
    resp = client.get("/api/players/power-rankings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["season"] == "2025-26"
    assert len(body["offense"]) == 1
    assert len(body["defense"]) == 1


def test_power_rankings_breakdown_is_fully_transparent(client):
    """The whole point of this endpoint: a client should never need a second call
    to reconstruct how a score was produced."""
    resp = client.get("/api/players/power-rankings")
    body = resp.json()
    player = body["offense"][0]
    assert player["subject_name"] == "Player One"
    assert player["composite_score"] == 2.1
    component = player["components"][0]
    assert set(component.keys()) == {"name", "column", "raw_value", "z_score", "weight", "higher_is_better", "contribution"}
    assert component["name"] == "True Shooting %"


def test_projected_leaders_shape(client):
    resp = client.get("/api/players/projected-leaders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["season"] == "2026-27"
    assert "PRESEASON PROJECTION" in body["note"]
    assert body["offense"][0]["subject_name"] == "Player Three"
    assert body["defense"][0]["subject_name"] == "Player Four"

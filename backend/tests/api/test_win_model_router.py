def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_predictions_returns_only_latest_season(client):
    resp = client.get("/api/win-model/predictions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2  # only the 2026 rows, not 2025
    assert {row["season"] for row in body} == {2026}
    assert {row["team"] for row in body} == {"Boston Celtics", "Miami Heat"}


def test_list_predictions_nan_actual_wins_becomes_null(client):
    resp = client.get("/api/win-model/predictions")
    body = resp.json()
    assert all(row["actual_wins"] is None for row in body)  # 2026 has no known outcome yet


def test_list_predictions_has_no_methodology_field(client):
    resp = client.get("/api/win-model/predictions")
    body = resp.json()
    assert "methodology" not in body[0]


def test_get_team_prediction_includes_full_methodology(client):
    resp = client.get("/api/win-model/predictions/Boston Celtics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["team"] == "Boston Celtics"
    assert body["season"] == 2026
    assert body["predicted_wins"] == 47.0
    assert body["actual_wins"] is None
    assert body["methodology"]["model_comparison"]["winner"] == "gbm"
    assert body["methodology"]["n_training_rows"] == 270


def test_get_team_prediction_unknown_team_404s(client):
    resp = client.get("/api/win-model/predictions/Nonexistent Team")
    assert resp.status_code == 404


def test_get_methodology_standalone(client):
    resp = client.get("/api/win-model/methodology")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_comparison"]["winner"] == "gbm"
    assert body["model_comparison"]["knn_walk_forward_mae"] == 8.283


def test_top_features_present_for_available_columns(client):
    resp = client.get("/api/win-model/predictions")
    body = resp.json()
    boston = next(row for row in body if row["team"] == "Boston Celtics")
    assert boston["top_features"]["E_L"] == 13.0


def test_top_features_omits_missing_value_rather_than_sending_null(client):
    """SOS is NaN for the 2026 forecast row (see PREDICTIONS_DF's comment) — must
    be dropped from top_features, not sent as a null/NaN that a frontend chart
    would have to special-case."""
    resp = client.get("/api/win-model/predictions")
    body = resp.json()
    for row in body:
        assert "SOS" not in row["top_features"]


def test_row_to_prediction_includes_feature_when_present_and_not_nan():
    """Sanity check the omission above is specifically about NaN, not that a
    feature name is dropped unconditionally — direct unit test on the row
    helper, using the 2025 row (real SOS value) that /predictions never
    surfaces on its own (it only ever returns the latest season)."""
    from backend.api.routers.win_model import _row_to_prediction
    from backend.tests.api.conftest import PREDICTIONS_DF

    row_2025 = PREDICTIONS_DF[
        (PREDICTIONS_DF["Season"] == 2025) & (PREDICTIONS_DF["Team"] == "Boston Celtics")
    ].iloc[0]
    prediction = _row_to_prediction(row_2025, feature_names=["SOS", "E_L"])
    assert prediction.top_features == {"SOS": 0.02, "E_L": 15.0}

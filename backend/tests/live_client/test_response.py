import pandas as pd
import pytest

from live_client.response import NBAResponse

RESULT_SETS_PAYLOAD = {
    "resultSets": [
        {"name": "LeagueDashPlayerStats", "headers": ["PLAYER_ID", "PLAYER_NAME", "PTS"],
         "rowSet": [[1, "A Player", 20.5], [2, "B Player", 15.0]]},
        {"name": "Other", "headers": ["X"], "rowSet": [[1]]},
    ]
}

SINGLE_RESULT_SET_PAYLOAD = {
    "resultSet": {"name": "SeasonTotalsRegularSeason", "headers": ["PLAYER_ID", "GP"], "rowSet": [[1, 82]]}
}


def test_to_dict_and_to_json_roundtrip():
    import json

    response = NBAResponse(RESULT_SETS_PAYLOAD, result_set_name="LeagueDashPlayerStats")
    assert response.to_dict() == RESULT_SETS_PAYLOAD
    assert json.loads(response.to_json()) == RESULT_SETS_PAYLOAD


def test_to_dataframe_picks_named_result_set():
    response = NBAResponse(RESULT_SETS_PAYLOAD, result_set_name="LeagueDashPlayerStats")
    df = response.to_dataframe()
    assert list(df.columns) == ["PLAYER_ID", "PLAYER_NAME", "PTS"]
    assert len(df) == 2


def test_to_dataframe_is_memoized():
    response = NBAResponse(RESULT_SETS_PAYLOAD, result_set_name="LeagueDashPlayerStats")
    df1 = response.to_dataframe()
    df2 = response.to_dataframe()
    assert df1 is df2


def test_to_dataframe_unknown_result_set_name_raises():
    response = NBAResponse(RESULT_SETS_PAYLOAD, result_set_name="DoesNotExist")
    with pytest.raises(ValueError):
        response.to_dataframe()


def test_to_dataframe_handles_singular_result_set_key():
    response = NBAResponse(SINGLE_RESULT_SET_PAYLOAD, result_set_name="SeasonTotalsRegularSeason")
    df = response.to_dataframe()
    assert list(df.columns) == ["PLAYER_ID", "GP"]


def test_to_dataframe_raises_on_non_stats_shaped_payload():
    response = NBAResponse({"scoreboard": {"games": []}}, result_set_name="whatever")
    with pytest.raises(ValueError):
        response.to_dataframe()


def test_pre_built_dataframe_is_used_as_is_for_live_endpoints():
    df = pd.DataFrame({"gameId": ["001"], "homeTeam.score": [100]})
    response = NBAResponse({"scoreboard": {}}, dataframe=df)
    assert response.to_dataframe() is df


def test_requires_dataframe_or_result_set_name():
    with pytest.raises(ValueError):
        NBAResponse({"anything": True})

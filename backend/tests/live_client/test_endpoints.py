from unittest.mock import MagicMock

import pytest

from live_client.endpoints.base import SchemaValidationError
from live_client.endpoints.live.scoreboard import TodaysScoreboard
from live_client.endpoints.stats.season_totals import PlayerSeasonTotals

GOOD_SEASON_TOTALS_PAYLOAD = {
    "resultSets": [{
        "name": "LeagueDashPlayerStats",
        "headers": [
            "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
            "GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
            "FG_PCT", "FG3_PCT", "FT_PCT",
        ],
        "rowSet": [
            [1, "Player One", 1610612738, "BOS", 82, 2500, 1800, 400, 300, 80, 40, 150, 0.48, 0.38, 0.85],
        ],
    }]
}

# Simulates NBA.com silently renaming a column — the kind of upstream change this
# validation exists to catch (backend/AGENTS.md testing priority #2).
BROKEN_SEASON_TOTALS_PAYLOAD = {
    "resultSets": [{
        "name": "LeagueDashPlayerStats",
        "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "MIN", "POINTS"],
        "rowSet": [[1, "Player One", 1610612738, "BOS", 82, 2500, 1800]],
    }]
}


def _fake_client(payload):
    client = MagicMock()
    client.get_json.return_value = payload
    return client


class _NullCache:
    """A cache that always misses and discards writes — isolates a test from disk
    state without needing a real DiskCache + tmp_path in every test."""
    def get(self, *a, **k):
        return None

    def set(self, *a, **k):
        pass


def test_fetch_succeeds_with_well_formed_response():
    endpoint = PlayerSeasonTotals(season="2023-24", client=_fake_client(GOOD_SEASON_TOTALS_PAYLOAD), cache=_NullCache())
    df = endpoint.fetch().to_dataframe()
    assert len(df) == 1
    assert df.iloc[0]["PLAYER_NAME"] == "Player One"


def test_fetch_raises_schema_validation_error_on_renamed_column():
    endpoint = PlayerSeasonTotals(season="2023-24", client=_fake_client(BROKEN_SEASON_TOTALS_PAYLOAD), cache=_NullCache())
    with pytest.raises(SchemaValidationError, match="PTS"):
        endpoint.fetch()


def test_fetch_uses_cache_on_second_call():
    client = _fake_client(GOOD_SEASON_TOTALS_PAYLOAD)
    cache_store: dict = {}

    class _RecordingCache:
        def get(self, name, params, force_refresh=False):
            if force_refresh:
                return None
            return cache_store.get((name, tuple(sorted(params.items()))))

        def set(self, name, params, raw):
            cache_store[(name, tuple(sorted(params.items())))] = raw

    endpoint = PlayerSeasonTotals(season="2023-24", client=client, cache=_RecordingCache())
    endpoint.fetch()
    endpoint.fetch()
    assert client.get_json.call_count == 1  # second fetch was served from cache


def test_force_refresh_bypasses_cache_and_hits_client_again():
    client = _fake_client(GOOD_SEASON_TOTALS_PAYLOAD)
    cache_store: dict = {}

    class _RecordingCache:
        def get(self, name, params, force_refresh=False):
            if force_refresh:
                return None
            return cache_store.get((name, tuple(sorted(params.items()))))

        def set(self, name, params, raw):
            cache_store[(name, tuple(sorted(params.items())))] = raw

    endpoint = PlayerSeasonTotals(season="2023-24", client=client, cache=_RecordingCache())
    endpoint.fetch()
    endpoint.fetch(force_refresh=True)
    assert client.get_json.call_count == 2


LIVE_SCOREBOARD_PAYLOAD = {
    "scoreboard": {
        "gameDate": "2024-01-15",
        "games": [
            {
                "gameId": "0022300500",
                "gameStatus": 2,
                "gameStatusText": "Q3 05:23",
                "homeTeam": {"teamId": 1610612738, "teamTricode": "BOS", "score": 60},
                "awayTeam": {"teamId": 1610612747, "teamTricode": "LAL", "score": 55},
            }
        ],
    }
}


def test_live_endpoint_flattens_nested_json_into_dataframe():
    endpoint = TodaysScoreboard(client=_fake_client(LIVE_SCOREBOARD_PAYLOAD), cache=_NullCache())
    df = endpoint.fetch().to_dataframe()
    assert df.loc[0, "homeTeam.teamTricode"] == "BOS"
    assert df.loc[0, "awayTeam.score"] == 55

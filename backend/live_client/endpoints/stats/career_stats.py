"""backend/live_client/endpoints/stats/career_stats.py

Per-player career stats, broken down by season — built via nba_api's
PlayerCareerStats.
"""

from __future__ import annotations

from nba_api.stats.endpoints import PlayerCareerStats as _NbaApiPlayerCareerStats

from ..base import Endpoint


class PlayerCareerStats(Endpoint):
    """One player's regular-season stats for every season of their career.

    Expected schema (subset): PLAYER_ID, SEASON_ID, TEAM_ID, TEAM_ABBREVIATION,
    GP, GS, MIN, PTS, REB, AST. Verified live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "SeasonTotalsRegularSeason"
    expected_columns = (
        "PLAYER_ID", "SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION",
        "GP", "GS", "MIN", "PTS", "REB", "AST",
    )

    def __init__(self, player_id: int, per_mode: str = "PerGame", client=None, cache=None):
        super().__init__(client, cache)
        self.player_id = player_id
        self.params = {"PlayerID": player_id, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = _NbaApiPlayerCareerStats(
            player_id=self.params["PlayerID"],
            per_mode36=self.params["PerMode"],
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

"""backend/live_client/endpoints/stats/shot_chart.py

Shot-location detail for a player (optionally scoped to one season) — built via
nba_api's ShotChartDetail.
"""

from __future__ import annotations

from nba_api.stats.endpoints import ShotChartDetail as _NbaApiShotChartDetail

from ..base import Endpoint


class PlayerShotChart(Endpoint):
    """Every logged shot attempt for one player in one season.

    Expected schema (subset): GAME_ID, PLAYER_ID, TEAM_ID, PERIOD, LOC_X, LOC_Y,
    SHOT_DISTANCE, SHOT_MADE_FLAG, SHOT_TYPE, ACTION_TYPE. Verified live against
    stats.nba.com — see backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "Shot_Chart_Detail"
    expected_columns = (
        "GAME_ID", "PLAYER_ID", "TEAM_ID", "PERIOD", "LOC_X", "LOC_Y",
        "SHOT_DISTANCE", "SHOT_MADE_FLAG", "SHOT_TYPE", "ACTION_TYPE",
    )

    def __init__(
        self,
        player_id: int,
        season: str,
        team_id: int = 0,
        season_type: str = "Regular Season",
        client=None,
        cache=None,
    ):
        """
        Parameters
        ----------
        player_id : int
            NBA.com player ID.
        season : str
            e.g. "2023-24".
        team_id : int
            0 for "any team" (handles players who were traded mid-season).
        """
        super().__init__(client, cache)
        self.player_id = player_id
        self.season = season
        self.params = {
            "PlayerID": player_id, "TeamID": team_id, "Season": season, "SeasonType": season_type,
        }

    def _request(self) -> dict:
        endpoint = _NbaApiShotChartDetail(
            team_id=self.params["TeamID"],
            player_id=self.params["PlayerID"],
            season_nullable=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            context_measure_simple="FGA",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

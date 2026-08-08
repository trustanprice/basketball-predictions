"""backend/live_client/endpoints/stats/shot_chart.py

Shot-location detail for a player (optionally scoped to one season) — `shotchartdetail`.
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/shotchartdetail"


class PlayerShotChart(Endpoint):
    """Every logged shot attempt for one player in one season.

    Expected schema (subset): GAME_ID, PLAYER_ID, TEAM_ID, PERIOD, LOC_X, LOC_Y,
    SHOT_DISTANCE, SHOT_MADE_FLAG, SHOT_TYPE, ACTION_TYPE.
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
            "PlayerID": player_id,
            "TeamID": team_id,
            "GameID": "",
            "Season": season,
            "SeasonType": season_type,
            "ContextMeasure": "FGA",
            "LeagueID": "00",
            "PlayerPosition": "",
            "Outcome": "",
            "Location": "",
            "Month": 0,
            "SeasonSegment": "",
            "DateFrom": "",
            "DateTo": "",
            "OpponentTeamID": 0,
            "VsConference": "",
            "VsDivision": "",
            "RookieYear": "",
            "GameSegment": "",
            "Period": 0,
            "LastNGames": 0,
        }

    def _request(self) -> dict:
        return self.client.get_json(URL, params=self.params)

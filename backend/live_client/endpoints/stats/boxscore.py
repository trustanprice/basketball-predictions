"""backend/live_client/endpoints/stats/boxscore.py

Historical (completed-game) traditional box score — `boxscoretraditionalv2`.
For the currently-in-progress game, see endpoints/live/live_boxscore.py instead —
different endpoint, different freshness, different schema.
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/boxscoretraditionalv2"


class GameBoxScore(Endpoint):
    """Player-level traditional box score for one completed game.

    Expected schema (subset): GAME_ID, TEAM_ID, PLAYER_ID, PLAYER_NAME, MIN,
    PTS, REB, AST, STL, BLK, TO, PLUS_MINUS.
    """

    result_set_name = "PlayerStats"
    expected_columns = (
        "GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME",
        "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "PLUS_MINUS",
    )

    def __init__(self, game_id: str, client=None, cache=None):
        """
        Parameters
        ----------
        game_id : str
            NBA.com 10-digit game ID, e.g. "0022300001".
        """
        super().__init__(client, cache)
        self.game_id = game_id
        self.params = {
            "GameID": game_id,
            "StartPeriod": 0,
            "EndPeriod": 10,
            "StartRange": 0,
            "EndRange": 28800,
            "RangeType": 0,
        }

    def _request(self) -> dict:
        return self.client.get_json(URL, params=self.params)

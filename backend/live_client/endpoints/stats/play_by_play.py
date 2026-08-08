"""backend/live_client/endpoints/stats/play_by_play.py

Historical (completed-game) play-by-play log — `playbyplayv2`.
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/playbyplayv2"


class GamePlayByPlay(Endpoint):
    """Full play-by-play event log for one completed game.

    Expected schema (subset): GAME_ID, EVENTNUM, EVENTMSGTYPE, PERIOD,
    PCTIMESTRING, HOMEDESCRIPTION, VISITORDESCRIPTION, SCORE.
    """

    result_set_name = "PlayByPlay"
    expected_columns = (
        "GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "PERIOD",
        "PCTIMESTRING", "HOMEDESCRIPTION", "VISITORDESCRIPTION", "SCORE",
    )

    def __init__(self, game_id: str, client=None, cache=None):
        super().__init__(client, cache)
        self.game_id = game_id
        self.params = {
            "GameID": game_id,
            "StartPeriod": 0,
            "EndPeriod": 10,
        }

    def _request(self) -> dict:
        return self.client.get_json(URL, params=self.params)

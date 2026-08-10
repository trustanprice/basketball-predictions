"""backend/live_client/endpoints/stats/play_by_play.py

Historical (completed-game) play-by-play log — built via nba_api's PlayByPlayV3.
NOT V2: nba_api's own source flags PlayByPlayV2 as deprecated — "The NBA API no
longer returns data for PlayByPlayV2 (returns empty JSON)," confirmed by reading
nba_api's source (github.com/swar/nba_api issue #591). See boxscore.py's
docstring for why this overrides _build_response the same way.
"""

from __future__ import annotations

from nba_api.stats.endpoints import PlayByPlayV3

from ...response import NBAResponse
from ..base import Endpoint


class GamePlayByPlay(Endpoint):
    """Full play-by-play event log for one completed game.

    Expected schema (subset): gameId, actionNumber, clock, period, teamId,
    personId, description, actionType, scoreHome, scoreAway. Verified live
    against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    expected_columns = (
        "gameId", "actionNumber", "clock", "period", "teamId",
        "personId", "description", "actionType", "scoreHome", "scoreAway",
    )

    def __init__(self, game_id: str, client=None, cache=None):
        super().__init__(client, cache)
        self.game_id = game_id
        self.params = {"GameID": game_id}
        self._dataframe = None

    def _request(self) -> dict:
        endpoint = PlayByPlayV3(
            game_id=self.params["GameID"],
            timeout=self.client.timeout,
            get_request=False,
        )
        raw = self.client.get_via_nba_api(endpoint)
        self._dataframe = endpoint.play_by_play.get_data_frame()
        return raw

    def _build_response(self, raw: dict) -> NBAResponse:
        return NBAResponse(raw, dataframe=self._dataframe)

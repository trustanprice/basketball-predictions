"""backend/live_client/endpoints/stats/boxscore.py

Historical (completed-game) traditional box score — built via nba_api's
BoxScoreTraditionalV3. NOT V2: nba_api's own source flags BoxScoreTraditionalV2
as deprecated and no longer returning data as of the 2025-26 season (confirmed
live — V2 comes back empty). V3 uses a nested JSON shape (camelCase, a
`statistics` sub-object per player) rather than the classic resultSets/rowSet
table, so this overrides _build_response to use nba_api's own dataframe
flattening instead of response.py's generic resultSets parser — same pattern
endpoints/live/*.py already uses for other nested-shaped responses.

For the currently-in-progress game, see endpoints/live/live_boxscore.py instead —
different endpoint, different freshness, different (though similarly nested) schema.
"""

from __future__ import annotations

from nba_api.stats.endpoints import BoxScoreTraditionalV3

from ...response import NBAResponse
from ..base import Endpoint


class GameBoxScore(Endpoint):
    """Player-level traditional box score for one completed game.

    Expected schema (subset): gameId, teamId, personId, nameI, minutes, points,
    reboundsTotal, assists, steals, blocks, turnovers, plusMinusPoints. Verified
    live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    expected_columns = (
        "gameId", "teamId", "personId", "nameI", "minutes",
        "points", "reboundsTotal", "assists", "steals", "blocks", "turnovers", "plusMinusPoints",
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
        self.params = {"GameID": game_id}
        self._dataframe = None

    def _request(self) -> dict:
        endpoint = BoxScoreTraditionalV3(
            game_id=self.params["GameID"],
            timeout=self.client.timeout,
            get_request=False,
        )
        raw = self.client.get_via_nba_api(endpoint)
        # endpoint is already fired at this point (get_via_nba_api called
        # .get_request()) — pulling the dataframe here is free, no extra call.
        self._dataframe = endpoint.player_stats.get_data_frame()
        return raw

    def _build_response(self, raw: dict) -> NBAResponse:
        return NBAResponse(raw, dataframe=self._dataframe)

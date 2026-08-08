"""backend/live_client/endpoints/live/live_boxscore.py

In-progress (or just-finished) box score for one game — cdn.nba.com's live box
score feed. For a completed historical game, use endpoints/stats/boxscore.py
instead — that one is the stable, backfilled source; this one is only useful
while (or shortly after) a game is being played.
"""

from __future__ import annotations

import pandas as pd

from ...client import LIVE_BASE_URL
from ...response import NBAResponse
from ..base import Endpoint

URL_TEMPLATE = f"{LIVE_BASE_URL}/boxscore/boxscore_{{game_id}}.json"


class LiveBoxScore(Endpoint):
    """Player-level live box score for one game, flattened from both teams'
    player lists.

    Expected schema (subset, after flattening): personId, name, teamId,
    teamTricode, statistics.points, statistics.reboundsTotal, statistics.assists.
    """

    expected_columns = (
        "personId", "name", "teamId", "teamTricode",
        "statistics.points", "statistics.reboundsTotal", "statistics.assists",
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
        self.params = {}
        self._url = URL_TEMPLATE.format(game_id=game_id)

    def _request(self) -> dict:
        return self.client.get_json(self._url)

    def cache_key_params(self) -> dict:
        return {"game_id": self.game_id}

    def _build_response(self, raw: dict) -> NBAResponse:
        game = raw.get("game", {})
        players = []
        for side in ("homeTeam", "awayTeam"):
            team = game.get(side, {})
            for player in team.get("players", []):
                players.append({
                    **player,
                    "teamId": team.get("teamId"),
                    "teamTricode": team.get("teamTricode"),
                })
        df = pd.json_normalize(players, sep=".")
        return NBAResponse(raw, dataframe=df)

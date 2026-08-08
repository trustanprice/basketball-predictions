"""backend/live_client/endpoints/live/scoreboard.py

Today's games and live scores — cdn.nba.com's live scoreboard feed. In-game data:
different host, different freshness (seconds-old, not season-stable), and a nested
JSON shape with no resultSets, unlike everything in endpoints/stats/.
"""

from __future__ import annotations

import pandas as pd

from ...client import LIVE_BASE_URL
from ...response import NBAResponse
from ..base import Endpoint

URL = f"{LIVE_BASE_URL}/scoreboard/todaysScoreboard_00.json"


class TodaysScoreboard(Endpoint):
    """Every game on the current NBA.com scoreboard (scheduled, live, or final).

    Expected schema (subset, after flattening): gameId, gameStatus,
    gameStatusText, homeTeam.teamId, homeTeam.teamTricode, homeTeam.score,
    awayTeam.teamId, awayTeam.teamTricode, awayTeam.score.
    """

    expected_columns = (
        "gameId", "gameStatus", "gameStatusText",
        "homeTeam.teamId", "homeTeam.teamTricode", "homeTeam.score",
        "awayTeam.teamId", "awayTeam.teamTricode", "awayTeam.score",
    )

    def __init__(self, client=None, cache=None):
        super().__init__(client, cache)
        self.params = {}  # no query params — always "today", per NBA.com's own feed

    def _request(self) -> dict:
        return self.client.get_json(URL)

    def cache_key_params(self) -> dict:
        # Cache key still needs to vary by day, even though the request itself
        # takes no params — otherwise a cached "today" from yesterday would stick.
        return {"date": pd.Timestamp.utcnow().strftime("%Y-%m-%d")}

    def _build_response(self, raw: dict) -> NBAResponse:
        games = raw.get("scoreboard", {}).get("games", [])
        df = pd.json_normalize(games, sep=".")
        return NBAResponse(raw, dataframe=df)

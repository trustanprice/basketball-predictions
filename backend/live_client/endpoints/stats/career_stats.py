"""backend/live_client/endpoints/stats/career_stats.py

Per-player career stats, broken down by season — `playercareerstats`.
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/playercareerstats"


class PlayerCareerStats(Endpoint):
    """One player's regular-season stats for every season of their career.

    Expected schema (subset): PLAYER_ID, SEASON_ID, TEAM_ID, TEAM_ABBREVIATION,
    GP, GS, MIN, PTS, REB, AST.
    """

    result_set_name = "SeasonTotalsRegularSeason"
    expected_columns = (
        "PLAYER_ID", "SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION",
        "GP", "GS", "MIN", "PTS", "REB", "AST",
    )

    def __init__(self, player_id: int, per_mode: str = "PerGame", client=None, cache=None):
        super().__init__(client, cache)
        self.player_id = player_id
        self.params = {
            "PlayerID": player_id,
            "PerMode": per_mode,
            "LeagueID": "00",
        }

    def _request(self) -> dict:
        return self.client.get_json(URL, params=self.params)

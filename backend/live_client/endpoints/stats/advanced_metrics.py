"""backend/live_client/endpoints/stats/advanced_metrics.py

League-wide player advanced metrics — `leaguedashplayerstats` (MeasureType=Advanced).
Same underlying NBA.com endpoint as season_totals.py but a genuinely different
response schema (rating/percentage columns instead of counting stats), so it gets
its own class and its own expected_columns rather than a parameter on
PlayerSeasonTotals — see backend/AGENTS.md ("one class per data source").
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/leaguedashplayerstats"


class PlayerAdvancedStats(Endpoint):
    """League-wide advanced metrics for the given season.

    Expected schema (subset): PLAYER_ID, PLAYER_NAME, TEAM_ID, OFF_RATING,
    DEF_RATING, NET_RATING, USG_PCT, TS_PCT, AST_PCT, REB_PCT.
    """

    result_set_name = "LeagueDashPlayerStats"
    expected_columns = (
        "PLAYER_ID", "PLAYER_NAME", "TEAM_ID",
        "OFF_RATING", "DEF_RATING", "NET_RATING", "USG_PCT", "TS_PCT", "AST_PCT", "REB_PCT",
    )

    def __init__(
        self,
        season: str,
        season_type: str = "Regular Season",
        per_mode: str = "PerGame",
        client=None,
        cache=None,
    ):
        super().__init__(client, cache)
        self.season = season
        self.params = {
            "Season": season,
            "SeasonType": season_type,
            "PerMode": per_mode,
            "MeasureType": "Advanced",
            "LeagueID": "00",
            "PlayerExperience": "",
            "PlayerPosition": "",
            "StarterBench": "",
            "TeamID": 0,
            "Outcome": "",
            "Location": "",
            "Month": 0,
            "SeasonSegment": "",
            "DateFrom": "",
            "DateTo": "",
            "OpponentTeamID": 0,
            "VsConference": "",
            "VsDivision": "",
            "GameSegment": "",
            "Period": 0,
            "LastNGames": 0,
            "PORound": 0,
            "PaceAdjust": "N",
            "PlusMinus": "N",
            "Rank": "N",
        }

    def _request(self) -> dict:
        return self.client.get_json(URL, params=self.params)

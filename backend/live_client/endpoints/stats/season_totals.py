"""backend/live_client/endpoints/stats/season_totals.py

League-wide player season totals — `leaguedashplayerstats` (MeasureType=Base).
Historical/season data: one row per player for the given season.
"""

from __future__ import annotations

from ...client import STATS_BASE_URL
from ..base import Endpoint

URL = f"{STATS_BASE_URL}/leaguedashplayerstats"


class PlayerSeasonTotals(Endpoint):
    """Season totals for every player who logged minutes in `season`.

    Expected schema (subset): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION,
    GP, MIN, PTS, REB, AST, STL, BLK, TOV, FG_PCT, FG3_PCT, FT_PCT.
    """

    result_set_name = "LeagueDashPlayerStats"
    expected_columns = (
        "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
        "GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
        "FG_PCT", "FG3_PCT", "FT_PCT",
    )

    def __init__(
        self,
        season: str,
        season_type: str = "Regular Season",
        per_mode: str = "Totals",
        client=None,
        cache=None,
    ):
        """
        Parameters
        ----------
        season : str
            NBA season string, e.g. "2023-24".
        season_type : str
            "Regular Season" | "Playoffs" | "Pre Season".
        per_mode : str
            "Totals" | "PerGame" | "Per36".
        """
        super().__init__(client, cache)
        self.season = season
        self.params = {
            "Season": season,
            "SeasonType": season_type,
            "PerMode": per_mode,
            "MeasureType": "Base",
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

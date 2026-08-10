"""backend/live_client/endpoints/stats/season_totals.py

League-wide player season totals — built via nba_api's LeagueDashPlayerStats
(MeasureType=Base), sent through our own retrying client and schema-validated
response wrapper (see backend/live_client/client.py's module docstring for why
nba_api alone isn't enough). Historical/season data: one row per player for the
given season.
"""

from __future__ import annotations

from nba_api.stats.endpoints import LeagueDashPlayerStats

from ..base import Endpoint


class PlayerSeasonTotals(Endpoint):
    """Season totals for every player who logged minutes in `season`.

    Expected schema (subset): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION,
    GP, MIN, PTS, REB, AST, STL, BLK, TOV, FG_PCT, FG3_PCT, FT_PCT. Verified live
    against stats.nba.com — see backend/tests/live_client/test_integration_real_network.py.
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
        # Kept minimal (just the identifying params) for the cache key — nba_api
        # fills in the other ~40 NBA.com params with its own current defaults,
        # see _request().
        self.params = {"Season": season, "SeasonType": season_type, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = LeagueDashPlayerStats(
            season=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            per_mode_detailed=self.params["PerMode"],
            measure_type_detailed_defense="Base",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

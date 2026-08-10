"""backend/live_client/endpoints/stats/team_season_stats.py

League-wide TEAM season stats — built via nba_api's LeagueDashTeamStats, the
team-level sibling of season_totals.py/advanced_metrics.py's player-level
LeagueDashPlayerStats calls (same endpoint family, same one-call-per-season
shape, just TeamID-keyed instead of PlayerID-keyed). Two classes, not one
with a MeasureType param, matching this package's "one class per data
source" convention (see advanced_metrics.py) -- Base and Advanced are
genuinely different schemas (counting stats vs. rating/pace percentages).
"""

from __future__ import annotations

from nba_api.stats.endpoints import LeagueDashTeamStats

from ..base import Endpoint


class TeamSeasonStats(Endpoint):
    """League-wide team season totals (Base measure type) for `season`.

    Expected schema (subset): TEAM_ID, TEAM_NAME, GP, FGA, FG3A, PTS.
    Verified live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "LeagueDashTeamStats"
    expected_columns = ("TEAM_ID", "TEAM_NAME", "GP", "FGA", "FG3A", "PTS")

    def __init__(self, season: str, season_type: str = "Regular Season", per_mode: str = "PerGame", client=None, cache=None):
        super().__init__(client, cache)
        self.season = season
        self.params = {"Season": season, "SeasonType": season_type, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = LeagueDashTeamStats(
            season=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            per_mode_detailed=self.params["PerMode"],
            measure_type_detailed_defense="Base",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)


class TeamAdvancedStats(Endpoint):
    """League-wide team advanced metrics (pace, ratings, AST%) for `season`.

    Expected schema (subset): TEAM_ID, TEAM_NAME, PACE, AST_PCT, TM_TOV_PCT,
    OFF_RATING, DEF_RATING. Verified live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "LeagueDashTeamStats"
    expected_columns = ("TEAM_ID", "TEAM_NAME", "PACE", "AST_PCT", "TM_TOV_PCT", "OFF_RATING", "DEF_RATING")

    def __init__(self, season: str, season_type: str = "Regular Season", per_mode: str = "PerGame", client=None, cache=None):
        super().__init__(client, cache)
        self.season = season
        self.params = {"Season": season, "SeasonType": season_type, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = LeagueDashTeamStats(
            season=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            per_mode_detailed=self.params["PerMode"],
            measure_type_detailed_defense="Advanced",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

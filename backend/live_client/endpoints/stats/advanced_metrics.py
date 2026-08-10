"""backend/live_client/endpoints/stats/advanced_metrics.py

League-wide player advanced metrics — built via nba_api's LeagueDashPlayerStats
(MeasureType=Advanced). Same underlying NBA.com endpoint as season_totals.py but
a genuinely different response schema (rating/percentage columns instead of
counting stats), so it gets its own class and its own expected_columns rather
than a parameter on PlayerSeasonTotals — see backend/AGENTS.md ("one class per
data source").
"""

from __future__ import annotations

from nba_api.stats.endpoints import LeagueDashPlayerStats

from ..base import Endpoint


class PlayerAdvancedStats(Endpoint):
    """League-wide advanced metrics for the given season.

    Expected schema (subset): PLAYER_ID, PLAYER_NAME, TEAM_ID, OFF_RATING,
    DEF_RATING, NET_RATING, USG_PCT, TS_PCT, AST_PCT, REB_PCT, DREB_PCT,
    TM_TOV_PCT. Verified live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py. Note:
    TM_TOV_PCT, not TOV_PCT — an earlier version of this file declared TOV_PCT,
    which turned out not to exist in the real response at all (caught by that
    same live test, not by the schema-mismatch mechanism this validation exists
    for — the assumed column name was simply wrong from the start).

    DREB_PCT and TM_TOV_PCT are included because backend/ratings/player_power_rankings
    reads them directly — without declaring them here, an upstream rename of either
    column would silently corrupt a rating instead of raising (see backend/AGENTS.md:
    "an upstream field rename should raise loudly").
    """

    result_set_name = "LeagueDashPlayerStats"
    expected_columns = (
        "PLAYER_ID", "PLAYER_NAME", "TEAM_ID",
        "OFF_RATING", "DEF_RATING", "NET_RATING", "USG_PCT", "TS_PCT", "AST_PCT", "REB_PCT",
        "DREB_PCT", "TM_TOV_PCT",
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
        self.params = {"Season": season, "SeasonType": season_type, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = LeagueDashPlayerStats(
            season=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            per_mode_detailed=self.params["PerMode"],
            measure_type_detailed_defense="Advanced",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

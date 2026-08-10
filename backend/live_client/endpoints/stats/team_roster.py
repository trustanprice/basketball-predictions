"""backend/live_client/endpoints/stats/team_roster.py

A team's current roster -- built via nba_api's CommonTeamRoster. Unlike the
rest of stats/ (season-final historical data, safe to cache indefinitely),
rosters move all through the offseason (trades, signings, waivers), so this
endpoint defaults to a short cache TTL instead of the base Endpoint's
never-expires default -- see backend/AGENTS.md.
"""

from __future__ import annotations

from nba_api.stats.endpoints import CommonTeamRoster as _NbaApiCommonTeamRoster

from ...cache import DiskCache
from ..base import Endpoint

# Short relative to every other endpoint in this package (which cache
# indefinitely -- a completed season's box score never changes). A roster can
# move through trades/signings/waivers at any point in the offseason, so a
# stale roster is a real correctness risk here, not just a missed
# optimization. 6 hours balances "don't hammer NBA.com on every request"
# against "don't serve a week-old roster deep into free agency." Callers that
# need the absolute latest can still pass fetch(force_refresh=True).
ROSTER_CACHE_TTL_SECONDS = 6 * 60 * 60


class TeamRoster(Endpoint):
    """One team's roster for `season` (e.g. "2026-27").

    Expected schema (subset): PLAYER, PLAYER_ID, AGE, EXP, POSITION. Verified
    live against stats.nba.com -- see
    backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "CommonTeamRoster"
    expected_columns = ("PLAYER", "PLAYER_ID", "AGE", "EXP", "POSITION")

    def __init__(self, team_id: int, season: str, client=None, cache=None):
        super().__init__(client, cache if cache is not None else DiskCache(ttl_seconds=ROSTER_CACHE_TTL_SECONDS))
        self.team_id = team_id
        self.season = season
        self.params = {"TeamID": team_id, "Season": season}

    def _request(self) -> dict:
        endpoint = _NbaApiCommonTeamRoster(
            team_id=self.params["TeamID"],
            season=self.params["Season"],
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

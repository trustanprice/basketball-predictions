"""backend/live_client/endpoints/stats/shot_chart.py

Shot-location detail for a player (optionally scoped to one season) — built via
nba_api's ShotChartDetail.
"""

from __future__ import annotations

from nba_api.stats.endpoints import ShotChartDetail as _NbaApiShotChartDetail

from ..base import Endpoint


class PlayerShotChart(Endpoint):
    """Every logged shot attempt for one player in one season.

    Expected schema (subset): GAME_ID, PLAYER_ID, TEAM_ID, PERIOD, LOC_X, LOC_Y,
    SHOT_DISTANCE, SHOT_MADE_FLAG, SHOT_TYPE, ACTION_TYPE. Verified live against
    stats.nba.com — see backend/tests/live_client/test_integration_real_network.py.
    """

    result_set_name = "Shot_Chart_Detail"
    expected_columns = (
        "GAME_ID", "PLAYER_ID", "TEAM_ID", "PERIOD", "LOC_X", "LOC_Y",
        "SHOT_DISTANCE", "SHOT_MADE_FLAG", "SHOT_TYPE", "ACTION_TYPE",
    )

    def __init__(
        self,
        player_id: int,
        season: str,
        team_id: int = 0,
        season_type: str = "Regular Season",
        client=None,
        cache=None,
    ):
        """
        Parameters
        ----------
        player_id : int
            NBA.com player ID.
        season : str
            e.g. "2023-24".
        team_id : int
            0 for "any team" (handles players who were traded mid-season).
        """
        super().__init__(client, cache)
        self.player_id = player_id
        self.season = season
        self.params = {
            "PlayerID": player_id, "TeamID": team_id, "Season": season, "SeasonType": season_type,
        }

    def _request(self) -> dict:
        endpoint = _NbaApiShotChartDetail(
            team_id=self.params["TeamID"],
            player_id=self.params["PlayerID"],
            season_nullable=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            context_measure_simple="FGA",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)


class TeamShotChart(Endpoint):
    """Every logged shot attempt for one team in one season — either the
    team's own offense, or (via `opponent_team_id`) every shot taken
    *against* that team, a real defensive-shape proxy (e.g. "allows a lot of
    restricted-area shots" vs. "forces mid-range/away from the rim").

    Confirmed live which ShotChartDetail parameter combination means what
    (not guessed): `team_id=X, opponent_team_id=0` returns only shots whose
    TEAM_NAME is team X (its offense); `team_id=0, opponent_team_id=X`
    returns shots whose TEAM_NAME is every *other* team (shots taken against
    X, i.e. X's defense) — see
    backend/tests/live_client/test_integration_real_network.py.

    Expected schema (subset): GAME_ID, TEAM_ID, TEAM_NAME, LOC_X, LOC_Y,
    SHOT_ZONE_BASIC, SHOT_MADE_FLAG.
    """

    result_set_name = "Shot_Chart_Detail"
    expected_columns = ("GAME_ID", "TEAM_ID", "TEAM_NAME", "LOC_X", "LOC_Y", "SHOT_ZONE_BASIC", "SHOT_MADE_FLAG")

    def __init__(
        self,
        season: str,
        team_id: int = 0,
        opponent_team_id: int = 0,
        season_type: str = "Regular Season",
        client=None,
        cache=None,
    ):
        """
        Parameters
        ----------
        season : str
            e.g. "2023-24".
        team_id : int
            The team whose own shots to fetch (offense). 0 if fetching by
            `opponent_team_id` instead.
        opponent_team_id : int
            The team whose *opponents'* shots to fetch (defense — what shots
            this team allowed). 0 if fetching by `team_id` instead.

        Exactly one of `team_id`/`opponent_team_id` should be non-zero — this
        is a thin wrapper, not a query builder, so it doesn't enforce that
        itself (see module docstring for what each combination actually
        returns).
        """
        super().__init__(client, cache)
        self.season = season
        self.params = {
            "TeamID": team_id, "OpponentTeamID": opponent_team_id,
            "Season": season, "SeasonType": season_type,
        }

    def _request(self) -> dict:
        endpoint = _NbaApiShotChartDetail(
            team_id=self.params["TeamID"],
            player_id=0,
            opponent_team_id=self.params["OpponentTeamID"],
            season_nullable=self.params["Season"],
            season_type_all_star=self.params["SeasonType"],
            context_measure_simple="FGA",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

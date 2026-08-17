"""backend/live_client/endpoints/stats/schedule.py

Full-season game-by-game schedule, via nba_api's ScheduleLeagueV2 -- built for
backend/win_model/schedule_simulation.py, which needs every regular-season
matchup (home/away) to simulate a season game-by-game instead of relying on
season-aggregate features alone.

Not a standard stats.nba.com `resultSets` response -- like endpoints/live/*.py,
this is nested JSON (`leagueSchedule.gameDates[].games[]`), so it overrides
`_build_response()` instead of using the generic resultSets parser. It's still
fetched through nba_api (stats.nba.com host, not cdn.nba.com), so it goes
through `get_via_nba_api()` for the same retry/backoff policy as every other
endpoints/stats/ class -- it just can't reuse NBAResponse's generic dataframe
parsing.

gameId prefixes (undocumented but stable -- confirmed by inspecting a full
season's worth of ids): '001' preseason, '002' regular season, '003'/'005'/'006'
All-Star/exhibition, '004' playoffs. Only regular season is in scope here.
"""

from __future__ import annotations

import pandas as pd
from nba_api.stats.endpoints import scheduleleaguev2

from ...response import NBAResponse
from ..base import Endpoint

REGULAR_SEASON_GAME_ID_PREFIX = "002"


class LeagueSchedule(Endpoint):
    """Every regular-season game on the schedule for `season` (e.g. "2026-27").

    Expected schema (subset): gameId, gameDateEst, homeTeam_teamId,
    awayTeam_teamId. Includes both played and not-yet-played games -- callers
    needing only future games should filter on gameStatus themselves (1 =
    scheduled, 2 = live, 3 = final).

    NBA Cup knockout games (semifinal/championship) are TBD-vs-TBD in the raw
    feed until the group stage completes and are dropped here (no resolvable
    team id) -- this means the schedule is a small number of games short of
    the full 1,230 until the Cup bracket is set. See ScheduleLeagueV2's own
    'gameLabel' field if a caller needs Cup context.
    """

    expected_columns = ("gameId", "gameDateEst", "homeTeam_teamId", "awayTeam_teamId")

    def __init__(self, season: str, client=None, cache=None):
        super().__init__(client, cache)
        self.season = season
        self.params = {"Season": season}

    def _request(self) -> dict:
        endpoint = scheduleleaguev2.ScheduleLeagueV2(
            season=self.params["Season"],
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

    def _build_response(self, raw: dict) -> NBAResponse:
        games = []
        for game_date in raw.get("leagueSchedule", {}).get("gameDates", []):
            games.extend(game_date.get("games", []))
        df = pd.json_normalize(games, sep="_")
        if not df.empty:
            df = df[df["gameId"].str.startswith(REGULAR_SEASON_GAME_ID_PREFIX)]
            df = df[(df["homeTeam_teamId"] > 0) & (df["awayTeam_teamId"] > 0)]
        return NBAResponse(raw, dataframe=df.reset_index(drop=True))

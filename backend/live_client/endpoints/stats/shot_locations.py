"""backend/live_client/endpoints/stats/shot_locations.py

League-wide, per-player shot attempts broken down by court zone for one
season -- built via nba_api's LeagueDashPlayerShotLocations. One call covers
every qualifying player in the league for that season (same shape as
season_totals.py/advanced_metrics.py), not one call per player -- this is
what makes it usable as an input to ratings/player_development.py's
archetype classification across many historical seasons without the request
volume that a per-player endpoint (like career_stats.py) would need.

Unlike every other stats/ endpoint, the raw response here is NOT a flat
resultSets/rowSet table. Confirmed live (not guessed):
  - `raw["resultSets"]` is a single dict here, not the list every other
    endpoint in this package returns.
  - Its "headers" field holds two header-group dicts: one named "columns"
    whose `columnNames` is actually the FULL flat 30-name column list for
    this response (identity names, then FGM/FGA/FG_PCT repeating once per
    zone -- the "columns" name is misleading, it is not just the identity
    columns); the other, named "SHOT_CATEGORY", holds the 8 zone labels
    (Restricted Area, In The Paint (Non-RA), Mid-Range, Left Corner 3, Right
    Corner 3, Above the Break 3, Backcourt, Corner 3) plus `columnsToSkip`
    (6 -- how many of the 30 flat columns are pure identity, unprefixed)
    and `columnSpan` (3 -- FGM/FGA/FG_PCT per zone).
  - rowSet itself is a plain flat 30-value-per-row list, in exactly that
    order (6 identity values, then 8 zones x 3 stats each) -- the "header
    groups" describe how to *label* the row, not how it's shaped.
response.py's generic parser assumes a flat resultSets list with simple
string headers, so this overrides _build_response() to hand-parse the shape
above -- same "non-standard shape" category as boxscore.py/play_by_play.py,
though the actual parsing differs since this doesn't have a friendly
alternate representation to reuse (see the git history of this file for a
first attempt with the header groups' roles reversed -- worth reading before
"fixing" this again on a hunch instead of re-verifying live).
"""

from __future__ import annotations

import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerShotLocations as _NbaApiLeagueDashPlayerShotLocations

from ...response import NBAResponse
from ..base import Endpoint


class PlayerShotLocations(Endpoint):
    """Every qualifying player's shot attempts for `season`, by zone.

    Expected schema (subset): PLAYER_ID, PLAYER_NAME, TEAM_ID, and, per zone,
    `"{zone}_FGA"` -- e.g. "Restricted Area_FGA", "Above the Break 3_FGA".
    Verified live against stats.nba.com — see
    backend/tests/live_client/test_integration_real_network.py.
    """

    expected_columns = ("PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "Restricted Area_FGA")

    def __init__(self, season: str, per_mode: str = "PerGame", client=None, cache=None):
        super().__init__(client, cache)
        self.season = season
        self.params = {"Season": season, "PerMode": per_mode}

    def _request(self) -> dict:
        endpoint = _NbaApiLeagueDashPlayerShotLocations(
            season=self.params["Season"],
            per_mode_detailed=self.params["PerMode"],
            distance_range="By Zone",
            timeout=self.client.timeout,
            get_request=False,
        )
        return self.client.get_via_nba_api(endpoint)

    def _build_response(self, raw: dict) -> NBAResponse:
        result_sets = raw["resultSets"]
        headers = result_sets["headers"]
        flat_names = next(h for h in headers if h["name"] == "columns")["columnNames"]
        zone_group = next(h for h in headers if h["name"] != "columns")
        n_skip = zone_group["columnsToSkip"]
        zone_span = zone_group["columnSpan"]

        columns = list(flat_names[:n_skip])
        for i, zone in enumerate(zone_group["columnNames"]):
            start = n_skip + i * zone_span
            columns.extend(f"{zone}_{sub}" for sub in flat_names[start:start + zone_span])

        df = pd.DataFrame(result_sets["rowSet"], columns=columns)
        for col in columns[n_skip:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return NBAResponse(raw, dataframe=df)

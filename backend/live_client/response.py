"""backend/live_client/response.py

Wraps raw NBA.com JSON so nothing downstream of the client layer ever touches
parsed JSON directly — always to_dict()/to_json()/to_dataframe() (see
backend/AGENTS.md).
"""

from __future__ import annotations

import json

import pandas as pd


class NBAResponse:
    """Wraps one endpoint's raw JSON response.

    Two ways to build the dataframe view:
      - `result_set_name` (stats.nba.com endpoints): parsed lazily via the
        generic `resultSets: [{name, headers, rowSet}]` shape shared by every
        endpoints/stats/ class.
      - `dataframe` (live/ endpoints): passed in pre-built, since cdn.nba.com's
        nested-object JSON shape has no generic tabular form — each live
        endpoint knows how to flatten its own response.
    """

    def __init__(
        self,
        raw: dict,
        dataframe: pd.DataFrame | None = None,
        result_set_name: str | None = None,
    ):
        if dataframe is None and result_set_name is None:
            raise ValueError("NBAResponse needs either dataframe= or result_set_name=")
        self._raw = raw
        self._dataframe = dataframe
        self._result_set_name = result_set_name

    def to_dict(self) -> dict:
        return self._raw

    def to_json(self, **kwargs) -> str:
        return json.dumps(self._raw, **kwargs)

    def to_dataframe(self) -> pd.DataFrame:
        if self._dataframe is None:
            self._dataframe = self._parse_result_sets(self._result_set_name)
        return self._dataframe

    def _parse_result_sets(self, name: str) -> pd.DataFrame:
        result_sets = self._raw.get("resultSets")
        if result_sets is None:
            single = self._raw.get("resultSet")
            result_sets = [single] if single else None
        if not result_sets:
            raise ValueError(
                "Response has neither 'resultSets' nor 'resultSet' — not a "
                "stats.nba.com-shaped response. Pass dataframe= explicitly instead."
            )

        matches = [rs for rs in result_sets if rs.get("name") == name]
        if not matches:
            available = [rs.get("name") for rs in result_sets]
            raise ValueError(f"No resultSet named {name!r} in response; available: {available}")

        chosen = matches[0]
        return pd.DataFrame(chosen["rowSet"], columns=chosen["headers"])

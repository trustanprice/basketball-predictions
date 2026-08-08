"""backend/live_client/endpoints/base.py

Base class for every endpoint in this package — one subclass per NBA.com data
source. Subclasses declare `expected_columns` and implement `_request()`;
`fetch()` handles caching and schema validation identically for all of them, so
an upstream field rename/removal raises loudly instead of silently producing a
dataframe with a missing/NaN column three layers downstream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..cache import DiskCache
from ..client import NBAStatsClient
from ..response import NBAResponse


class SchemaValidationError(RuntimeError):
    """Raised when an NBA.com response doesn't contain an endpoint's expected columns."""


class Endpoint(ABC):
    """One subclass per data source.

    Subclasses must set:
      - `expected_columns`: columns `fetch()` guarantees are present, or raises.
      - `self.params` (in `__init__`): the query params sent to NBA.com; also used
        as the cache key alongside the class name.
    And implement `_request()`, returning raw parsed JSON, and `_build_response()`
    if the endpoint isn't a standard stats.nba.com `resultSets` shape (live/
    endpoints override this — see endpoints/live/*.py).
    """

    expected_columns: tuple[str, ...] = ()
    result_set_name: str | None = None

    def __init__(self, client: NBAStatsClient | None = None, cache: DiskCache | None = None):
        self.client = client or NBAStatsClient()
        self.cache = cache if cache is not None else DiskCache()
        self.params: dict = {}

    @abstractmethod
    def _request(self) -> dict:
        """Make the HTTP call via self.client and return raw parsed JSON."""

    def _build_response(self, raw: dict) -> NBAResponse:
        """Default: a standard stats.nba.com resultSets response. Live endpoints
        (nested JSON, no resultSets) override this to build their own dataframe."""
        return NBAResponse(raw, result_set_name=self.result_set_name)

    def cache_key_params(self) -> dict:
        """Params used for the cache key. Defaults to the request params; override
        when a subclass encodes identifying info in the URL instead (e.g. a game ID
        embedded in a live/ endpoint's path rather than passed as a query param)."""
        return self.params

    def validate_schema(self, df: pd.DataFrame) -> None:
        missing = [c for c in self.expected_columns if c not in df.columns]
        if missing:
            raise SchemaValidationError(
                f"{type(self).__name__}: response is missing expected columns {missing} "
                f"— NBA.com may have changed this endpoint's schema. Got: {list(df.columns)}"
            )

    def fetch(self, force_refresh: bool = False) -> NBAResponse:
        """Fetch (cache-first unless force_refresh), wrap, and validate.

        Raises SchemaValidationError if the response doesn't match
        `expected_columns` — callers should let this propagate rather than catch
        it silently, per backend/AGENTS.md.
        """
        name = type(self).__name__
        key_params = self.cache_key_params()

        raw = self.cache.get(name, key_params, force_refresh=force_refresh)
        if raw is None:
            raw = self._request()
            self.cache.set(name, key_params, raw)

        response = self._build_response(raw)
        self.validate_schema(response.to_dataframe())
        return response

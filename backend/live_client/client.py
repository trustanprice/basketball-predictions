"""backend/live_client/client.py

The one requests.Session-holding client used by every endpoint in this package —
see backend/AGENTS.md's data-client conventions. No bare requests.get() calls
belong anywhere else under live_client/.

NBA.com's stats endpoints (stats.nba.com) and live endpoints (cdn.nba.com) are
different domains with different header requirements, so `get_json` takes a full
URL rather than assuming one base — endpoint classes each know which host they
need. This still keeps a single client class/Session, just not a single base_url.
"""

from __future__ import annotations

import time

import requests

STATS_BASE_URL = "https://stats.nba.com/stats"
LIVE_BASE_URL = "https://cdn.nba.com/static/json/liveData"

# stats.nba.com returns 403 for requests that don't look like a browser hitting
# nba.com — these headers are what's required to get a normal response, not a
# rate-limit bypass. cdn.nba.com (live/) endpoints are far less strict but a
# realistic User-Agent doesn't hurt.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}


class NBAClientError(RuntimeError):
    """Raised when a request fails after exhausting all retries."""


class NBAStatsClient:
    """Persistent-session HTTP client for NBA.com's stats and live JSON endpoints.

    Parameters
    ----------
    timeout : float
        Per-request timeout in seconds.
    max_retries : int
        Total attempts (including the first) before giving up on a request.
    backoff_seconds : float
        Base delay between retries; multiplied by the attempt number (linear
        backoff — this is a personal project hitting a public API, not a
        high-throughput client that needs exponential backoff/jitter).
    proxy : str | None
        Optional "http(s)://host:port" proxy applied to both schemes.
    extra_headers : dict | None
        Merged on top of DEFAULT_HEADERS for every request from this client.
    """

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        proxy: str | None = None,
        extra_headers: dict | None = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if extra_headers:
            self.session.headers.update(extra_headers)
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        """GET `url`, retrying transient failures, and return parsed JSON.

        Retries on network errors, non-2xx responses, and unparseable JSON bodies
        (NBA.com occasionally returns an HTML error page with a 200 status).
        Raises NBAClientError once `max_retries` is exhausted.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
        raise NBAClientError(f"GET {url} failed after {self.max_retries} attempts: {last_error}") from last_error

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "NBAStatsClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

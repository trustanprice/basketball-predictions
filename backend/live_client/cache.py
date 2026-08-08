"""backend/live_client/cache.py

Disk cache for raw NBA.com responses, keyed by endpoint name + sorted params.
Development convenience so repeated runs don't re-hit the network — not a
production data store (see backend/AGENTS.md: DB choice is a Phase 6 decision).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".cache"


class DiskCache:
    """JSON-on-disk cache. One file per (endpoint name, params) pair.

    Parameters
    ----------
    cache_dir : Path | str
        Where cached responses are written.
    ttl_seconds : float | None
        If set, cached entries older than this are treated as misses. `None`
        (default) means cached entries never expire on their own — use
        `force_refresh=True` on a fetch to bypass the cache explicitly instead.
    """

    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR, ttl_seconds: float | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _key_path(self, endpoint_name: str, params: dict) -> Path:
        normalized = json.dumps(params or {}, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{endpoint_name}:{normalized}".encode()).hexdigest()[:24]
        return self.cache_dir / f"{endpoint_name}__{digest}.json"

    def get(self, endpoint_name: str, params: dict, force_refresh: bool = False) -> dict | None:
        """Returns the cached raw response, or None on a miss / forced refresh."""
        if force_refresh:
            return None
        path = self._key_path(endpoint_name, params)
        if not path.exists():
            return None
        if self.ttl_seconds is not None and (time.time() - path.stat().st_mtime) > self.ttl_seconds:
            return None
        return json.loads(path.read_text())

    def set(self, endpoint_name: str, params: dict, raw: dict) -> None:
        self._key_path(endpoint_name, params).write_text(json.dumps(raw))

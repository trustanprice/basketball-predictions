"""Tests backend/api/main.py's background refresh check directly (not the
infinite sleep loop around it, which isn't practical or useful to unit test)."""

from unittest.mock import patch

import pytest

from backend.api import main as api_main


@pytest.mark.asyncio
async def test_refresh_if_stale_skips_when_fresh():
    with patch("backend.api.main.refresh_player_ratings.is_stale", return_value=False), \
         patch("backend.api.main.refresh_player_ratings.run_refresh") as mock_run:
        await api_main.refresh_if_stale()
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_if_stale_refreshes_when_stale():
    with patch("backend.api.main.refresh_player_ratings.is_stale", return_value=True), \
         patch("backend.api.main.refresh_player_ratings.run_refresh") as mock_run:
        await api_main.refresh_if_stale()
    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_if_stale_swallows_exceptions():
    """A failed NBA.com fetch (no network, rate-limited, down) must never crash
    the API or kill the background loop — this is the whole point of the
    try/except in refresh_if_stale()."""
    with patch("backend.api.main.refresh_player_ratings.is_stale", return_value=True), \
         patch("backend.api.main.refresh_player_ratings.run_refresh", side_effect=ConnectionError("no network")):
        await api_main.refresh_if_stale()  # must not raise

"""backend/api/main.py

FastAPI app wrapping backend.win_model and backend.ratings — see backend/AGENTS.md
for the full endpoint list and the player-ratings caching strategy.

Run locally:  uvicorn backend.api.main:app --reload --port 8000   (from repo root)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import coaching, players, win_model
from backend.ratings import refresh_player_ratings

logger = logging.getLogger("basketball_predictions.api")

# How often the background loop *checks* whether a refresh is due, and how old
# the cache is allowed to get before it's considered stale. Deliberately two
# separate knobs: checking hourly means a refresh fires promptly after either a
# cold start (Render's free tier sleeps the process after 15 min idle) or the
# 24h staleness boundary, without needing the process to have been continuously
# alive for exactly 24h — see backend/AGENTS.md's "Player ratings: refresh
# strategy" for why this replaced a separate host-level cron job.
REFRESH_CHECK_INTERVAL_SECONDS = int(os.environ.get("PLAYER_RATINGS_CHECK_INTERVAL_SECONDS", 60 * 60))
REFRESH_MAX_AGE_SECONDS = int(os.environ.get("PLAYER_RATINGS_MAX_AGE_SECONDS", refresh_player_ratings.DEFAULT_MAX_AGE_SECONDS))


async def refresh_if_stale() -> None:
    """One check-and-maybe-refresh attempt. Never raises: a failed NBA.com fetch
    (down, rate-limited, no network) must not crash the API or the background
    loop — the existing (stale) cache just keeps being served, and the next
    scheduled check retries. run_refresh() itself is synchronous/blocking
    (requests, not httpx), so it's offloaded to a thread to avoid stalling the
    event loop that's also serving requests.
    """
    try:
        if refresh_player_ratings.is_stale(REFRESH_MAX_AGE_SECONDS):
            await asyncio.to_thread(refresh_player_ratings.run_refresh)
            logger.info("player power rankings refreshed")
    except Exception:
        logger.exception("player power rankings refresh attempt failed; serving existing cache")


async def _refresh_loop() -> None:
    while True:
        await refresh_if_stale()
        await asyncio.sleep(REFRESH_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_refresh_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Basketball Predictions API",
    description="Win predictions, player power rankings, and coaching evaluation — read-only, JSON.",
    version="1.0.0",
    lifespan=lifespan,
)

# The Next.js frontend (local dev + Vercel deploy) is the only intended caller.
# ALLOWED_ORIGINS is a comma-separated env var so the Vercel URL doesn't need to
# be hardcoded here; defaults cover local Next.js dev.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(win_model.router)
app.include_router(players.router)
app.include_router(coaching.router)


@app.get("/health")
def health():
    """Liveness check for the hosting platform — deliberately does not touch
    any data file, so it stays fast/reliable even if a results file is missing."""
    return {"status": "ok"}

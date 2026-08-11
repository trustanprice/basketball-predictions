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
from backend.ratings import refresh_player_projections, refresh_player_ratings, refresh_team_style

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

# team_style and player_projections were built with the exact same is_stale()/
# run_refresh() interface as refresh_player_ratings specifically so they could
# share this one loop — they were never actually wired in until now, which is
# why "no team-style data available" / "projected leaders" never resolved on
# their own no matter how long the service ran: nothing was ever calling them.
# Reusing the same check interval/max-age knobs rather than adding six new env
# vars for what's the same tradeoff three times over.


async def refresh_if_stale() -> None:
    """One check-and-maybe-refresh attempt per data source. Never raises: a
    failed NBA.com fetch (down, rate-limited, no network) must not crash the
    API or the background loop — the existing (stale) cache just keeps being
    served, and the next scheduled check retries. Each source is caught
    independently so one failing (e.g. team_style) never blocks the others
    from refreshing. run_refresh() is synchronous/blocking (requests, not
    httpx), so each is offloaded to a thread to avoid stalling the event loop
    that's also serving requests.
    """
    try:
        if refresh_player_ratings.is_stale(REFRESH_MAX_AGE_SECONDS):
            await asyncio.to_thread(refresh_player_ratings.run_refresh)
            logger.info("player power rankings refreshed")
    except Exception:
        logger.exception("player power rankings refresh attempt failed; serving existing cache")

    try:
        if refresh_team_style.is_stale(REFRESH_MAX_AGE_SECONDS):
            await asyncio.to_thread(refresh_team_style.run_refresh)
            logger.info("team style refreshed")
    except Exception:
        logger.exception("team style refresh attempt failed; serving existing cache")

    try:
        if refresh_player_projections.is_stale(REFRESH_MAX_AGE_SECONDS):
            await asyncio.to_thread(refresh_player_projections.run_refresh)
            logger.info("player projections refreshed")
    except Exception:
        logger.exception("player projections refresh attempt failed; serving existing cache")


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

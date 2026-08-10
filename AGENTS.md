# Basketball-Predictions

NBA analytics project: a team win-total prediction model (backtested 2016–2025) plus new
live-data-driven player power rankings and coaching evaluation, moving off a static Streamlit
app onto a Next.js frontend backed by a real API.

## Module split

- **Win model** (`backend/win_model/`) — predicts team win totals per season from historical
  team/payroll/draft/coach/player data. Walk-forward validated (never random CV — this is a
  time-dependent process). Backtest data lives in `data/`.
- **Live ratings** (`backend/live_client/` + `backend/ratings/`) — a data client for NBA.com
  stats/live endpoints, and a separate computation module that turns those dataframes into
  Player Power Rankings (offense/defense). Fully explainable: formula, raw inputs, z-scores,
  and weights must be reproducible by hand for every number shown in the UI. No black-box ML
  here — see `backend/AGENTS.md`.
- **Coaching evaluation** (`backend/ratings/coaching_eval.py`) — actual coach win% vs.
  roster-talent-implied win%, using the win model's talent features and/or the player ratings
  above as the expectation baseline. Same transparency requirement as live ratings.

## Where data lives

- `data/raw/` and `data/processed/` — static, historical (2016–2025), scraped once. This is
  the only source for payroll/draft/coach history and the backtest set for the win model.
  **Never overwritten by the live client.** See `data/AGENTS.md`.
- Live/current-season data is fetched on demand (dev) or on a schedule (prod) by
  `backend/live_client/`, cached to disk during development — see `backend/AGENTS.md`.
- Static reference lookups (player/team ID↔name) live separately in
  `backend/live_client/lookups/` — those are client dependencies, not historical backtest
  data. Don't confuse them with `data/`: both are "static, not live-fetched," but they serve
  different purposes and neither should be merged into the other.

## Running locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ..
streamlit run app.py          # existing win-model app (transitional — Phase 6 replaces this)
```

API (from repo root, separate terminal): `uvicorn backend.api.main:app --reload --port 8000` —
serves win-model predictions, player power rankings, and coaching evaluation as JSON. See
`backend/AGENTS.md` for the endpoint list and the player-ratings refresh strategy.

Frontend (separate terminal): `cd frontend && npm install && npm run dev` — see `frontend/AGENTS.md`
for env setup (needs `API_BASE_URL` pointed at the API above).

## Subdirectory docs

- [`backend/AGENTS.md`](backend/AGENTS.md) — data-client conventions, ratings computation,
  testing.
- [`frontend/AGENTS.md`](frontend/AGENTS.md) — Next.js conventions, API usage, Vercel notes.
- [`data/AGENTS.md`](data/AGENTS.md) — static vs. live data boundary.

## Gotchas

- `app.py` and the root `requirements.txt` stay at repo root on purpose — Streamlit Cloud's
  deployment config points here. Root `requirements.txt` is just `-r backend/requirements.txt`.
- Historical data in `data/` is frozen and manually curated in places (payroll, draft, coach
  tenure) — there is no live-fetch replacement for pre-current-season data.
- The win model and the live ratings engine are architecturally separate (different validation
  needs, different data freshness) and are served by one FastAPI app in `backend/api/` — that
  app calls into both and reshapes their output as JSON, it does not merge their internals.
- The API never calls `live_client` directly on a request — player ratings are refreshed by an
  in-process background loop and served from a local file. See `backend/AGENTS.md`'s "Player
  ratings: refresh strategy" before changing anything about how that data gets to the API.

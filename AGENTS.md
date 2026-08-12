# Basketball-Predictions

NBA analytics project: a walk-forward-validated win-total prediction model, a live player
power-rankings engine, and a coaching evaluation model, served by a FastAPI backend and a
Next.js frontend — both built and deployed (Vercel + Render), not a work-in-progress plan
anymore. The original Streamlit app (`app.py`, root `requirements.txt`) still exists,
transitional, kept alive for its own Streamlit Cloud deployment.

## Module split

- **Win model** (`backend/win_model/`) — predicts team win totals per season. Walk-forward
  validated (never random CV — this is a time-dependent process), GBM benchmarked against KNN
  honestly, predictions calibrated to match real historical win-total spread and the exact
  1,230-game league total. The forecast row's roster-talent features come from a real,
  currently-running roster-projection pipeline (see `backend/AGENTS.md`) — not a stale
  same-roster carry-forward. Backtest data lives in `data/`.
  **`data/raw/master-stats/master_df.csv` must stay current to one season behind the calendar,
  or the "forecast" silently predicts an already-completed season instead of a real future one.**
  This actually happened: the dataset sat one season stale (its newest row was the real 2024-25
  season) for the entire early part of this project, so what the app called a "2026-27 forecast"
  was really a stale re-guess at the *already-played* 2025-26 season, built from a season-old
  input. Caught by comparing a live NBA.com standings pull against the training data directly.
  Fixed by adding the real, completed season as a new row (team stats, records, draft, coach —
  all pulled live and verified against real results) — this is a recurring maintenance task, not
  a one-time fix: **every season that finishes, this dataset needs the real result added**, or
  the same staleness silently recurs. There's no automated job for this yet — check `master_df`'s
  newest `Season` against the real calendar before trusting a forecast looks "off."
- **Live ratings** (`backend/live_client/` + `backend/ratings/`) — a data client for NBA.com
  (built on `nba_api`, with its own retry/cache/schema-validation layer nba_api itself doesn't
  have), and a computation module producing Player Power Rankings (offense/defense) and
  preseason projected leaders. Fully explainable: formula, raw inputs, z-scores, and weights
  must be reproducible by hand for every number shown in the UI. No black-box ML here — see
  `backend/AGENTS.md`.
- **Coaching evaluation** (`backend/ratings/coaching_eval.py` + `team_style.py`) — actual coach
  win% vs. roster-talent-implied win%, plus a team-style fingerprint (pace, shot profile, shot
  heatmaps) shown as descriptive context, explicitly never framed as causal. Same transparency
  requirement as live ratings.

## Deployment

- **Frontend**: Next.js on Vercel, root directory `frontend/` (monorepo — Vercel needs this set
  explicitly). Env var `API_BASE_URL` points at the Render backend.
- **Backend**: FastAPI on Render (`render.yaml` Blueprint at repo root), free tier. `ALLOWED_ORIGINS`
  env var must include the Vercel production domain for CORS.
- **Both auto-deploy from `main`** on push — see `backend/AGENTS.md`'s hosting section and the
  gotcha below about what that means for anything that touches live data.

## Where data lives

- `data/raw/` and `data/processed/` — static, historical, scraped once. The only source for
  payroll/draft/coach history and the backtest set for the win model. **Never overwritten by
  the live client.** See `data/AGENTS.md`, including the `master_df.csv` gotcha — it must be
  committed (backend reads it directly at request time for coaching endpoints), and it was
  missed once before, causing a real production outage.
- **`backend/outputs/*.json`** — live/current-season data (player rankings, team style, player
  projections). These are **committed**, not gitignored, despite being generated output — this
  is the single most important operational fact in this repo right now, see the Gotchas section
  below before touching anything related to live data freshness.
- Static reference lookups (player/team ID↔name) live in `backend/live_client/lookups/` —
  client dependencies, not historical backtest data. Don't confuse them with `data/`.

## Running locally

```bash
cd backend
python -m venv venv && source venv/bin/activate   # or: source venv/bin/activate if it exists
pip install -r requirements.txt
cd ..
uvicorn backend.api.main:app --reload --port 8000   # from repo root, separate terminal
```

Frontend (separate terminal): `cd frontend && npm install && npm run dev` — see
`frontend/AGENTS.md` for env setup (`API_BASE_URL` pointed at the API above).

Transitional Streamlit app: `streamlit run app.py` from repo root (uses the same
`backend/win_model` code, reads the same committed `data/raw/master-stats/` files).

## Subdirectory docs

- [`backend/AGENTS.md`](backend/AGENTS.md) — data-client conventions, ratings computation,
  the live-data refresh strategy (read this before touching anything related to NBA.com
  connectivity), testing.
- [`frontend/AGENTS.md`](frontend/AGENTS.md) — Next.js conventions, API usage, Vercel notes.
- [`data/AGENTS.md`](data/AGENTS.md) — static vs. live data boundary, the `master_df.csv`
  gotcha.

## Gotchas

- **NBA.com is not reachable from Render** — confirmed with real evidence (not assumed) across
  two different regions, both hard-timing-out identically. This is not fixed at the
  infrastructure level and may never need to be: the actual production strategy is running the
  refresh scripts locally (where the same client works fine, verified repeatedly) and committing
  the output — see `backend/AGENTS.md`'s refresh-strategy section for the full story, including
  two real bugs (a wiring gap, a per-player crash) found and fixed along the way. **If live data
  looks stale in production, the fix is usually "someone needs to re-run the refresh scripts
  locally and commit," not a code change.**
- **`backend/outputs/*.json` files being committed is a deliberate, load-bearing choice**, not
  an oversight — don't gitignore them "for cleanliness" without reading why they're there.
- `app.py` and the root `requirements.txt` stay at repo root on purpose — Streamlit Cloud's
  deployment config points here. Root `requirements.txt` is just `-r backend/requirements.txt`.
- Historical data in `data/` is frozen and manually curated in places (payroll, draft, coach
  tenure) — there is no live-fetch replacement for pre-current-season data, and `nba_api` has no
  payroll endpoint at all (current-season payroll is always last-known, labeled as such).
- The win model and the live ratings engine are architecturally separate (different validation
  needs, different data freshness) and are served by one FastAPI app in `backend/api/` — that
  app calls into both and reshapes their output as JSON, it does not merge their internals.
- Branching: page-scoped feature branches (`feature/win-predictions`,
  `feature/player-power-rankings`, `feature/coaching-evaluation`) plus git worktrees for
  running multiple builder sessions in parallel without one session's `git checkout` yanking
  files out from under another — see recent git history/reflog if picking this convention back
  up. `main` is always what's deployed; never commit directly to it without verifying tests +
  build first.

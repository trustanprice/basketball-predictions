# backend/

All Python for this project: the win-total model, the NBA.com live data client, the ratings
engine, and (eventually) the API the frontend calls. See root `AGENTS.md` for the module split.

## Layout

```
backend/
├── win_model/       # team win-total prediction (Phase 1)
├── live_client/      # NBA.com data client (Phase 2)
├── ratings/           # player ratings + coaching eval, consumes live_client output (Phase 3-4)
├── api/                # FastAPI app serving win_model + ratings results as JSON (Phase 5)
├── notebooks/          # exploratory work; production logic belongs in the packages above, not here
├── tests/              # pytest, mirrors package layout (tests/win_model/, tests/live_client/, ...)
├── outputs/             # gitignored model artifacts/figures + the player-rankings cache (see below)
└── requirements.txt
```

## Imports

`backend/` and `backend/win_model/` are explicit packages (`__init__.py`, not implicit
namespace packages) — this keeps imports unambiguous as more subpackages get added.

- From repo root (`app.py`, and later `backend/api/`): `from backend.win_model.data_loader import ...`
- From inside `backend/notebooks/`: notebooks run with cwd = their own directory, and each
  does `sys.path.append(os.path.abspath(".."))` to put `backend/` on the path, so imports
  there are `from win_model.data_loader import ...` (no `backend.` prefix). Don't "fix" this
  to match the root-style import — it's correct for where the notebook's sys.path points.
- Because a package under `backend/` gets imported under both roots above (`backend.win_model`
  from repo root, plain `win_model` from notebooks), cross-module imports **inside** a package
  must be relative (`from .utils import ...`), never absolute (`from backend.win_model.utils
  import ...`). An absolute internal import only resolves under one of the two roots and breaks
  the other silently at import time.
- `backend/api/` and `backend/ratings/refresh_player_ratings.py` are **repo-root-context only**
  — like `app.py`, they're never imported from notebooks, only run via `uvicorn
  backend.api.main:app` / `python -m backend.ratings.refresh_player_ratings` from the repo root.
  They use absolute `backend.X` imports to reach sibling top-level packages (e.g.
  `refresh_player_ratings.py` importing `backend.live_client`) — there's no relative-import path
  between sibling packages under the notebook-style root (`ratings` has no parent package in
  that scheme), so absolute is the only option that works there. Same-package siblings inside
  these files (e.g. `refresh_player_ratings.py` importing its own `player_power_rankings.py`)
  still use relative imports, matching the rest of the codebase. `backend/tests/conftest.py` adds
  *both* `backend/` and the repo root to `sys.path` so tests can exercise either import style.

## Data client conventions (`live_client/`)

Modeled loosely on `nba_api`'s patterns (not its code). When adding a new data source, all four
layers are required — don't shortcut with a bare `requests.get()` anywhere outside `client.py`:

1. **`client.py`** — the one `requests.Session`-holding client class. Headers, timeout, retry,
   and error handling live here, once.
2. **`response.py`** — every endpoint's raw JSON gets wrapped before it leaves the client layer.
   `to_dict()` / `to_json()` / `to_dataframe()`. Nothing downstream touches raw parsed JSON.
3. **`endpoints/`** — one class per data source, with typed constructor args, a documented
   expected schema, and `fetch()`. Validate the schema at parse time — an upstream field
   rename should raise loudly, not silently produce a dataframe with a NaN column.
   `endpoints/stats/` = historical/season data (season totals, career stats, shot charts,
   advanced metrics, box scores). `endpoints/live/` = in-game feeds (scoreboard, live box
   score). Keep these separate — different freshness guarantees, different schemas, don't
   let a "generic" endpoint class quietly serve both.
4. **`cache.py`** — disk cache keyed by endpoint name + sorted params, used during
   development. Every fetch path needs an easy force-refresh flag; don't build a fetcher that
   can only ever read cache or only ever hit the network.

Static player/team ID↔name lookups live in `live_client/lookups/`, not fetched live. See root
`AGENTS.md` for how this differs from `data/`.

Storage for cached/computed output beyond local disk (Postgres vs. DuckDB) is an open decision,
deferred to Phase 6 when backend hosting is chosen. Don't wire a specific database into
`live_client/` or `ratings/` before then — keep them writing plain dataframes/disk cache so the
storage layer can be swapped in underneath without touching fetch or computation logic.

## Ratings/computation conventions (`ratings/`)

This module is a consumer of `live_client/`, not part of it — it never makes HTTP calls.

- **Transparency is the hard requirement, not a nice-to-have.** Every number `ratings/`
  produces (player power ranking, coaching wins-above-expectation) must be traceable back to:
  the exact formula, the player/coach's raw inputs, their z-scores, and the weights used. If a
  change can't be explained in those four terms by hand, it doesn't belong in `ratings/` yet —
  save it for a future regression-based model, which is explicitly out of scope until the
  transparent version is validated.
- Shared z-score/weighting utilities go in `core.py` so `player_power_rankings.py` and
  `coaching_eval.py` don't duplicate the "explain this number" scaffolding.
- `coaching_eval.py` lives here (not a separate top-level package) because it's tightly
  coupled to `core.py`'s engine and reuses `win_model`'s talent features — it isn't
  architecturally separate the way `win_model` and `live_client` are.

## API (`api/`)

FastAPI app wrapping `win_model` and `ratings` as JSON — it must not duplicate their logic,
only call into them and reshape output (`backend/api/dependencies.py` is where that
reshaping lives; routers stay thin). Run locally with `uvicorn backend.api.main:app --reload`
from the repo root. Endpoints:

- `GET /api/win-model/predictions` — all teams, latest season, no methodology (kept light for
  a 30-row list).
- `GET /api/win-model/predictions/{team}` — one team + the full methodology inline (validation
  method, model comparison, feature importances) — self-contained, no second call needed.
- `GET /api/win-model/methodology` — the methodology on its own.
- `GET /api/players/power-rankings` — top-5 offense/defense, each with a full `RatingBreakdown`
  (raw value, z-score, weight, contribution per component). See refresh strategy below —
  503s with an explanatory message if the cache has never been populated.
- `GET /api/coaches/wins-above-expectation` (optional `season`/`team` query filters) and
  `GET /api/coaches/career-summary`.

All routers read their data via FastAPI `Depends()` (see `dependencies.py`) rather than calling
loaders directly in the route body — this is what makes `backend/tests/api/` able to swap in
synthetic fixtures via `app.dependency_overrides` instead of touching real files/network.

### Player ratings: refresh strategy

`ratings.player_power_rankings` depends on `live_client`, and `live_client` must **not** be hit
live on every API request — NBA.com rate limits and request latency make that wrong for a
request-serving API (a slow or rate-limited upstream call would directly become a slow or
failing API response). Measured this directly in dev: a fully-unreachable NBA.com doesn't fail
fast, it hangs to the 15s read-timeout **per attempt**, ×3 retries ×2 endpoints — up to ~96s for
one failed refresh. That number is exactly why this can never happen inside a request.

Chose **scheduled refresh to a local store** over a plain TTL cache — implemented as an
**in-process background loop inside the API's own web service**, not a separate host-level cron
job. That's a deliberate choice, not the default: a separate cron *service* (Render's native Cron
Jobs, Railway's scheduled runs, etc.) doesn't share a filesystem with the web service on any of
these hosts' standard tiers, so a cron job writing `player_power_rankings.json` would write it
somewhere the API can never read it back from. Running the refresh in the same process/container
as the request handling sidesteps that entirely.

- `backend/ratings/refresh_player_ratings.py` — standalone, independently runnable (same shape
  as `win_model/train.py`): fetches the current season from `live_client`, computes the
  rankings, and writes `backend/outputs/player_power_rankings.json` (gitignored — a build
  artifact, not source, unlike `win_model`'s `test_results.csv`/`model_metadata.json`, which are
  committed because Streamlit Cloud has no separate build step; the API's host does). Also
  exposes `is_stale(max_age_seconds)`, so a caller can check before fetching instead of always
  fetching unconditionally.
- `backend/api/main.py` runs a background `asyncio` loop (started in the FastAPI `lifespan`)
  that checks `is_stale()` roughly hourly and calls `run_refresh()` when due (default staleness
  bound: 24h — "who's playing well this season" doesn't change hour to hour). The actual
  network call is offloaded via `asyncio.to_thread` so a slow/hanging fetch (see the ~96s
  number above) never blocks request handling — verified directly: `/health` kept responding in
  ~12ms while a refresh attempt was stuck retrying in the background.
- Failures are caught and logged, never raised — a down/rate-limited NBA.com must not crash the
  API or kill the loop; the existing (stale) cache keeps being served and the next hourly check
  retries.
- Checking hourly rather than sleeping for a fixed 24h also makes this self-healing across
  process restarts: if the host's free tier sleeps the process on idle (Render's does, after
  15 min), the loop's first check on the next cold start re-evaluates staleness immediately —
  frequent restarts with a still-fresh cache are cheap no-ops, and a genuinely stale cache gets
  refreshed promptly regardless of exactly when the process happened to be alive.
- The API's `/api/players/power-rankings` route **only ever reads the file** the loop wrote —
  never calls `live_client` itself. If it doesn't exist yet (fresh deploy, first refresh still
  in flight or failed), the endpoint 503s with an explanatory message rather than blocking.
- **Tradeoff, stated plainly**: rankings can be up to ~1 day + up to 1 check-interval stale.
  If that bound ever needs to tighten, lower `PLAYER_RATINGS_MAX_AGE_SECONDS`/
  `PLAYER_RATINGS_CHECK_INTERVAL_SECONDS` (both env-configurable); don't reach for a
  live-fetch-per-request instead without re-reading the ~96s number above.
- `win_model` and `coaching_eval` don't need any of this — both are cheap, pure computation over
  static/already-written data (a small file read, and a ~300-row in-memory computation
  respectively), so the API reads/computes them straight, per-request (coaching results are
  `functools.lru_cache`d in-process purely to avoid re-parsing `master_df.csv` on every call,
  not because the computation is slow).

### Hosting

**Render**, free web-service tier. Rationale: the refresh strategy above no longer needs
host-level cron support (that was the original plan, dropped for the filesystem-isolation reason
explained above), which was the main axis that would've favored a different host — so the
deciding factors become cost and deploy simplicity, where Render's free tier and single-file
`render.yaml` Blueprint (declares the web service, build/start commands, and health check path
all in one committed file) are the simplest path for a personal project. The known tradeoff:
free-tier services sleep after 15 min idle and cold-start (~30-50s) on the next request — the
refresh loop's hourly-recheck design (above) specifically absorbs that without going stale in an
unbounded way, so it's an acceptable tradeoff rather than a blocker. Config: `render.yaml` at the
repo root (`rootDir` deliberately *not* set — commands stay repo-root-relative to match the
import convention above, e.g. `uvicorn backend.api.main:app`, not `uvicorn api.main:app`).

## win_model conventions

- Validation is walk-forward only: train on seasons ≤ N, evaluate on season N+1, roll forward.
  Random-fold `cv=` on team-season rows leaks future seasons into training — do not reintroduce
  it.
- Point predictions ship with a prediction interval, not just a single number.
- Every prediction surfaced in the app needs a "how this was calculated" explanation — same
  transparency spirit as `ratings/`, even though this module is allowed to use real ML
  (ElasticNet / gradient-boosted regressor) rather than a hand-reproducible formula.

## Testing

`pytest` from `backend/`. `ratings/` is the highest-value thing to test — unit tests against
known inputs (a synthetic player line with a hand-computed z-score/weight) are what catch a
silently-wrong formula. `live_client/endpoints/` schema validation is the second priority —
test that a malformed/renamed-field response raises instead of parsing quietly.

`tests/api/` uses FastAPI's `TestClient` with `app.dependency_overrides` (see
`tests/api/conftest.py`) — routers take their data via `Depends()` specifically so tests can
swap in synthetic fixtures instead of touching real files or the network. `tests/api/test_dependencies.py`
is the exception: it calls the dependency functions directly against this repo's real committed
data (`test_results.csv`, `model_metadata.json`, `master_df.csv`) as a genuine integration
check, not mocks — the one dependency that can't be exercised for real here is player power
rankings, since its source file only ever comes from a live NBA.com fetch and this dev
environment has no network access.

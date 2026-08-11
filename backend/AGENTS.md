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
- A **dual-context file that needs a sibling top-level package** (not just its own package's
  siblings) is the one case neither rule above covers cleanly: relative dots (`..ratings.X`)
  only resolve from the repo-root context; plain top-level (`ratings.X`) only resolves from the
  notebook-style context (or tests, via `conftest.py`'s sys.path). `win_model/train.py` importing
  `ratings.player_development` (for the roster-projection wiring) is the first place this came
  up — resolved with a try/relative-except/plain-fallback:
  ```python
  try:
      from ..ratings.player_development import team_talent_composite
  except ImportError:
      from ratings.player_development import team_talent_composite
  ```
  Reach for this only when a dual-context file genuinely needs a sibling package; same-package
  imports still just use relative dots.

## Data client conventions (`live_client/`)

`endpoints/stats/*.py` build their requests via the `nba_api` package (a real dependency, not
just a pattern reference — added after confirming two things by reading its source: it makes
exactly one request attempt with no retry, and it does zero schema validation), rather than
hand-rolled URLs/params. What stays ours on top of it:

1. **`client.py`** — the one `requests.Session`-holding client class, PLUS `get_via_nba_api()`:
   a retry/backoff wrapper around an already-built (`get_request=False`) nba_api endpoint
   instance — this is the retry nba_api itself doesn't have. `DEFAULT_HEADERS` is a **verified**
   working header set for stats.nba.com (confirmed live, not guessed — a request with a
   plausible-but-incomplete header set gets a 200 that just hangs to the read timeout; the
   missing pieces were `Sec-Ch-Ua*`, `Sec-Fetch-Dest`, `Accept-Encoding`, `Pragma`,
   `Cache-Control` — this is also nba_api's own default header set, so `endpoints/stats/*.py`
   mostly don't even need to pass headers explicitly). `endpoints/live/` (cdn.nba.com) still
   calls `get_json()` directly — out of scope for the nba_api migration, and cdn.nba.com's 403
   here is a CDN-level block unrelated to headers, not something either client fixes.
2. **`response.py`** — every endpoint's raw JSON/dataframe gets wrapped before it leaves the
   client layer. `to_dict()` / `to_json()` / `to_dataframe()`. Nothing downstream touches raw
   parsed JSON — nba_api hands back whatever columns come back with no check at all.
3. **`endpoints/`** — one class per data source, with typed constructor args, a documented
   expected schema, and `fetch()`. Validate the schema at parse time — an upstream field
   rename (or a wrong assumption about the schema in the first place — see `TM_TOV_PCT` below)
   should raise loudly, not silently produce a dataframe with a NaN column.
   `endpoints/stats/` = historical/season data (season totals, career stats, shot charts,
   advanced metrics, box scores). `endpoints/live/` = in-game feeds (scoreboard, live box
   score). Keep these separate — different freshness guarantees, different schemas, don't
   let a "generic" endpoint class quietly serve both.
   - `boxscore.py`/`play_by_play.py` use nba_api's V3 endpoints (`BoxScoreTraditionalV3`,
     `PlayByPlayV3`), not V2 — nba_api's own source flags V2 as deprecated and no longer
     returning data as of the 2025-26 season. V3's response is nested JSON (camelCase, a
     `statistics` sub-object per player), not the classic `resultSets`/`rowSet` table, so
     these two override `_build_response()` to use nba_api's own dataframe flattening
     (`endpoint.player_stats.get_data_frame()` / `.play_by_play.get_data_frame()`) instead of
     `response.py`'s generic parser — same pattern `endpoints/live/*.py` already used.
   - `PlayerAdvancedStats`'s real turnover-rate column is `TM_TOV_PCT`, not `TOV_PCT` — an
     assumption that was simply wrong from the start (not an upstream rename), caught by the
     real-network integration test below, not by schema validation (which only catches a
     column going missing, not a column that was never right to begin with).
4. **`cache.py`** — disk cache keyed by endpoint name + sorted params, used during
   development. Every fetch path needs an easy force-refresh flag; don't build a fetcher that
   can only ever read cache or only ever hit the network. Default TTL is `None` (never expires
   on its own) — an endpoint whose data actually changes over time (see `TeamRoster` below)
   overrides this per-instance rather than changing the shared default.
5. **Request pacing matters, separately from per-request retry.** `client.py`'s retry/backoff is
   about one request's transient failure; it does nothing for sustained request *volume* against
   a rate limit. Confirmed directly while building the roster-projection pipeline (below): firing
   ~60 `PlayerCareerStats` calls back-to-back with no delay between them started producing read
   timeouts partway through, and retrying each one individually didn't help — the fix was pacing
   the *loop*, not the client (see `REQUEST_PACING_SECONDS` in `refresh_roster_projection.py`).
   Any new script that fires more than a handful of requests in a loop needs an explicit
   inter-request delay; don't assume `client.py`'s retry alone is enough at that volume.

Static player/team ID↔name lookups live in `live_client/lookups/`, sourced from
`nba_api.stats.static` (`teams.get_teams()` / `players.get_players()` — bundled with the
package, no network call, confirmed 30 teams / 5,103 players), not hand-maintained CSVs. Note
`players.get_players()` has no `team_id` — a player's team is a roster/season fact, not a
static one; that's the separate not-yet-built roster/schedule unit of work, not this lookup.
See root `AGENTS.md` for how `lookups/` differs from `data/`.

**Testing**: `tests/live_client/test_endpoints.py` mocks `client.get_via_nba_api`/`get_json`
directly (schema-validation-on-malformed-response tests — cheap, deterministic, no network).
`tests/live_client/test_integration_real_network.py` is different on purpose: no mocks, actually
hits stats.nba.com, skips cleanly (doesn't fail the suite) if unreachable. Both matter — mocked
tests catch a response *shape* regression; the real-network test is what actually caught
`TM_TOV_PCT`, which no amount of mock-based testing could have, since the mock's payload was
built from the same wrong assumption as the code. Re-run the real one after touching any
`endpoints/stats/*.py` file, don't trust mocked-only green.

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
- `player_development.py` follows the same rule as `coaching_eval.py`: it never calls
  `live_client` itself (`refresh_roster_projection.py` does the fetching and hands it
  dataframes) and never imports `win_model` — see "Roster projection" below for how the two
  actually connect, which is the reverse direction (`win_model` reads `ratings`' output, not
  the other way around).

### Roster projection: empirical aging curve + team-talent projection

Real current rosters, projected one season forward via an empirical (not fitted-ML) aging curve,
feeding `win_model`'s **forecast row only** — historical (already-completed) seasons are
untouched. Same transparency bar as the rest of `ratings/`: the curve is "age-X players
historically see a median Y% change in scoring rate the next season," reproducible by grouping
real player-seasons and taking a median — not a trained model.

- **`live_client/endpoints/stats/team_roster.py`** (`TeamRoster`, via nba_api's
  `CommonTeamRoster`) is the one endpoint in this project with a **short cache TTL** (6h)
  instead of the default never-expires — a roster moves through trades/signings/waivers all
  offseason, unlike a completed season's box score, which never changes once written.
- **`ratings/player_development.py`** — pure computation, no network:
  - `build_aging_curve(career_histories)`: pools every player-season-to-season transition across
    the input careers, computes % change in PTS-per-36, bins by the age at the *start* of the
    transition, takes the median. Drops a transition if either season has fewer than
    `MIN_GP_FOR_CURVE` (10) games played (a 2-game stretch at an extreme rate is noise, not
    signal), and drops an entire age bin if it has fewer than `MIN_OBSERVATIONS_PER_AGE_BIN` (5)
    real transitions (an untrustworthy median is worse than no adjustment).
  - `project_player_next_season(career_df, aging_curve)`: applies that curve to one player's real
    most recent season. Players with ≤2 total recorded seasons ("0-1 prior seasons") get **no
    adjustment** — their actual most-recent-season stats are carried forward unadjusted and the
    result is flagged (`development_adjustment_applied=False`) — this project doesn't fabricate a
    trend it has no real personal history to support. Same for a player landing on an age with no
    curve data. Minutes-per-game are carried forward unchanged (projecting playing time is a
    separate problem this curve doesn't attempt); only the per-36 scoring rate gets adjusted.
  - `project_team_talent_features(projected_players)`: aggregates to the exact same
    `avg_age`/`avg_pts_top10`/`avg_production_score` shape `win_model/data_loader.py`'s
    `calculate_player_features()` produces from historical data — so these values are drop-in
    replacements for `win_model`'s existing feature columns, not a new/different feature.
  - `team_talent_composite(team_features)`: the explainable, hand-reproducible "how this team's
    projected talent compares league-wide" summary — reuses `coaching_eval.compute_team_season_talent`
    and its `TALENT_COMPONENTS` directly rather than a second parallel composite system. This is a
    **methodology-panel transparency artifact only** — it is *not* what `win_model` reads (that's
    the raw recomputed feature columns above, the same columns the model was already trained on).
- **`ratings/refresh_roster_projection.py`** — the fetch/orchestration script, same shape as
  `refresh_player_ratings.py`: fetches every team's real roster + every roster player's career
  history (one `PlayerCareerStats` call each, reused for both "most recent season" and the pooled
  aging-curve sample — "reachable history" means *current NBA players*, not an exhaustive fetch of
  league history, which would be substantial extra load for marginal curve accuracy), builds the
  curve, projects, aggregates, and writes `backend/outputs/roster_projection.json` (gitignored).
  `win_model/train.py` only ever reads this file — same refresh/consumer split as player ratings,
  same reason (this fetch is 400-500 real HTTP calls; it can never happen inside a request or
  inside `win_model`'s own training run). Run manually:
  `python -m backend.ratings.refresh_roster_projection`.
- **Payroll is deliberately untouched by any of this.** nba_api has no payroll endpoint, and a
  team's actual payroll changes with every offseason transaction — there's no live source to
  project it from. `win_model/train.py` keeps using `master_df`'s last-known payroll value for
  the forecast row (exactly as before) and labels it explicitly stale in both
  `FEATURE_NOTES["Payroll"]` and `metadata.roster_projection` — same honesty standard as the SOS
  null-for-forecast-season caveat.

### Projected player leaders (Players page, preseason)

A second, independent use of the aging-curve idea above, for the players page's "Projected
Offense/Defense" tabs — reuses `player_power_rankings.py`'s exact composite (not a second
ranking system), fed *projected* stats instead of actual ones.

- **Archetype-segmented, not one universal curve.** `player_development.py`'s
  `classify_archetype()` buckets a player-season into `Rim-Reliant` / `Perimeter` / `Balanced`
  from real shot-location data (rim-attempt rate, 3PA rate — simple, statable thresholds, not a
  clustering model). `build_archetype_curves()`/`project_player_multistat()` compute the same
  median-%-change-by-age-bin curve as `build_aging_curve()` above, just segmented by
  `(archetype, age)` and applied to every stat `OFFENSE_COMPONENTS`/`DEFENSE_COMPONENTS` actually
  need (`TS_PCT`, `USG_PCT`, `AST_PCT`, `TM_TOV_PCT`, `STL_BLK_PER36`, `DREB_PCT`, `DEF_RATING`,
  plus `PTS`) — not just scoring. A thin `(archetype, age)` cell (fewer than
  `MIN_OBSERVATIONS_PER_ARCHETYPE_AGE_BIN` real transitions) falls back to the pooled
  all-archetype curve for that age and says so in `development_notes`, same "don't fabricate a
  trend you don't have data for" principle as the win-model roster projection. These functions
  are additive, not a change to `build_aging_curve()`/`project_player_next_season()` — those stay
  exactly as win_model's roster-projection pipeline depends on them.
- **`ratings/refresh_player_projections.py`** — fetches real current rosters (`TeamRoster`) plus
  a `N_HISTORICAL_SEASONS`-season league-wide panel (`PlayerSeasonTotals` + `PlayerAdvancedStats`
  + the new `PlayerShotLocations`, three calls *per season*, not per player — a deliberately
  different, cheaper shape than `refresh_roster_projection.py`'s per-player `PlayerCareerStats`
  calls, chosen specifically to avoid the real rate-limiting that approach already hit once at
  volume), projects every current-roster player, reshapes the projected numbers into the exact
  input shape `build_player_table()` expects, and runs the *unmodified*
  `top_offensive_players`/`top_defensive_players` on them. Writes
  `backend/outputs/player_projections.json` (gitignored). Run manually:
  `python -m backend.ratings.refresh_player_projections`.
- **`live_client/endpoints/stats/shot_locations.py`** (`PlayerShotLocations`, via nba_api's
  `LeagueDashPlayerShotLocations`) — league-wide shot attempts by court zone for one season.
  Its raw response shape is genuinely unusual even by this project's "non-standard shape"
  standards (see boxscore/play_by_play): confirmed live, `resultSets` here is a single dict,
  and its two header groups' *names* are misleading — the one named `"columns"` is actually the
  full flat 30-column list, and the other (`"SHOT_CATEGORY"`) holds the zone labels plus
  `columnsToSkip`/`columnSpan` metadata describing how to slice that flat list. Read this file's
  module docstring in full before touching it again — an earlier version had the two groups'
  roles reversed and only the real-network test caught it, not the mocked fixture (built from
  the same wrong assumption as the code, which is exactly the failure mode
  `test_integration_real_network.py` exists to catch).
- **Every payload carries an explicit "PRESEASON PROJECTION, not a live in-season ranking" note**
  (`refresh_player_projections.PROJECTED_LEADERS_NOTE`) — surfaced directly in the API response
  and rendered in the frontend, not just implied by a tab label.

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
- `GET /api/players/power-rankings?n=` — top-`n` (default 5, max `MAX_N`=50) offense/defense,
  each with a full `RatingBreakdown` (raw value, z-score, weight, contribution per component).
  `n` slices the already-cached top-50 list at request time — the refresh script always
  computes/caches the max, so "show more" on the frontend never needs a re-fetch. See refresh
  strategy below — 503s with an explanatory message if the cache has never been populated.
- `GET /api/players/projected-leaders?n=` — same shape and `n` behavior as power-rankings, but
  every number is a **preseason projection** (real current rosters, aging-curve-adjusted), not
  actual in-season stats — see "Projected player leaders" below. A separate endpoint, not a
  query param on power-rankings: genuinely different data and methodology, not a filter.
- `GET /api/coaches/wins-above-expectation` (optional `season`/`team` query filters) and
  `GET /api/coaches/career-summary` — each team-season also carries `pace`/`ast_pct`/
  `three_pa_rate` (null if `refresh_team_style.py` hasn't run), descriptive context, not a
  causal claim — see `ratings/team_style.py`.
- `GET /api/coaches/shot-heatmap?team=&season=` — the **one** endpoint in this API that calls
  `live_client` directly on a request, not from a scheduled refresh. Deliberate, narrow
  exception — see the comment on `dependencies.get_team_shot_heatmap` before adding another one
  like it: it's a single external call (~1.5s, confirmed), backed by `live_client`'s own
  never-expiring disk cache (so only the *first* request per team+season ever hits NBA.com), for
  a completed season with no staleness concern a scheduled refresh would even solve.

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
- The **forecast row only** (the current, not-yet-played season) has its `avg_age`/
  `avg_pts_top10`/`avg_production_score` overridden from `ratings/`'s roster-projection output
  when available (`train.py`'s `_apply_roster_projection`) — real current rosters instead of the
  stale team-level carry-forward every other row uses. `trainable` (historical seasons) is never
  touched by this; see "Roster projection" under Ratings/computation conventions above for the
  full pipeline, and `metadata.roster_projection` for which teams actually got a real projection
  vs. fell back to the stale value in a given run.

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

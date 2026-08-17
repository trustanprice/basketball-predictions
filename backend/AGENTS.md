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
    **All three are restricted to the top-10-by-projected-points players on the roster**, not
    the full ~15-19 man roster — matching how the historical training data was always implicitly
    top-10-only (the source player stats this project has only ever contained the top 10 per
    team, see root README's Data Sources). This was a real train/serve inconsistency until fixed
    (`avg_age`/`avg_production_score` were averaging every rostered player, including deep-bench/
    two-way players, while `avg_pts_top10` was already correctly restricted) — confirmed the fix
    by hand-recomputing a team's `avg_age` from just its top-10 scorers and matching the committed
    value exactly. A player who doesn't crack the top 10 by points (e.g. a min-minutes veteran)
    has zero influence on team talent features, by design — don't "fix" this back to a full-roster
    average.
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
  Once the master_df staleness fix above landed, this stopped being a live-forecast staleness
  problem for the *current* forecast row specifically — the forecast row's own-season payroll is
  now a real, known figure (that season already happened), not a carry-forward guess. The
  forward-looking multi-year salary figures in `data/raw/team-stats/team-payroll.csv` (real,
  user-supplied, current as of when they were entered — not fetched, since there's still no live
  source) are what the *next* forecast cycle will need once the season they describe completes;
  they aren't wired into anything yet on their own.
- **`Roster_Change` (`win_model/roster_change_features.py`) is a shipped, validated feature** —
  season-over-season roster-talent change (arriving players' own prior production minus departing
  players'), leak-free by construction (never uses a player's output on their new team). Prompted
  directly by this project's first real out-of-sample backtest and validated the same way
  everything else here is: walk-forward MAE 6.614 → 6.418. Not a uniform win — helps some of the
  real misses that motivated it, makes others worse — kept because the honest aggregate number is
  what decides, not whether it explains every anecdote. Three follow-up hypotheses
  (`age_curve_residual_features.py`, `defense_composite_features.py`, `coach_quality_features.py`)
  each looked like a further improvement in isolation, then **regressed once tested stacked on
  top of `Roster_Change`** instead of the plain baseline — their signal overlaps with what
  `Roster_Change` already captures. None are wired in; see `model_metadata.json`'s
  `feature_experiments` for the documented numbers, same treatment as `player_projection_features`
  and `gbm_knn_ensemble` below. **Lesson worth repeating for any future feature test: validate
  stacked on the real current baseline, not just against the plain unweighted one — isolated
  results here have repeatedly looked like wins and then evaporated once tested honestly.**

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
  `backend/outputs/player_projections.json` — **committed**, not gitignored (see the
  manual-refresh strategy note below; this was gitignored originally, un-ignored once Render's
  NBA.com connectivity was confirmed broken and manual-refresh-then-commit became the actual
  production data path). Run manually: `python -m backend.ratings.refresh_player_projections`.
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
- `GET /api/coaches/shot-heatmap?team=&season=&grid_cells=` — reads
  `refresh_shot_heatmaps.py`'s precomputed cache (all 30 teams, 10 historical seasons,
  offense+defense, at the default `grid_cells=25`), same "only ever read the file a scheduled
  refresh wrote" rule as player power rankings/team style above. This used to be the one
  endpoint in this API that called `live_client` directly on a request — a deliberate, narrow
  exception that held up fine on a working network (~1.5s per call, disk-cached after the
  first hit) but hung for minutes per request on Render, which can't reach stats.nba.com at all
  (see "Player ratings: refresh strategy" below). 503s immediately on a cache miss (non-default
  `grid_cells`, or a season the refresh script hasn't covered) rather than falling back to a
  live fetch — a fast, clear 503 is strictly better than one that arrives after minutes of
  hanging.

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
  rankings, and writes `backend/outputs/player_power_rankings.json` — **committed** (see the
  manual-refresh strategy note below — this was originally gitignored on the assumption the
  in-process loop would keep it fresh in production; that assumption turned out to be wrong on
  Render specifically, so it's committed now, same treatment `test_results.csv`/
  `model_metadata.json` and `team_style.json` get). Also exposes `is_stale(max_age_seconds)`, so
  a caller can check before fetching instead of always fetching unconditionally.
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
- **This in-process refresh loop cannot reach NBA.com from Render — confirmed, not a hypothesis,
  and not fixed at the infrastructure level.** Two real fix attempts, both confirmed failed with
  actual evidence (not assumed): (1) bumping the client's timeout 15s→40s and retries 3→4 — still
  hard-timed-out after all 4 attempts, confirmed via the deployed traceback showing
  `read timeout=40.0`, proving the new code ran and still failed; (2) moving the Render service to
  a different region (Ohio instead of Oregon) — identical failure, ruling out regional
  IP-throttling specifically and pointing at NBA.com blocking cloud/datacenter IP ranges more
  broadly. A GitHub Actions offload (running the refresh on GitHub-hosted runners' network
  instead) was scoped as a third option but **not what was actually adopted**.
- **The actual production strategy: manual local refresh + commit, not automation.** Since the
  same client works fine from a local/residential connection (verified repeatedly, real data
  pulled successfully every time), the chosen fix is running the refresh scripts locally
  (`refresh_player_ratings.py`, `refresh_team_style.py`, `refresh_player_projections.py`,
  `refresh_shot_heatmaps.py`) by hand periodically (weekly-ish, no fixed schedule) and
  committing the resulting `backend/outputs/*.json` files — same treatment as
  `master_df.csv`/`test_results.csv`. This is *why* those files moved from gitignored to
  committed (see the notes above). The in-process background loop (player ratings/team
  style/player projections only — `refresh_shot_heatmaps.py` was never added to it, see its own
  section above: a cache miss there 503s immediately rather than attempting any live fetch,
  in-process or otherwise) still runs in production as a harmless fallback for those three (it
  keeps retrying and failing gracefully, exactly as designed — verified this can never overwrite
  good committed data, since the write only happens after a fully successful fetch, past the
  point where it actually fails) — if Render's connectivity or hosting ever
  changes, the loop would just start working again with zero code changes needed.
- A **separate, unrelated bug** was found and fixed alongside this: `refresh_team_style.py` and
  `refresh_player_projections.py` were built with the exact same `is_stale()`/`run_refresh()`
  interface as `refresh_player_ratings.py` specifically so they could share this loop, but were
  never actually added to it — nothing was calling them, automatically or manually, until this was
  caught. Both are wired into `refresh_if_stale()` now. Don't assume a 503/null-style-field means
  the network issue above; check whether this wiring gap has recurred for any *new* refresh source
  added later.
- `refresh_roster_projection.py` also had a real bug, unrelated to Render: one player's
  `PlayerCareerStats` response doesn't match what `nba_api` expects (`KeyError: 'resultSet'`, not
  a timeout), and the ~400-500-call batch had no per-player error handling, so one bad player
  crashed the entire run. Fixed to catch and log per-player, excluding that player the same way an
  empty response already was — if this script fails again, check whether it's this same failure
  mode on a *different* player before assuming something bigger broke.

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
- Point predictions ship with a prediction interval, not just a single number. The interval
  comes from two **independently-fit** GBM quantile models (10th/90th percentile) — nothing
  guarantees either stays on the correct side of the point estimate for every team
  ("quantile crossing"). A naive `upper = max(upper, point)` clamp prevents an invalid interval
  but produces a degenerate near-zero-margin one instead whenever crossing happens — confirmed
  live in a real run: 9/30 teams had an upper margin under 1 win while their lower margin was a
  normal 8-14 wins, silently implying "no upside uncertainty" for that team specifically, which
  wasn't true. Where crossing is detected, the crossed side now mirrors the other (uncrossed)
  side's margin instead of collapsing to zero width (`train.py`, right after the interval is
  computed) — an honest "no trustworthy quantile fit on this side, using the other side's scale
  as the best estimate" fallback. If you ever see a team with a suspiciously tight one-sided
  margin again, check whether this mirroring logic still covers the case before assuming
  something new broke.
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
- **Schedule simulation (`win_model/schedule_simulation.py`) is a shipped, validated adjustment
  to the forecast row's `Pred_Wins`/`Pred_Wins_Lower`/`Pred_Wins_Upper`** — the one feature
  hypothesis this project tried that survived the honest test (see
  `model_metadata.json`'s `feature_experiments.schedule_simulation`; `age_curve_residual`,
  `defense_composite`, `coach_quality`, and `recency_weighting` all failed the same test and
  are documented as rejected right next to it). Instead of treating a team's predicted win
  percentage as flat across all 82 games, it simulates the real schedule game-by-game — log5
  win probability per matchup (Bill James' formula, standard for combining two teams' win
  percentages into a head-to-head probability), a home-court edge calibrated from this
  project's own historical `Home_W`/`Home_L` split (not hand-picked), Monte Carlo averaged over
  10,000 simulated seasons. Pooled across every backtestable season (2017-18 through 2025-26,
  270 team-seasons, real historical schedules fetched live via `live_client/endpoints/stats/
  schedule.py`'s `LeagueSchedule` → nba_api's `ScheduleLeagueV2`), walk-forward MAE improves
  6.835 → 6.768 wins — real but modest, and it clearly hurts in both pandemic-disrupted seasons
  (2019-20, 2020-21) while helping in most normal ones; see `schedule_simulation_backtest.py`.
  - **Not a `train.py` step, and not a `FEATURE_COLUMNS` addition.** It needs the forecast row's
    already-calibrated `Pred_Wins` as its rating input, which `train.py` is what produces — so it
    runs as a separate pass *after* `train.py`, not inside its pipeline (chicken-and-egg
    otherwise). `refresh_schedule_simulation.py` reads `test_results.csv`'s current forecast
    row, fetches the live schedule for that season, simulates, and overwrites that row's
    `Pred_Wins`/`Pred_Wins_Lower`/`Pred_Wins_Upper` in place with the simulated mean and
    10th/90th percentiles — replacing the point estimate and its interval *together*, not just
    adding a second number, so they stay self-consistent (same reasoning as the quantile-crossing
    fix above: a point estimate and interval from two different mechanisms have no guarantee of
    agreeing).
  - **Operationally load-bearing, easy to silently undo**: re-running `train.py` regenerates
    `test_results.csv` from scratch and puts the flat, non-schedule-adjusted `Pred_Wins` straight
    back for the forecast row. `refresh_schedule_simulation.py` must be re-run after every
    `train.py` run for the forecast row to reflect the schedule adjustment — same class of "gets
    silently wiped on regeneration" issue as `recency_weighting`'s `feature_experiments` entry
    (which is why that one's now hardcoded in `train.py` itself instead of hand-patched into the
    JSON — this can't get the same fix, since it structurally can't run inside `train.py`, so the
    ordering just has to be remembered). Run both, in order:
    `python -m backend.win_model.train && python -m backend.win_model.refresh_schedule_simulation`.
  - **The live schedule can be short of the full 1,230 games until the NBA Cup knockout bracket
    resolves** — semifinal/championship slots are `TBD vs TBD` in the raw feed until the group
    stage completes (confirmed live: 1,200 of 1,230 games resolved for 2026-27 as of this
    writing), so `Pred_Wins` for the forecast row will sum to whatever number of games are
    currently known, not exactly 1,230, until re-run once the bracket is set. This is a real,
    current gap, not a bug — no manual workaround needed, just re-run the refresh once the
    schedule fills in.
  - **Surfaced on the site, not just in this file.** `train.py` writes a `schedule_adjustment`
    placeholder (`applied: false`) into `model_metadata.json`; `refresh_schedule_simulation.py`
    patches it with the real numbers (games simulated, home-court edge, the pooled validation
    MAE) after it runs. Wired all the way through — `backend/api/schemas.py`'s `ModelMetadata`,
    `frontend/lib/types.ts`, and rendered in `MethodologyPanel.tsx` — because this project's
    other four rejected feature experiments were found to not be surfaced on the site at all
    (`feature_experiments` was never added to the API schema or frontend types, a pre-existing
    gap this didn't fix — see `model_metadata.json`'s `feature_experiments` for those, readable
    only by reading the file/repo directly, not via the API). Don't let a future adjustment like
    this one land only in the raw JSON again without checking whether it needs the same
    schema→types→component wiring to actually reach a site visitor.

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

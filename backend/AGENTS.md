# backend/

All Python for this project: the win-total model, the NBA.com live data client, the ratings
engine, and (eventually) the API the frontend calls. See root `AGENTS.md` for the module split.

## Layout

```
backend/
├── win_model/       # team win-total prediction (Phase 1)
├── live_client/      # NBA.com data client (Phase 2)
├── ratings/           # player ratings + coaching eval, consumes live_client output (Phase 3-4)
├── api/                # FastAPI app serving win_model + ratings results (Phase 6, not yet built)
├── notebooks/          # exploratory work; production logic belongs in the packages above, not here
├── tests/              # pytest, mirrors package layout (tests/win_model/, tests/live_client/, ...)
├── outputs/             # gitignored model artifacts/figures
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

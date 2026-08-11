# data/

Static, historical (2016–2025), manually scraped/curated. This is the only source for payroll,
draft, and coach-tenure history, and it's the backtest set for `backend/win_model/` and the
coaching evaluation module.

- **Never overwritten by the live client.** `backend/live_client/` writes to its own disk cache
  under `backend/`, not here.
- `raw/` → `processed/` is a one-way, mostly manual pipeline (see `backend/notebooks/`
  `01_data_cleaning.ipynb`) — there's no automated job that regenerates these files, so don't
  assume a "rebuild" step exists.
- Not the same thing as `backend/live_client/lookups/`: that directory holds static player/team
  ID↔name reference tables the live client depends on to parse responses. Both are "static, not
  live-fetched," but `data/` is historical backtest data and `lookups/` is a client dependency —
  don't merge them.
- `data/raw/master-stats/test_results.csv` and `model_metadata.json` are the one exception to
  "manually curated": they're generated **output**, written by `backend/win_model/train.py` each
  time it runs, not hand-collected source data. They live here (rather than under `backend/`)
  only because the app reads them at runtime and Streamlit Cloud has no separate artifact store —
  don't treat them as frozen/curated the way the rest of this directory is, and don't hand-edit
  them.
- **`master_df.csv` must also be committed** (`.gitignore` explicitly un-ignores it, same pattern
  as the two files above) — `backend/api/dependencies.py` reads it directly at request time for
  every `/api/coaches/*` endpoint. It was missed when `test_results.csv`/`model_metadata.json`
  got their exceptions added, so it silently didn't exist on Render's deploy — every coaching
  endpoint 503'd (`master_df.csv not found`) until this was caught and fixed. If a future
  `git status` shows this file as untracked, that's the same bug recurring — re-check
  `.gitignore`'s `data/raw/master-stats/*` block, don't just re-add it and move on without
  understanding why it went missing.

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

# 🏀 Basketball Predictions

An NBA analytics project that started as a single team win-total model and has grown into
three connected pieces: a walk-forward-validated win predictor, a live player power-rankings
engine, and a coaching evaluation model — all built to be transparent about *how* every number
was produced, not just what it is.

👉 Transitional Streamlit demo (being replaced by the Next.js frontend below):
[Streamlit App](https://basketball-predictions-trustanprice.streamlit.app/)

👉 Codebase: [GitHub Repo](https://github.com/trustanprice/basketball-predictions)

---

## What's here

- **Win-total model** (`backend/win_model/`) — predicts each team's next-season win total.
  Walk-forward validated (trained only on past seasons, never randomly shuffled), compares a
  KNN regressor against a monotonic-constrained gradient-boosted model, and ships every
  prediction with an interval and a plain-language "how this was calculated" explanation
  rather than a bare number. Honest backtested accuracy — not an inflated same-season
  number — is reported directly in the app.
- **Live data client** (`backend/live_client/`) — pulls real NBA.com data (season stats,
  advanced metrics, rosters) through `nba_api`, wrapped in this project's own retry, disk
  cache, and schema-validation layer so a silent upstream column rename fails loudly instead
  of quietly corrupting a rating.
- **Player power rankings** (`backend/ratings/`) — top offensive/defensive players, computed
  as a transparent weighted composite (z-scored inputs, documented weights) rather than a
  black-box model. Every rating expands into its exact formula, raw inputs, z-scores, and
  per-component contribution.
- **Coaching evaluation** (`backend/ratings/coaching_eval.py`) — actual win% vs.
  roster-talent-implied win%, tracked per coach across every team and season they've coached,
  using the same transparency standard as the player ratings.
- **API** (`backend/api/`) — a FastAPI app serving all of the above as JSON, with live-data
  results refreshed on a background schedule rather than fetched on every request.
- **Frontend** (`frontend/`) — a Next.js (App Router, TypeScript, Tailwind) app that reads
  exclusively from the API above; no direct dataframe or CSV access from the frontend.

See [`AGENTS.md`](AGENTS.md) for the full module breakdown and the per-directory docs it
links to ([`backend/AGENTS.md`](backend/AGENTS.md), [`data/AGENTS.md`](data/AGENTS.md),
[`frontend/AGENTS.md`](frontend/AGENTS.md)).

---

## Project structure

```
Basketball-Predictions/
├── data/                  # Static, historical (2016–2025) datasets — see data/AGENTS.md
│   ├── raw/
│   └── processed/
│
├── backend/                # All Python — see backend/AGENTS.md
│   ├── win_model/           # Data loading, features, and the win-total model
│   ├── live_client/         # NBA.com data client (nba_api underneath, own cache/validation)
│   ├── ratings/              # Player power rankings + coaching evaluation
│   ├── api/                   # FastAPI app serving the above to the frontend
│   ├── notebooks/              # Jupyter notebooks (data cleaning, exploration, early modeling)
│   ├── tests/
│   └── requirements.txt
│
├── frontend/                # Next.js app — see frontend/AGENTS.md
│
├── app.py                   # Streamlit app — transitional, stays at repo root for the
│                             # existing Streamlit Cloud deployment until frontend/ fully replaces it
├── requirements.txt         # Pointer to backend/requirements.txt (keeps Streamlit Cloud working)
├── render.yaml               # Backend hosting config
├── .gitignore
└── README.md
```

---

## Data sources

- **Team stats & records** — season results, home/road splits, pre/post All-Star splits, win %
  (historical, 2016–2025, curated in `data/`).
- **Payroll** — team salary data, 2016–2025 (curated; current-season payroll isn't available
  from any free live source, so the app labels it explicitly as last-known, not live).
- **Coaching data** — tenure, win/loss records, coach counts per season.
- **Draft data** — picks aligned by season/year.
- **Strength of Schedule (SOS)** — self-calculated from opponent win%. The app labels this
  explicitly as a self-calculated metric, not a third-party benchmark, and notes when it's
  unavailable for the current forecast season.
- **Live player/team data** — season totals, advanced metrics, and rosters, fetched from
  NBA.com through `backend/live_client/`.

---

## Running it locally

### Backend (API + win model)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
cd ..
uvicorn backend.api.main:app --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`. The frontend expects the API running at
`http://localhost:8000` (see `frontend/.env.example`).

### Transitional Streamlit app

```bash
source backend/venv/bin/activate
streamlit run app.py
```

### Notebooks

```bash
cd backend
jupyter notebook
```

---

## Goals

- Predict team win totals with honestly validated accuracy, not an inflated same-season number
- Surface a live, explainable view of who's actually playing well, offense and defense, as the
  season unfolds
- Evaluate coaching staffs against the roster talent they've had, not in isolation
- Make every number's methodology visible, not just the number itself

---

## Tech stack

- **Backend:** Python 3.11+, pandas, scikit-learn, FastAPI, `nba_api`, pytest
- **Frontend:** Next.js (App Router), TypeScript, Tailwind
- **Transitional:** Streamlit (being phased out in favor of the Next.js frontend)

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd
like to change.

---

## License & Attribution

Historical data collected from basketball-reference.com and nba.com for educational purposes.
Live data via NBA.com's stats endpoints, through the `nba_api` package.

"""backend/win_model/refresh_schedule_simulation.py

Applies the validated schedule-simulation adjustment (see
schedule_simulation_backtest.py -- pooled MAE 6.835 -> 6.768 across all 9
backtestable seasons, a real if modest improvement, unlike the four rejected
feature_experiments in train.py) to the current forecast row(s) in
test_results.csv.

Sequencing, not a train.py step: schedule simulation needs Pred_Wins as its
rating input, but train.py is what PRODUCES Pred_Wins -- so this can't run
inside train.py itself (chicken-and-egg) and must run as a separate pass
afterward, the same "refresh script layered on top of train.py's output"
shape as refresh_roster_projection.py, just on the other side of train.py
instead of feeding into it. Concretely: this script reads the forecast
season's already-calibrated Pred_Wins from test_results.csv, uses Pred_Wins/82
as each team's rating, fetches the real live schedule, simulates, and
OVERWRITES that row's Pred_Wins/Pred_Wins_Lower/Pred_Wins_Upper in place with
the schedule-simulated mean and 10th/90th percentiles -- replacing the point
estimate and its interval together (not just appending a second number)
because they need to come from the same distribution to stay self-consistent
(mirrors the quantile-crossing fix elsewhere in this project: a point
estimate and interval built from two different mechanisms have no guarantee
of agreeing).

**Operationally load-bearing**: re-running train.py regenerates test_results.csv
from scratch and will silently put the flat, non-schedule-adjusted Pred_Wins
back for the forecast row -- this script must be re-run after every train.py
run for the forecast row to reflect the schedule adjustment. See
backend/AGENTS.md.

Run manually (after train.py):  python -m backend.win_model.refresh_schedule_simulation
"""

from __future__ import annotations

import pandas as pd

from .data_loader import MASTER_DF_FILE, RESULTS_FILE
from .schedule_simulation import (
    fetch_regular_season_schedule,
    home_court_edge_from_history,
    simulate_season,
)

N_SIMULATIONS = 10000
SIM_SEED = 42


def _nba_season_format(season: int) -> str:
    return f"{season - 1}-{str(season)[-2:]}"


def run_refresh(n_simulations: int = N_SIMULATIONS, seed: int = SIM_SEED) -> dict:
    master_df = pd.read_csv(MASTER_DF_FILE)
    test_results = pd.read_csv(RESULTS_FILE)

    forecast_season = int(test_results["Season"].max())
    forecast_rows = test_results[test_results["Season"] == forecast_season]
    if forecast_rows["W"].notna().any():
        raise ValueError(
            f"Season={forecast_season} has real results in test_results.csv -- refusing to "
            f"schedule-adjust a season that's already been played. Something upstream (train.py's "
            f"forecast-row wiring, or master_df.csv's newest Season) is likely stale."
        )

    ratings = dict(zip(forecast_rows["Team"], forecast_rows["Pred_Wins"] / 82.0))
    edge = home_court_edge_from_history(master_df)
    nba_season = _nba_season_format(forecast_season)
    schedule = fetch_regular_season_schedule(nba_season)

    sim = simulate_season(schedule, ratings, edge, n_simulations=n_simulations, seed=seed)
    sim_by_team = sim.set_index("Team")

    updated = test_results.copy()
    mask = updated["Season"] == forecast_season
    updated.loc[mask, "Pred_Wins"] = updated.loc[mask, "Team"].map(sim_by_team["sim_mean_wins"])
    updated.loc[mask, "Pred_Wins_Lower"] = updated.loc[mask, "Team"].map(sim_by_team["sim_p10_wins"])
    updated.loc[mask, "Pred_Wins_Upper"] = updated.loc[mask, "Team"].map(sim_by_team["sim_p90_wins"])
    updated.to_csv(RESULTS_FILE, index=False)

    return {
        "forecast_season": nba_season,
        "n_teams_adjusted": int(mask.sum()),
        "n_games_simulated": len(schedule),
        "home_court_edge": round(edge, 4),
    }


if __name__ == "__main__":
    result = run_refresh()
    print(f"Applied schedule-simulated win totals for {result['forecast_season']} "
          f"({result['n_teams_adjusted']} teams, {result['n_games_simulated']} games simulated, "
          f"home_court_edge={result['home_court_edge']})")
    print(f"Wrote {RESULTS_FILE}")

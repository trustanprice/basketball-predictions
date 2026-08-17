"""backend/win_model/schedule_simulation_backtest.py

Decisive test for schedule_simulation.py, matching every other feature
hypothesis in this project (see recency_weighting.py, train.py's
feature_experiments): does simulating the real schedule game-by-game produce
a more accurate win-total estimate than the win_model's plain
predict-a-flat-win-rate-across-82-games approach?

Tested across every backtestable season in test_results.csv (2018-2026 in
this project's end-year Season convention, i.e. real 2017-18 through
2025-26) -- not just one season. A single-season test was tried first and
rejected as too weak a sample (30 teams) to trust either way; nba_api's
ScheduleLeagueV2 turns out to serve real historical schedules for every one
of these seasons (including the COVID-shortened 2019-20, 1,059 games instead
of 1,230 -- handled automatically, nothing hardcoded), so there's no reason
to settle for n=1 when the walk-forward standard everywhere else in this
project is pooled multi-season MAE.

Ratings come from test_results.csv's Pred_Wins for each season -- the
win_model's own honest walk-forward out-of-fold prediction (trained only on
other seasons, never shown that season's actual results), not a
fitted-on-itself number. Home-court edge is calibrated once from Home_W/Home_L
for seasons strictly before the earliest backtested season, so calibration
data and every tested season stay non-overlapping -- not recalibrated
per-season, which would leak each season's own home/away split into its own
test.

Compares schedule-sim's pooled MAE against the plain model's pooled MAE on
the exact same team-seasons, so this is apples-to-apples with each other, and
directly comparable to this project's overall backtest_accuracy MAE (6.434
wins as of the last train.py run) -- both are pooled multi-season numbers,
not per-season snapshots.

Run manually: python -m backend.win_model.schedule_simulation_backtest
"""

from __future__ import annotations

import pandas as pd

from .data_loader import MASTER_DF_FILE, RESULTS_FILE
from .schedule_simulation import (
    fetch_regular_season_schedule,
    home_court_edge_from_history,
    simulate_season,
)

FORECAST_ONLY_SEASON = 2027  # no real W yet -- excluded from backtest, matches train.py


def _nba_season_format(season: int) -> str:
    """Season=2026 (this project's end-year convention) -> "2025-26"."""
    return f"{season - 1}-{str(season)[-2:]}"


def run_backtest(n_simulations: int = 10000, seed: int = 42) -> dict:
    master_df = pd.read_csv(MASTER_DF_FILE)
    test_results = pd.read_csv(RESULTS_FILE)

    backtestable = sorted(s for s in test_results["Season"].unique() if s != FORECAST_ONLY_SEASON)
    if not backtestable:
        raise ValueError("No backtestable seasons in test_results.csv — run train.py first.")

    edge = home_court_edge_from_history(master_df, before_season=min(backtestable))

    per_season = []
    all_rows = []
    for season in backtestable:
        season_rows = test_results[test_results["Season"] == season].copy()
        ratings = dict(zip(season_rows["Team"], season_rows["Pred_Wins"] / 82.0))
        actual_wins = dict(zip(season_rows["Team"], season_rows["W"]))
        plain_pred_wins = dict(zip(season_rows["Team"], season_rows["Pred_Wins"]))

        schedule = fetch_regular_season_schedule(_nba_season_format(season))
        sim = simulate_season(schedule, ratings, edge, n_simulations=n_simulations, seed=seed)
        sim["Season"] = season
        sim["actual_wins"] = sim["Team"].map(actual_wins)
        sim["plain_pred_wins"] = sim["Team"].map(plain_pred_wins)
        sim["schedule_sim_error"] = (sim["sim_mean_wins"] - sim["actual_wins"]).abs()
        sim["plain_error"] = (sim["plain_pred_wins"] - sim["actual_wins"]).abs()

        per_season.append({
            "season": _nba_season_format(season),
            "n_games_simulated": len(schedule),
            "plain_mae": round(float(sim["plain_error"].mean()), 3),
            "schedule_sim_mae": round(float(sim["schedule_sim_error"].mean()), 3),
        })
        all_rows.append(sim)

    pooled = pd.concat(all_rows, ignore_index=True)
    plain_mae = pooled["plain_error"].mean()
    schedule_sim_mae = pooled["schedule_sim_error"].mean()

    return {
        "seasons_tested": [_nba_season_format(s) for s in backtestable],
        "n_team_seasons": len(pooled),
        "home_court_edge": round(edge, 4),
        "plain_model_mae": round(float(plain_mae), 3),
        "schedule_sim_mae": round(float(schedule_sim_mae), 3),
        "improves_mae": bool(schedule_sim_mae < plain_mae),
        "per_season": per_season,
    }


if __name__ == "__main__":
    result = run_backtest()
    print(f"Seasons tested: {', '.join(result['seasons_tested'])} "
          f"({result['n_team_seasons']} team-seasons pooled)")
    print(f"Home-court edge (calibrated on seasons before the earliest tested): {result['home_court_edge']}")
    print()
    for row in result["per_season"]:
        print(f"  {row['season']}: plain={row['plain_mae']} schedule_sim={row['schedule_sim_mae']} "
              f"({row['n_games_simulated']} games)")
    print()
    print(f"Pooled plain model MAE:  {result['plain_model_mae']}")
    print(f"Pooled schedule-sim MAE: {result['schedule_sim_mae']}")
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Schedule simulation {verdict} win-total accuracy vs. the plain model, pooled across "
          f"every backtestable season.")

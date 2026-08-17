"""backend/win_model/schedule_simulation.py

Schedule-aware win total estimation: instead of treating a team's predicted
win percentage as uniform across all 82 games, simulate the real schedule
game-by-game so teams with harder schedules (more games against strong
opponents) end up with a lower expected win total than teams with the same
underlying rating but an easier slate, and vice versa.

Deliberately NOT "whichever team's rating is higher wins that game" -- that's
deterministic and produces degenerate records (division-worst teams near
0-82), since real NBA teams beat better opponents regularly. Every game gets
a win PROBABILITY instead, via the log5 formula (Bill James -- the standard
way to combine two teams' win percentages into a head-to-head probability),
plus a home-court adjustment calibrated from this project's own historical
Home_W/Home_L data rather than a hand-picked constant. A full season is then
simulated thousands of times (Monte Carlo) and averaged into an expected win
total per team -- mathematically converges to sum-of-per-game-probabilities
as n_simulations grows, but simulating game-by-game (rather than summing
probabilities directly) also yields a real win-total distribution "for free",
consistent with how prediction intervals already work elsewhere in this
project (see model.gbm_quantile_interval).

Ratings in, expected wins out: this module takes team win percentages as
given (usually the win_model's own Pred_Wins / 82 for each team) and answers
"does simulating the real schedule with these ratings estimate final win
totals more accurately than assuming a flat win rate across all 82 games?" --
see schedule_simulation_backtest.py for the honest answer, tested the same
stacked-vs-isolated way as every other feature hypothesis in this project
(see train.py's feature_experiments and backend/AGENTS.md).

Run manually: python -m backend.win_model.schedule_simulation_backtest
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from ..live_client.endpoints.stats.schedule import LeagueSchedule
    from ..live_client.lookups.loader import team_name_for_id
except ImportError:
    from live_client.endpoints.stats.schedule import LeagueSchedule
    from live_client.lookups.loader import team_name_for_id


def log5(win_pct_a: float, win_pct_b: float) -> float:
    """Bill James' log5 formula: P(A beats B) given each team's win percentage
    against a league-average opponent. Degenerates to 0.5 when the shared
    denominator would be zero (both teams undefeated or both winless)."""
    denom = win_pct_a + win_pct_b - 2 * win_pct_a * win_pct_b
    if denom == 0:
        return 0.5
    return (win_pct_a - win_pct_a * win_pct_b) / denom


def home_court_edge_from_history(master_df: pd.DataFrame, before_season: int | None = None) -> float:
    """Empirical league-wide home-court advantage, as a probability shift off
    0.5 -- e.g. 0.57 league-wide home win rate returns 0.07. Computed from
    this project's own historical Home_W/Home_L columns rather than a
    hand-picked constant, matching the rest of this project's live-verify
    ethos. Excludes rows with no Home_W/Home_L (the forecast-only row) and,
    if `before_season` is given, any season >= it -- lets a backtest calibrate
    only on data that would have been available at prediction time."""
    rows = master_df.dropna(subset=["Home_W", "Home_L"])
    if before_season is not None:
        rows = rows[rows["Season"] < before_season]
    home_wins = rows["Home_W"].sum()
    home_games = home_wins + rows["Home_L"].sum()
    if home_games == 0:
        raise ValueError("No historical Home_W/Home_L data available to calibrate home-court edge.")
    return float(home_wins / home_games) - 0.5


def game_win_probability(home_win_pct: float, away_win_pct: float, home_court_edge: float) -> float:
    """P(home team wins), combining log5 with the calibrated home-court edge.
    Clipped away from exactly 0/1 so no game is ever a mathematical certainty
    -- a rating gap this large still shouldn't zero out real NBA game
    variance."""
    base = log5(home_win_pct, away_win_pct)
    return float(np.clip(base + home_court_edge, 0.02, 0.98))


def fetch_regular_season_schedule(season: str) -> pd.DataFrame:
    """Real full regular-season schedule for `season` (e.g. "2026-27"), team
    names resolved to this project's "City Team" convention (matching
    master_df.csv's Team column) via the same team_id lookup the rest of
    live_client uses. See endpoints/stats/schedule.py for what's excluded
    (preseason, playoffs, not-yet-resolved NBA Cup knockout games)."""
    raw = LeagueSchedule(season=season).fetch().to_dataframe()
    return pd.DataFrame({
        "gameId": raw["gameId"],
        "home_team": raw["homeTeam_teamId"].map(team_name_for_id),
        "away_team": raw["awayTeam_teamId"].map(team_name_for_id),
    })


def simulate_season(
    schedule: pd.DataFrame,
    team_win_pct: dict[str, float],
    home_court_edge: float,
    n_simulations: int = 10000,
    seed: int = 42,
) -> pd.DataFrame:
    """Monte Carlo season simulation. `schedule` needs home_team/away_team
    columns (team names matching `team_win_pct`'s keys). Returns one row per
    team: sim_mean_wins (the schedule-aware win total estimate), sim_std_wins,
    sim_p10_wins/sim_p90_wins (10th/90th percentile across simulations, for a
    prediction interval in the same spirit as the win_model's own quantile
    intervals).

    Any team not present in `team_win_pct` is dropped from its games with a
    ValueError, rather than silently defaulting to 0.5 -- an unrated team
    means a real gap in the input, not something to paper over.
    """
    missing = set(schedule["home_team"]) | set(schedule["away_team"])
    missing -= set(team_win_pct)
    if missing:
        raise ValueError(f"No win percentage supplied for: {sorted(missing)}")

    teams = sorted(team_win_pct)
    home_idx = schedule["home_team"].map({t: i for i, t in enumerate(teams)}).to_numpy()
    away_idx = schedule["away_team"].map({t: i for i, t in enumerate(teams)}).to_numpy()

    home_prob = np.array([
        game_win_probability(team_win_pct[h], team_win_pct[a], home_court_edge)
        for h, a in zip(schedule["home_team"], schedule["away_team"])
    ])

    rng = np.random.default_rng(seed)
    n_games = len(schedule)
    n_teams = len(teams)

    draws = rng.random((n_simulations, n_games))
    home_wins = draws < home_prob[np.newaxis, :]
    winner_idx = np.where(home_wins, home_idx[np.newaxis, :], away_idx[np.newaxis, :])

    sim_ids = np.repeat(np.arange(n_simulations), n_games)
    flat_bins = sim_ids * n_teams + winner_idx.ravel()
    wins = np.bincount(flat_bins, minlength=n_simulations * n_teams).reshape(n_simulations, n_teams)

    return pd.DataFrame({
        "Team": teams,
        "sim_mean_wins": wins.mean(axis=0),
        "sim_std_wins": wins.std(axis=0),
        "sim_p10_wins": np.percentile(wins, 10, axis=0),
        "sim_p90_wins": np.percentile(wins, 90, axis=0),
    }).sort_values("Team").reset_index(drop=True)

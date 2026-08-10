"""backend/win_model/calibration.py

Post-processing calibration applied to a season's raw predictions (30 teams),
correcting two real problems, not stylistic ones:

1. Nothing constrains 30 teams' predicted wins to sum to a real schedule's
   total. 30 teams x 82 games = 2,460 team-games, but each real game involves
   two teams, so exactly 1,230 games are actually played league-wide in a
   season -- the sum of all 30 teams' wins (and losses) must equal 1,230
   (mean 41). The raw model has no way to know this; it predicts each team
   independently.
2. The raw predicted spread is compressed relative to real NBA history --
   regression pulls extreme teams toward the mean more than real seasons
   actually do (real seasons regularly have a 60+-win team and a 20-ish-win
   team). Rescaling each team's deviation from the season mean to match the
   real historical spread corrects this without changing the mean.

Order matters: rescale variance first (around the raw mean, so the mean is
untouched), *then* shift every team by a constant so the sum lands on exactly
1,230 (mean exactly 41) -- shifting first would just get undone by the
rescale's own mean-preserving math. Clip to a sane range last, since clipping
can itself break the exact-sum constraint (a team clipped at 82 or 0 can't
absorb its share of the shift) -- see _clip_and_redistribute.

Applied identically to every walk-forward fold's out-of-fold predictions
(one season's 30 teams at a time) and to the live forecast row -- see
backend/win_model/train.py, which also reports the walk-forward MAE with and
without this calibration rather than assuming it helps.
"""

from __future__ import annotations

import numpy as np

# 30 teams x 82 games each = 2,460 team-games; each real game involves two
# teams, so 1,230 games are actually played -- the real, unavoidable
# constraint every complete season's win totals (and loss totals) satisfy.
N_TEAMS = 30
GAMES_PER_TEAM = 82
TOTAL_SEASON_WINS = N_TEAMS * GAMES_PER_TEAM // 2  # 1,230
MIN_WINS = 0.0
MAX_WINS = float(GAMES_PER_TEAM)

_ZERO_DEFICIT_TOLERANCE = 1e-9
_MAX_REDISTRIBUTE_ITERATIONS = 50


def historical_win_std(real_win_totals) -> float:
    """Population std (ddof=0, matching ratings/core.py's zscore convention)
    of real, completed-season win totals -- the target spread calibration
    rescales predictions to match. Callers pass real historical outcomes only
    (e.g. the walk-forward target column across every trainable row) -- never
    include the current unplayed forecast season, which has no real result
    yet to measure a spread from.
    """
    values = np.asarray(real_win_totals, dtype=float)
    if len(values) < 2:
        raise ValueError("historical_win_std needs at least 2 real observations")
    return float(values.std(ddof=0))


def _clip_and_redistribute(
    values: np.ndarray,
    lower: float,
    upper: float,
    target_sum: float,
    max_iterations: int = _MAX_REDISTRIBUTE_ITERATIONS,
) -> np.ndarray:
    """Clips to [lower, upper], then redistributes whatever sum clipping
    removed (or added) proportionally across the teams *not* sitting at a
    bound, so the exact-target_sum constraint holds after clipping too.
    Proportional to each free team's own (already-clipped) value -- a team
    predicted for 55 wins absorbs more of the correction than one predicted
    for 25, rather than an equal flat split.

    Redistributing can itself push a previously-free team past a bound, so
    this re-clips and re-checks the deficit in a loop (bounded by
    max_iterations, which realistic NBA-shaped inputs never come close to
    needing -- it's a safety bound, not a tuning knob).
    """
    values = np.asarray(values, dtype=float).copy()
    for _ in range(max_iterations):
        clipped = np.clip(values, lower, upper)
        deficit = target_sum - clipped.sum()
        if abs(deficit) < _ZERO_DEFICIT_TOLERANCE:
            return clipped

        free = (clipped > lower) & (clipped < upper)
        if not free.any():
            # Every team is pinned to a bound -- physically nothing left that
            # can absorb the remainder (e.g. target_sum itself is outside
            # what N teams can sum to within [lower, upper]). Return the best
            # achievable result rather than looping forever.
            return clipped

        free_values = clipped[free]
        total = free_values.sum()
        weights = (
            free_values / total if total > 0 else np.full(free_values.shape, 1.0 / free_values.size)
        )
        clipped[free] = free_values + deficit * weights
        values = clipped

    return np.clip(values, lower, upper)


def calibrate_season_predictions(
    raw_predictions,
    historical_std: float,
    target_sum: float = TOTAL_SEASON_WINS,
    lower_bound: float = MIN_WINS,
    upper_bound: float = MAX_WINS,
) -> np.ndarray:
    """Rescales one season's raw predictions (all teams playing that season)
    to match `historical_std`'s spread, shifts them to sum to `target_sum`,
    then clips/redistributes to stay in [lower_bound, upper_bound]. See
    module docstring for why this exact order.

    `raw_predictions` must be every team playing in the season being
    calibrated (a walk-forward fold's held-out season, or the live forecast
    row) -- calibrating a subset would compute the wrong mean/std/sum for
    what's actually a partial season.
    """
    raw = np.asarray(raw_predictions, dtype=float)
    n = len(raw)
    raw_mean = raw.mean()
    raw_std = raw.std(ddof=0)

    if raw_std > 0:
        rescaled = raw_mean + (raw - raw_mean) * (historical_std / raw_std)
    else:
        # Degenerate: every raw prediction identical (e.g. n=1, or a model
        # that collapsed to one value) -- nothing to rescale a spread around.
        rescaled = raw.copy()

    shift = (target_sum / n) - rescaled.mean()
    shifted = rescaled + shift

    return _clip_and_redistribute(shifted, lower_bound, upper_bound, target_sum)


def recenter_interval(raw_point, raw_lower, raw_upper, calibrated_point):
    """Shifts an existing prediction interval by the same total adjustment
    (rescale + shift + any clip/redistribution) applied to its point
    estimate, computed as calibrated_point - raw_point per team -- this
    stays correct even for a team whose point estimate got extra adjustment
    from redistribution, since that's already baked into the difference.
    """
    delta = np.asarray(calibrated_point, dtype=float) - np.asarray(raw_point, dtype=float)
    return np.asarray(raw_lower, dtype=float) + delta, np.asarray(raw_upper, dtype=float) + delta

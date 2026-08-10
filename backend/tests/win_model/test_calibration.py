import numpy as np
import pytest

from win_model.calibration import (
    MAX_WINS,
    MIN_WINS,
    TOTAL_SEASON_WINS,
    _clip_and_redistribute,
    calibrate_season_predictions,
    historical_win_std,
    recenter_interval,
)


def test_total_season_wins_matches_real_schedule_constraint():
    # 30 teams x 82 games each = 2,460 team-games; each real game involves
    # two teams, so exactly half that many games are actually played.
    assert TOTAL_SEASON_WINS == 1230
    assert TOTAL_SEASON_WINS == 30 * 82 / 2


def test_historical_win_std_matches_population_std_hand_computed():
    # [21, 41, 61]: mean 41, deviations [-20, 0, 20] -> population std
    # sqrt((400+0+400)/3) = sqrt(266.667).
    result = historical_win_std([21.0, 41.0, 61.0])
    assert result == pytest.approx(np.sqrt(800 / 3))


def test_historical_win_std_requires_at_least_two_observations():
    with pytest.raises(ValueError):
        historical_win_std([41.0])


def test_clip_and_redistribute_no_clipping_needed_is_a_no_op():
    values = np.array([30.0, 41.0, 52.0])  # already sums to 123
    result = _clip_and_redistribute(values, MIN_WINS, MAX_WINS, target_sum=123.0)
    np.testing.assert_allclose(result, values)


def test_clip_and_redistribute_single_free_team_absorbs_exact_deficit():
    # Hand-computed: clip([90, 40, -7], 0, 82) = [82, 40, 0], sum=122,
    # deficit=123-122=1. Only index 1 (40) is strictly inside (0, 82), so it
    # alone absorbs the +1 -> [82, 41, 0].
    result = _clip_and_redistribute(np.array([90.0, 40.0, -7.0]), 0.0, 82.0, target_sum=123.0)
    np.testing.assert_allclose(result, [82.0, 41.0, 0.0])


def test_clip_and_redistribute_proportional_to_free_team_value():
    # clip([85, 10, 5], 0, 82) = [82, 10, 5], sum=97, deficit=100-97=3.
    # Free teams [10, 5] split 3 proportionally to their own value: 10/15 and
    # 5/15 of 3 -> +2.0 and +1.0.
    result = _clip_and_redistribute(np.array([85.0, 10.0, 5.0]), 0.0, 82.0, target_sum=100.0)
    np.testing.assert_allclose(result, [82.0, 12.0, 6.0])


def test_clip_and_redistribute_converges_after_a_second_clipping_pass():
    # First pass pushes a free team's redistributed share past the upper
    # bound (97.83 > 82); the function must re-clip and redistribute again
    # rather than returning an out-of-bounds value or an off-target sum.
    result = _clip_and_redistribute(np.array([10.0, 75.0, 30.0]), 0.0, 82.0, target_sum=150.0)
    assert result.sum() == pytest.approx(150.0)
    assert (result >= 0.0).all() and (result <= 82.0).all()
    assert result[1] == pytest.approx(82.0)  # the team that hit the bound stays pinned there


def test_clip_and_redistribute_gives_up_gracefully_when_target_is_unreachable():
    # With index 0 pinned at its upper-bound clip (82), the other two can't
    # possibly bring the sum down to 30 -- every team ends up pinned at a
    # bound, free.any() goes False, and the function must return its best
    # achievable result instead of looping forever or raising.
    result = _clip_and_redistribute(np.array([85.0, 10.0, 5.0]), 0.0, 82.0, target_sum=30.0)
    assert (result >= 0.0).all() and (result <= 82.0).all()
    assert result.sum() != pytest.approx(30.0)  # confirms this is the "impossible" branch, not a fluke


def test_calibrate_season_predictions_variance_rescale_hand_computed():
    # [21, 41, 61]: mean 41 already equals target_sum/n (123/3), so the shift
    # step is a no-op and the result is pure variance-rescale math:
    # deviations [-20, 0, 20] * (historical_std / raw_std) where raw_std =
    # sqrt(800/3) ~= 16.3299 and historical_std = 10 -> factor ~= 0.61237.
    result = calibrate_season_predictions(
        [21.0, 41.0, 61.0], historical_std=10.0, target_sum=123.0, lower_bound=0.0, upper_bound=82.0,
    )
    factor = 10.0 / np.sqrt(800 / 3)
    expected = np.array([41.0 - 20 * factor, 41.0, 41.0 + 20 * factor])
    np.testing.assert_allclose(result, expected, atol=1e-6)
    assert result.sum() == pytest.approx(123.0)


def test_calibrate_season_predictions_shift_recenters_mean_to_target():
    # Raw predictions already have the target's std (10), so rescale is a
    # no-op -- this isolates the shift step. Raw mean = 30, target mean =
    # 123/3 = 41, so every value should shift by exactly +11.
    raw = [20.0, 30.0, 40.0]  # population std = sqrt((100+0+100)/3) = 10 exactly... verify below
    result = calibrate_season_predictions(raw, historical_std=np.sqrt(200 / 3), target_sum=123.0)
    np.testing.assert_allclose(result, [31.0, 41.0, 51.0], atol=1e-6)


def test_calibrate_season_predictions_sums_to_1230_for_30_teams_with_clipping():
    rng = np.random.default_rng(42)
    # Deliberately wide raw spread (some negative, some past 82) so clipping
    # and redistribution both actually engage, not just the easy no-op path.
    raw = rng.normal(loc=41, scale=40, size=30)
    result = calibrate_season_predictions(raw, historical_std=12.0)
    assert result.sum() == pytest.approx(TOTAL_SEASON_WINS)
    assert (result >= MIN_WINS).all() and (result <= MAX_WINS).all()


def test_calibrate_season_predictions_degenerate_zero_std_does_not_crash():
    raw = [41.0, 41.0, 41.0]  # every raw prediction identical -> raw_std == 0
    result = calibrate_season_predictions(raw, historical_std=10.0, target_sum=123.0)
    np.testing.assert_allclose(result, [41.0, 41.0, 41.0])


def test_recenter_interval_shifts_by_point_delta():
    raw_point = np.array([50.0, 30.0])
    calibrated_point = np.array([55.0, 25.0])  # +5 and -5
    raw_lower = np.array([45.0, 25.0])
    raw_upper = np.array([55.0, 35.0])

    lower, upper = recenter_interval(raw_point, raw_lower, raw_upper, calibrated_point)
    np.testing.assert_allclose(lower, [50.0, 20.0])
    np.testing.assert_allclose(upper, [60.0, 30.0])

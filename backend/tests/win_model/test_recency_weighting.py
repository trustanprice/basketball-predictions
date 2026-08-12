import numpy as np
import pytest

from win_model.model import recency_sample_weight


def test_recency_sample_weight_hand_computed():
    """seasons_ago is anchored to the max season present -- 2020 is the most
    recent here, so it gets weight decay_rate**0 = 1.0, 2018 is two years
    back (decay_rate**2), 2016 is four years back (decay_rate**4)."""
    seasons = np.array([2016, 2018, 2020])
    weight = recency_sample_weight(seasons, decay_rate=0.9)
    assert weight == pytest.approx([0.9 ** 4, 0.9 ** 2, 0.9 ** 0])


def test_recency_sample_weight_decay_rate_one_is_uniform():
    """decay_rate=1.0 must be a real no-op (today's unweighted behavior),
    regardless of how spread out the seasons are."""
    seasons = np.array([2016, 2020, 2025])
    weight = recency_sample_weight(seasons, decay_rate=1.0)
    assert weight == pytest.approx([1.0, 1.0, 1.0])


def test_recency_sample_weight_is_fold_relative_not_absolute():
    """The same relative age (two seasons back from whatever's most recent in
    the slice) must get the same weight whether the slice's own max season is
    2020 or 2026 -- this is what makes the formula safe to reuse unchanged on
    an early fold's smaller training slice instead of leaking the full
    dataset's real max season into it."""
    early_fold = np.array([2016, 2018, 2020])
    later_fold = np.array([2022, 2024, 2026])
    assert recency_sample_weight(early_fold, 0.9)[0] == pytest.approx(
        recency_sample_weight(later_fold, 0.9)[0]
    )


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run (isolated + stacked, each walk-forward-tuning GBM
    once per candidate decay rate) -- slow, but this is the actual validation
    this module's docstring cites."""
    from win_model.recency_weighting import run_experiment

    result = run_experiment()
    assert result["isolated"]["baseline_decay_rate_1_0_mae"] > 0
    assert result["stacked"]["baseline_decay_rate_1_0_mae"] > 0
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding at the time this was written: recency
    # weighting looks like a real win in isolation (vs. plain NUMERIC_FEATURES,
    # decay_rate=0.95: 6.614 -> 6.531) but does NOT improve the decisive,
    # stacked comparison (NUMERIC_FEATURES + Roster_Change) -- decay_rate=1.0
    # (no weighting) wins outright there, 6.418, and every other candidate
    # rate is worse. Same overlap story as Tasks 5-7: whatever recency signal
    # exists overlaps with what Roster_Change already captures. Notably, the
    # real most-recent (2026) backtest fold specifically gets worse under
    # recency weighting in the stacked comparison (4.298 -> 4.949 at
    # decay_rate=0.95), not better -- the opposite of what motivated trying
    # this. Not wired into train.py. If a future change flips either result,
    # the honest thing is to update the finding, not treat this assertion as
    # sacred.
    assert result["improves_mae"] is False

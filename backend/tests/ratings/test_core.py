import numpy as np
import pandas as pd
import pytest

from ratings.core import Component, RatingBreakdown, compute_composite, zscore


def test_zscore_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s)
    assert z.mean() == pytest.approx(0.0, abs=1e-9)
    assert z.std(ddof=0) == pytest.approx(1.0, abs=1e-9)
    # mean=3, population std = sqrt(2) ~= 1.4142
    assert z.iloc[0] == pytest.approx((1.0 - 3.0) / np.sqrt(2), abs=1e-6)


def test_zscore_zero_variance_returns_zeros():
    s = pd.Series([5.0, 5.0, 5.0])
    z = zscore(s)
    assert (z == 0).all()


def test_zscore_all_nan_std_returns_zeros():
    s = pd.Series([np.nan])
    z = zscore(s)
    assert (z == 0).all()


def test_compute_composite_matches_hand_calculation():
    df = pd.DataFrame({
        "id": ["A", "B", "C"],
        "name": ["Alpha", "Beta", "Gamma"],
        "x": [10.0, 20.0, 30.0],
        "y": [3.0, 2.0, 1.0],
    })
    components = [
        Component("X", "x", weight=0.6, higher_is_better=True),
        Component("Y", "y", weight=0.4, higher_is_better=False),
    ]
    scores, breakdowns = compute_composite(df, components, "id", "name")

    x_z = zscore(df["x"])
    y_z = zscore(df["y"])
    expected = x_z * 0.6 + (-y_z) * 0.4

    pd.testing.assert_series_equal(scores, expected, check_names=False)
    assert len(breakdowns) == 3
    assert all(isinstance(b, RatingBreakdown) for b in breakdowns)

    # subject B's breakdown should reproduce its composite score by hand
    b = breakdowns[1]
    assert b.subject_id == "B"
    hand_total = sum(c["contribution"] for c in b.components)
    assert hand_total == pytest.approx(b.composite_score, abs=1e-3)


def test_compute_composite_rejects_weights_not_summing_to_one():
    df = pd.DataFrame({"id": ["A"], "name": ["Alpha"], "x": [1.0]})
    components = [Component("X", "x", weight=0.5)]
    with pytest.raises(ValueError, match="sum to 1.0"):
        compute_composite(df, components, "id", "name")


def test_compute_composite_rejects_empty_dataframe():
    df = pd.DataFrame({"id": [], "name": [], "x": []})
    components = [Component("X", "x", weight=1.0)]
    with pytest.raises(ValueError, match="empty"):
        compute_composite(df, components, "id", "name")


def test_higher_is_better_false_inverts_ranking():
    df = pd.DataFrame({
        "id": ["A", "B"],
        "name": ["Alpha", "Beta"],
        "x": [1.0, 10.0],
    })
    components = [Component("X", "x", weight=1.0, higher_is_better=False)]
    scores, _ = compute_composite(df, components, "id", "name")
    assert scores.loc[0] > scores.loc[1]  # A (lower raw x) scores higher


def test_rating_breakdown_to_dict_shape():
    df = pd.DataFrame({"id": ["A"], "name": ["Alpha"], "x": [1.0], "y": [2.0]})
    components = [
        Component("X", "x", weight=0.5),
        Component("Y", "y", weight=0.5),
    ]
    _, breakdowns = compute_composite(df, components, "id", "name")
    d = breakdowns[0].to_dict()
    assert set(d.keys()) == {"subject_id", "subject_name", "composite_score", "components"}
    assert len(d["components"]) == 2
    for comp in d["components"]:
        assert set(comp.keys()) == {"name", "column", "raw_value", "z_score", "weight", "higher_is_better", "contribution"}

import numpy as np
import pandas as pd
import pytest

from win_model.validation import SeasonWalkForwardSplit


def _toy_frame(seasons, teams_per_season=3, with_nan_target_season=None):
    rows = []
    for s in seasons:
        for t in range(teams_per_season):
            target = np.nan if s == with_nan_target_season else float(s * 10 + t)
            rows.append({"Season": s, "Team": f"team{t}", "y": target})
    return pd.DataFrame(rows)


def test_folds_are_expanding_and_one_season_ahead():
    df = _toy_frame([2016, 2017, 2018, 2019])
    splitter = SeasonWalkForwardSplit()
    folds = list(splitter.split(df, df["y"], groups=df["Season"]))

    assert len(folds) == 3  # test seasons 2017, 2018, 2019

    for train_idx, test_idx in folds:
        train_seasons = set(df.iloc[train_idx]["Season"])
        test_seasons = set(df.iloc[test_idx]["Season"])
        assert len(test_seasons) == 1
        (test_season,) = test_seasons
        assert max(train_seasons) == test_season - 1
        assert max(train_seasons) < test_season  # no future data in training


def test_no_row_ever_appears_in_both_train_and_test_of_a_fold():
    df = _toy_frame([2016, 2017, 2018, 2019, 2020])
    splitter = SeasonWalkForwardSplit()
    for train_idx, test_idx in splitter.split(df, df["y"], groups=df["Season"]):
        assert set(train_idx).isdisjoint(set(test_idx))


def test_rows_with_null_target_are_excluded_from_train_and_test():
    df = _toy_frame([2016, 2017, 2018], with_nan_target_season=2018)
    splitter = SeasonWalkForwardSplit()
    folds = list(splitter.split(df, df["y"], groups=df["Season"]))

    # Only one evaluable fold: train=2016, test=2017 (2018 has no known target,
    # so it can never appear as a test fold; and appearing only as a *later*
    # potential train season doesn't matter since there's no season after it).
    assert len(folds) == 1
    train_idx, test_idx = folds[0]
    assert set(df.iloc[test_idx]["Season"]) == {2017}
    assert 2018 not in set(df.iloc[train_idx]["Season"])


def test_min_train_seasons_delays_the_first_fold():
    df = _toy_frame([2016, 2017, 2018, 2019])
    splitter = SeasonWalkForwardSplit(min_train_seasons=2)
    folds = list(splitter.split(df, df["y"], groups=df["Season"]))
    assert len(folds) == 2  # test seasons 2018, 2019 only
    first_train_idx, first_test_idx = folds[0]
    assert set(df.iloc[first_train_idx]["Season"]) == {2016, 2017}


def test_get_n_splits_matches_split_count():
    df = _toy_frame([2016, 2017, 2018, 2019, 2020])
    splitter = SeasonWalkForwardSplit()
    assert splitter.get_n_splits(df, df["y"], groups=df["Season"]) == len(
        list(splitter.split(df, df["y"], groups=df["Season"]))
    )


def test_row_order_does_not_affect_fold_membership():
    df = _toy_frame([2016, 2017, 2018, 2019]).sample(frac=1, random_state=7).reset_index(drop=True)
    splitter = SeasonWalkForwardSplit()
    folds = list(splitter.split(df, df["y"], groups=df["Season"]))
    assert len(folds) == 3
    for train_idx, test_idx in folds:
        assert max(df.iloc[train_idx]["Season"]) < min(df.iloc[test_idx]["Season"])


def test_requires_groups():
    df = _toy_frame([2016, 2017])
    with pytest.raises(ValueError):
        list(SeasonWalkForwardSplit().split(df, df["y"], groups=None))


def test_invalid_min_train_seasons():
    with pytest.raises(ValueError):
        SeasonWalkForwardSplit(min_train_seasons=0)


def test_too_few_seasons_yields_no_folds():
    df = _toy_frame([2016])
    splitter = SeasonWalkForwardSplit()
    assert list(splitter.split(df, df["y"], groups=df["Season"])) == []


def test_plugs_into_gridsearchcv():
    """Integration check: the splitter works as a real `cv=` object, and `groups=`
    passed to .fit() reaches it (this is the actual usage pattern in model.py)."""
    from sklearn.dummy import DummyRegressor
    from sklearn.model_selection import GridSearchCV

    df = _toy_frame([2016, 2017, 2018, 2019, 2020], teams_per_season=5)
    X = df[["Season"]]
    y = df["y"]

    search = GridSearchCV(
        DummyRegressor(),
        param_grid={"strategy": ["mean", "median"]},
        cv=SeasonWalkForwardSplit(),
        scoring="neg_mean_absolute_error",
    )
    search.fit(X, y, groups=df["Season"])
    assert search.best_score_ is not None
    assert np.isfinite(search.best_score_)

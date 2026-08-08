"""Season-grouped walk-forward cross-validation for the win model.

Random k-fold CV leaks future seasons into training for a time-dependent process
(team-season rows aren't exchangeable across years). This splitter trains on every
season <= N and validates on season N+1, rolling forward one season at a time —
sklearn's TimeSeriesSplit doesn't apply directly since rows are season-grouped
(~30 teams per season) rather than a single ordered sequence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class SeasonWalkForwardSplit:
    """Walk-forward CV splitter, grouped by a season label.

    Fold k trains on all rows whose season is <= the k-th smallest season that has
    at least one later season available, and validates on the rows of the very next
    season. Compatible with sklearn's ``cv=`` interface: pass ``groups=<season array>``
    to ``.fit()`` (GridSearchCV, cross_val_score, etc. forward ``groups`` straight to
    ``split()``).

    Parameters
    ----------
    min_train_seasons : int
        Minimum number of distinct seasons required in a fold's training set before
        it's eligible to be validated against. Defaults to 1 (train on whatever
        earliest season exists, validate on the next one).
    """

    def __init__(self, min_train_seasons: int = 1):
        if min_train_seasons < 1:
            raise ValueError("min_train_seasons must be >= 1")
        self.min_train_seasons = min_train_seasons

    def split(self, X, y=None, groups=None):
        """Yield (train_idx, test_idx) index arrays, one pair per validated season.

        ``groups`` must be an array-like of season labels aligned to X's rows
        (integer years, e.g. 2016, 2017, ...). Rows with a null target (``y``) are
        excluded from both train and test — a season held out because its outcome
        isn't known yet can't be scored, and shouldn't silently poison training.
        """
        if groups is None:
            raise ValueError(
                "SeasonWalkForwardSplit requires groups=<season array> — "
                "pass it to .fit(X, y, groups=season_values)."
            )

        seasons = pd.Series(np.asarray(groups)).reset_index(drop=True)
        n = len(seasons)

        if y is not None:
            y_arr = pd.Series(np.asarray(y)).reset_index(drop=True)
            has_target = y_arr.notna().to_numpy()
        else:
            has_target = np.ones(n, dtype=bool)

        unique_seasons = np.sort(seasons.unique())
        if len(unique_seasons) <= self.min_train_seasons:
            return  # not enough distinct seasons to form a single fold

        for i in range(self.min_train_seasons, len(unique_seasons)):
            train_season_cutoff = unique_seasons[i - 1]
            test_season = unique_seasons[i]

            train_mask = (seasons.to_numpy() <= train_season_cutoff) & has_target
            test_mask = (seasons.to_numpy() == test_season) & has_target

            train_idx = np.flatnonzero(train_mask)
            test_idx = np.flatnonzero(test_mask)

            if len(train_idx) == 0 or len(test_idx) == 0:
                continue

            yield train_idx, test_idx

    def get_n_splits(self, X=None, y=None, groups=None):
        if groups is None:
            raise ValueError("SeasonWalkForwardSplit.get_n_splits requires groups=<season array>")
        return sum(1 for _ in self.split(X, y, groups))

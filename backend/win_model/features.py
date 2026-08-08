"""Feature list and model-table preparation for the win model.

`master_df.csv` has ~78 duplicate rows per team-season (one per opponent, inherited
from the schedule/SOS join) and a stored `NWins` column that despite its name and
the old notebook's comments is NOT next-season wins — it's that same row's own `W`,
with the most recent season blanked out. Training on it as-is means using in-season
stats (Home_W, Pre-ASG splits, actual shooting/plus-minus) to predict that same
season's own win total: near-tautological for historical rows, and at real
prediction time for an unplayed season those in-season columns don't exist yet and
get mean-imputed, dragging every team toward the league average regardless of the
downstream regressor. `prepare_model_table` fixes both: it dedupes to one row per
team-season, and builds a real target (`Next_W`) via an explicit groupby-shift, so
every feature is something that's genuinely known at prediction time (last
season's completed stats projecting next season).
"""

from __future__ import annotations

import pandas as pd

# Same feature set the original ElasticNet stage used. Kept as-is — Phase 1 fixes
# validation methodology and model choice, not feature engineering.
NUMERIC_FEATURES = [
    "GP", "W", "L", "WIN%", "Min", "PTS", "FGM", "FGA", "FG%",
    "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "OREB", "DREB",
    "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD",
    "PLUS_MINUS", "Home_W", "Home_L", "Road_W", "Road_L",
    "E_W", "E_L", "W_W", "W_L", "Pre-ASG_W", "Pre-ASG_L",
    "Post-ASG_W", "Post-ASG_L", "SOS", "Yw/Franch", "YOverall",
    "CareerW", "CareerL", "CareerW%", "FirstRoundPicks", "SecondRoundPicks",
    "Coach_Count", "Payroll",
    "avg_age", "avg_pts_top10", "avg_production_score", "injury_rate",
]

# "Season" was previously one-hot encoded as a categorical feature. Under walk-forward
# validation the test season is unseen by construction in every fold, so that column
# is provably all-zero at evaluation time — dead weight, dropped rather than carried
# forward as a feature. Kept as a plain (non-modeled) column for grouping/joining.
CATEGORICAL_FEATURES: list[str] = []

TARGET_COLUMN = "Next_W"

ID_COLUMNS = ["Season", "Team"]


def prepare_model_table(master_df: pd.DataFrame) -> pd.DataFrame:
    """Dedupe to one row per (Season, Team) and attach the true next-season target.

    Returns columns: Season, Team, W, Next_W, + NUMERIC_FEATURES/CATEGORICAL_FEATURES.
    Rows for the most recent season have Next_W = NaN (that season's real outcome
    hasn't happened yet) — callers use those as the live forecast row, and exclude
    them from training/evaluation.
    """
    df = master_df.drop_duplicates(subset=ID_COLUMNS).copy()
    df = df.sort_values(["Team", "Season"]).reset_index(drop=True)
    df[TARGET_COLUMN] = df.groupby("Team")["W"].shift(-1)

    keep_cols = list(dict.fromkeys(ID_COLUMNS + ["W", TARGET_COLUMN] + NUMERIC_FEATURES + CATEGORICAL_FEATURES))
    missing = [c for c in keep_cols if c not in df.columns]
    if missing:
        raise ValueError(f"master_df is missing expected columns: {missing}")

    return df[keep_cols].sort_values(ID_COLUMNS).reset_index(drop=True)

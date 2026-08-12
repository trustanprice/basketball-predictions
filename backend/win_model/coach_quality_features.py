"""backend/win_model/coach_quality_features.py

Hypothesis test: coaching_eval.py's wins-above-expectation (WAE) is currently
descriptive-only (coaching page, never fed back into win_model). Does a
team-level feature -- the team's current coach's own career-average WAE --
improve walk-forward MAE?

For historical row Season=N (features describe season N, predicting N+1):
"current coach" = whoever master_df.csv says coached team T in season N (now
that this is correct -- see the real bug this task caught below). Their
"career average" is computed across every (Coach, Season<=N) row on record for
them, any team -- includes season N itself (already realized/known by the
time row N is used to predict N+1, so this isn't leakage the way including
N+1 would be; a coach's own just-completed season is exactly the kind of
thing "current coach's career average" should reflect). Requires at least
MIN_TOTAL_SEASONS_FOR_ADJUSTMENT (reusing ratings/player_development.py's
exact constant and reasoning, not a new arbitrary threshold) qualifying
seasons before trusting the average -- a first-year coach (their only row is
season N itself, 1 total season) gets no adjustment, flagged, not guessed.

A real, unrelated bug surfaced while building this and had to be fixed first:
four teams' committed Season=2026 (real, completed 2025-26) "Coach" value was
actually their incoming 2026-27 hire (Milwaukee/New Orleans/New York/Phoenix --
Yw/Franch had reset to 1 with no in-season-continuity evidence, unlike the
four legitimate in-season 2024-25 hires that correctly carried into 2025-26).
Fixed in data/raw/team-stats/coach.csv and master_df.csv (Doc Rivers/Willie
Green/Tom Thibodeau/Mike Budenholzer restored as who actually coached the real
2025-26 season) before this feature was built on top of it -- re-ran train.py
after, confirmed the win model's own predictions are unaffected (Coach's name
isn't itself a NUMERIC_FEATURES input, only the unchanged Coach_Count is).

The forecast row (Season=2026, predicting the still-unplayed 2026-27 season)
needs the *actual* 2026-27 coach, which is a genuinely different question from
"who coached the real 2025-26 season" the historical rows use -- sourced from
a live nba_api roster fetch (CommonTeamRoster's coaches result set), not
merged into the historical coach.csv (that file is "one row per real completed
season," and 2026-27 hasn't happened). Three teams (Chicago Bulls/Dallas
Mavericks/Orlando Magic) had no head-coach tag in that live fetch at all;
absent evidence of a 2026-27 change, they default to their real 2025-26 coach
continuing -- same "no evidence of a hire, most teams don't change coaches
every year" default already used for the other 23 unchanged teams, not a
guess at a specific new name.

Run manually: python -m backend.win_model.coach_quality_features
"""

from __future__ import annotations

import pandas as pd

from .data_loader import MASTER_DF_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward

try:
    from ..ratings import coaching_eval
    from ..ratings.player_development import MIN_TOTAL_SEASONS_FOR_ADJUSTMENT
except ImportError:
    from ratings import coaching_eval
    from ratings.player_development import MIN_TOTAL_SEASONS_FOR_ADJUSTMENT

COACH_QUALITY_COLUMN = "Coach_Career_WAE"

# The real 2026-27 coach per team, as of the live nba_api CommonTeamRoster
# fetch this session already did (see backend/AGENTS.md's coach.csv history
# for the three unresolved teams). Kept here, not in coach.csv, since that
# file is "one row per real completed season" and 2026-27 hasn't happened --
# this dict is forecast-row-only context, same separation roster_projection.json
# has from the historical CSVs.
CURRENT_SEASON_COACHES = {
    "Atlanta Hawks": "Quin Snyder", "Boston Celtics": "Joe Mazzulla",
    "Brooklyn Nets": "Jordi Fernandez", "Charlotte Hornets": "Charles Lee",
    "Chicago Bulls": "Billy Donovan",  # no live tag; defaults to real 2025-26 coach continuing
    "Cleveland Cavaliers": "Kenny Atkinson", "Dallas Mavericks": "Jason Kidd",  # same default
    "Denver Nuggets": "David Adelman", "Detroit Pistons": "J.B. Bickerstaff",
    "Golden State Warriors": "Steve Kerr", "Houston Rockets": "Ime Udoka",
    "Indiana Pacers": "Rick Carlisle", "Los Angeles Clippers": "Tyronn Lue",
    "Los Angeles Lakers": "JJ Redick", "Memphis Grizzlies": "Tuomas Iisalo",
    "Miami Heat": "Erik Spoelstra", "Milwaukee Bucks": "Taylor Jenkins",
    "Minnesota Timberwolves": "Chris Finch", "New Orleans Pelicans": "Jamahl Mosley",
    "New York Knicks": "Mike Brown", "Oklahoma City Thunder": "Mark Daigneault",
    "Orlando Magic": "Jamahl Mosley",  # no live tag; defaults to real 2025-26 coach continuing
    "Philadelphia 76ers": "Nick Nurse", "Phoenix Suns": "Jordan Ott",
    "Portland Trail Blazers": "Chauncey Billups", "Sacramento Kings": "Doug Christie",
    "San Antonio Spurs": "Mitch Johnson", "Toronto Raptors": "Darko Rajakovic",
    "Utah Jazz": "Will Hardy", "Washington Wizards": "Brian Keefe",
}


def _team_season_coach_map(master_df: pd.DataFrame) -> pd.DataFrame:
    return master_df.drop_duplicates(subset=["Season", "Team"])[["Season", "Team", "Coach"]]


def _coach_wae_table(master_df: pd.DataFrame) -> pd.DataFrame:
    """One row per (Coach, Season, Team) with wins_above_expectation, across
    every season on record -- reuses coaching_eval.coach_wins_above_expectation()
    directly, not a second WAE computation."""
    input_df = master_df.drop_duplicates(subset=["Season", "Team"])[list(coaching_eval.TEAM_SEASON_INPUT_COLUMNS)]
    return coaching_eval.coach_wins_above_expectation(input_df.reset_index(drop=True))


def _career_avg_wae(coach: str, as_of_season: int, wae_table: pd.DataFrame) -> float | None:
    """Coach's own average wins_above_expectation across every (any-team)
    season on record with Season <= as_of_season -- None if fewer than
    MIN_TOTAL_SEASONS_FOR_ADJUSTMENT qualifying seasons exist."""
    prior = wae_table[(wae_table["Coach"] == coach) & (wae_table["Season"] <= as_of_season)]
    if len(prior) < MIN_TOTAL_SEASONS_FOR_ADJUSTMENT:
        return None
    return float(prior["wins_above_expectation"].mean())


def build_coach_quality_features(master_df_path=None) -> pd.DataFrame:
    """Returns one row per (Season, Team) with COACH_QUALITY_COLUMN, for
    exactly the historical rows compare_models_walk_forward trains/evaluates on."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    coach_map = _team_season_coach_map(master_df)
    wae_table = _coach_wae_table(master_df)

    merged = trainable[["Season", "Team"]].merge(coach_map, on=["Season", "Team"], how="left")
    rows = []
    for season, team, coach in zip(merged["Season"], merged["Team"], merged["Coach"]):
        value = _career_avg_wae(coach, int(season), wae_table) if pd.notna(coach) else None
        rows.append({"Season": season, "Team": team, COACH_QUALITY_COLUMN: value})
    return pd.DataFrame(rows)


def forecast_coach_quality(team: str, most_recent_season: int, master_df_path=None) -> float | None:
    """Forecast-row version: the team's real 2026-27 coach's career-average
    WAE through the most recently completed real season (see
    CURRENT_SEASON_COACHES for why this can't just reuse master_df's own
    Coach column, which describes 2025-26, not 2026-27)."""
    coach = CURRENT_SEASON_COACHES.get(team)
    if coach is None:
        return None
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    wae_table = _coach_wae_table(master_df)
    return _career_avg_wae(coach, most_recent_season, wae_table)


def run_experiment(master_df_path=None) -> dict:
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    quality = build_coach_quality_features(master_df_path)
    merged = trainable.merge(quality, on=["Season", "Team"], how="left")
    n_missing = merged[COACH_QUALITY_COLUMN].isna().sum()
    merged[COACH_QUALITY_COLUMN] = merged[COACH_QUALITY_COLUMN].fillna(0.0)

    y = merged[TARGET_COLUMN]
    groups = merged["Season"]

    baseline_X = merged[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    augmented_numeric = NUMERIC_FEATURES + [COACH_QUALITY_COLUMN]
    augmented_X = merged[augmented_numeric + CATEGORICAL_FEATURES]

    baseline = compare_models_walk_forward(baseline_X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    augmented = compare_models_walk_forward(augmented_X, y, groups, augmented_numeric, CATEGORICAL_FEATURES)

    baseline_mae = min(baseline.knn_walk_forward_mae, baseline.gbm_walk_forward_mae)
    augmented_mae = min(augmented.knn_walk_forward_mae, augmented.gbm_walk_forward_mae)

    return {
        "hypothesis": (
            "The team's current coach's own career-average wins-above-expectation "
            "(coaching_eval.py, currently descriptive-only) improves walk-forward MAE "
            "as a win_model feature."
        ),
        "baseline_walk_forward_mae": round(float(baseline_mae), 3),
        "baseline_winner": baseline.winner,
        "augmented_walk_forward_mae": round(float(augmented_mae), 3),
        "augmented_winner": augmented.winner,
        "improves_mae": bool(augmented_mae < baseline_mae),
        "n_rows": int(len(merged)),
        "n_missing_coach_data": int(n_missing),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Baseline MAE: {result['baseline_walk_forward_mae']} ({result['baseline_winner']})")
    print(f"Augmented MAE: {result['augmented_walk_forward_mae']} ({result['augmented_winner']})")
    print(f"Coach-quality feature {verdict} walk-forward MAE.")
    print(f"(no qualifying coach track record for {result['n_missing_coach_data']} of {result['n_rows']} rows)")

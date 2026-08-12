"""backend/win_model/roster_change_features.py

Hypothesis test (prompted by the first real out-of-season backtest, Season=2026 —
see model_metadata.json's feature_experiments once wired in): does a feature
capturing season-over-season roster-talent change improve walk-forward MAE, on
top of the existing team-level current-season aggregates?

For historical row Season=N (features describe season N, target is season N+1's
wins), "roster change" means: who left the N roster, who joined it for N+1,
weighted by production. Deliberately uses each arriving player's own **prior**
(season-N, wherever they played -- possibly a different team, possibly nowhere if
they're a rookie) production as the weight, not their actual season-N+1 output --
using N+1 performance would leak outcome information from the season being
predicted into a feature describing the season before it, the same "no
same-season leakage" discipline as TARGET_COLUMN's Next_W shift and SOS's
prior-season-only construction. A rookie or two-way call-up with no prior-season
line anywhere contributes 0 (unknown talent, not fabricated).

Sourced from the local per-season player files (data/raw/player-stats/{season}-
player-stats.csv, 2016-2026, all already on disk) rather than a fresh nba_api
roster fetch -- same choice player_projection_features.py already made for its
retrospective historical test, for the same reason (avoids ~500+ calls to
re-derive data already sitting on disk from Basketball-Reference/nba_api scrapes
run earlier this session).

Run manually: python -m backend.win_model.roster_change_features
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from .data_loader import MASTER_DF_FILE, PLAYER_STATS_DIR
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import compare_models_walk_forward
from .utils import team_map

ROSTER_CHANGE_COLUMN = "Roster_Change"


def _normalize_name(name: str) -> str:
    """Strip accents/punctuation so Basketball-Reference and nba_api spellings
    of the same player ('Nikola Jokić' vs 'Nikola Jokic') match as one player,
    not a false departure+arrival pair."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.strip().lower().replace(".", "").replace("'", "")


def _load_season_panel(season: int) -> pd.DataFrame:
    """One row per player who appeared for a real NBA team in `season`
    (2TM/3TM/4TM combined-team rows dropped, same as data_loader.load_players),
    with a normalized name and total-season point production (PTS/game * GP,
    the same production proxy the rest of this feature uses)."""
    path = PLAYER_STATS_DIR / f"{season}-player-stats.csv"
    if not path.exists():
        return pd.DataFrame(columns=["norm_name", "Team_full", "total_pts"])
    df = pd.read_csv(path)
    df = df[~df["Team"].isin(["2TM", "3TM", "4TM"])].copy()
    df["Team_full"] = df["Team"].map(team_map).fillna(df["Team"])
    df["norm_name"] = df["Player"].map(_normalize_name)
    df["total_pts"] = df["PTS"] * df["G"]
    return df[["norm_name", "Team_full", "total_pts"]]


def _roster_change_for_team_season(season: int, team: str, panels: dict[int, pd.DataFrame]) -> float | None:
    """Roster_Change for row (season, team): arriving players' prior-season
    production (wherever they played, 0 if none on record) minus departing
    players' season-`season` production. None if either season's panel is
    unavailable (first season on record has no prior panel to diff against).
    """
    this_season = panels.get(season)
    next_season = panels.get(season + 1)
    if this_season is None or next_season is None or this_season.empty or next_season.empty:
        return None

    this_roster = this_season[this_season["Team_full"] == team]
    next_roster = next_season[next_season["Team_full"] == team]
    if this_roster.empty or next_roster.empty:
        return None

    this_names = set(this_roster["norm_name"])
    next_names = set(next_roster["norm_name"])
    departed_names = this_names - next_names
    arrived_names = next_names - this_names

    departed_pts = this_roster[this_roster["norm_name"].isin(departed_names)]["total_pts"].sum()

    # Arriving players' weight is their OWN prior-season production, wherever
    # they played it -- not their new team's, and not their season+1 output
    # (see module docstring on leakage). A player absent from the prior
    # season's panel entirely (rookie, or a two-way/G-League call-up with no
    # top-line stat row) contributes 0.
    prior_panel = panels.get(season)
    arrived_pts = 0.0
    if prior_panel is not None and not prior_panel.empty:
        prior_by_name = prior_panel.groupby("norm_name")["total_pts"].sum()
        arrived_pts = sum(float(prior_by_name.get(name, 0.0)) for name in arrived_names)

    return float(arrived_pts - departed_pts)


def forecast_roster_change(
    team: str, most_recent_season: int, roster_projection_path: Path | str,
) -> float | None:
    """Roster_Change for the live forecast row: same "arrived minus departed,
    weighted by each player's own last-known real production" definition as
    the historical version above, just sourced from
    backend/ratings/refresh_roster_projection.py's real current-roster fetch
    (see backend/AGENTS.md) instead of a future season's per-season file,
    which doesn't exist yet for an unplayed season. `most_recent_season` is
    the last completed season on record (e.g. 2026 for the 2025-26 season) --
    the "departed" side comes from that season's real roster.

    Deliberately still uses each arriving player's *own* last-known
    production as the weight, not their team's/player_development's
    projected_pts for the upcoming season -- keeps the feature's meaning
    identical between training and prediction time rather than mixing
    "realized last season" (historical rows) with "projected next season"
    (forecast row) versions of the same number.
    """
    import json

    path = Path(roster_projection_path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    player_detail = payload.get("player_detail", {})
    if team not in player_detail:
        return None

    current_panel = _load_season_panel(most_recent_season)
    if current_panel.empty:
        return None
    this_roster = current_panel[current_panel["Team_full"] == team]
    if this_roster.empty:
        return None

    projected_names = {_normalize_name(p["player_name"]) for p in player_detail[team]}
    this_names = set(this_roster["norm_name"])
    departed_names = this_names - projected_names
    arrived_names = projected_names - this_names

    departed_pts = this_roster[this_roster["norm_name"].isin(departed_names)]["total_pts"].sum()

    prior_by_name = current_panel.groupby("norm_name")["total_pts"].sum()
    arrived_pts = sum(float(prior_by_name.get(name, 0.0)) for name in arrived_names)

    return float(arrived_pts - departed_pts)


def build_roster_change_features(master_df_path=None) -> pd.DataFrame:
    """Returns one row per (Season, Team) with ROSTER_CHANGE_COLUMN, for
    exactly the historical rows compare_models_walk_forward trains/evaluates on."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    seasons_needed = set(trainable["Season"].unique()) | {s + 1 for s in trainable["Season"].unique()}
    panels = {s: _load_season_panel(int(s)) for s in seasons_needed}

    rows = []
    for season, team in zip(trainable["Season"], trainable["Team"]):
        change = _roster_change_for_team_season(int(season), team, panels)
        rows.append({"Season": season, "Team": team, ROSTER_CHANGE_COLUMN: change})
    return pd.DataFrame(rows)


def run_experiment(master_df_path=None) -> dict:
    """Honest baseline-vs-augmented walk-forward comparison, same shape as
    player_projection_features.run_experiment()."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)
    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)

    changes = build_roster_change_features(master_df_path)
    merged = trainable.merge(changes, on=["Season", "Team"], how="left")
    # A team-season with no computable change (missing panel data, e.g. the
    # very first season on record) falls back to 0 -- "no measured change"
    # is a defensible neutral value, and keeps every row usable rather than
    # dropping teams the way an unfilled NaN would going into the model.
    merged[ROSTER_CHANGE_COLUMN] = merged[ROSTER_CHANGE_COLUMN].fillna(0.0)

    y = merged[TARGET_COLUMN]
    groups = merged["Season"]

    baseline_X = merged[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    augmented_numeric = NUMERIC_FEATURES + [ROSTER_CHANGE_COLUMN]
    augmented_X = merged[augmented_numeric + CATEGORICAL_FEATURES]

    baseline = compare_models_walk_forward(baseline_X, y, groups, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    augmented = compare_models_walk_forward(augmented_X, y, groups, augmented_numeric, CATEGORICAL_FEATURES)

    baseline_mae = min(baseline.knn_walk_forward_mae, baseline.gbm_walk_forward_mae)
    augmented_mae = min(augmented.knn_walk_forward_mae, augmented.gbm_walk_forward_mae)

    return {
        "hypothesis": (
            "Feeding season-over-season roster-talent change (arriving players' "
            "prior production minus departing players' production) into every "
            "historical training row improves walk-forward MAE."
        ),
        "baseline_walk_forward_mae": round(float(baseline_mae), 3),
        "baseline_winner": baseline.winner,
        "augmented_walk_forward_mae": round(float(augmented_mae), 3),
        "augmented_winner": augmented.winner,
        "improves_mae": bool(augmented_mae < baseline_mae),
        "n_rows": int(len(merged)),
    }


if __name__ == "__main__":
    result = run_experiment()
    verdict = "IMPROVES" if result["improves_mae"] else "does NOT improve"
    print(f"Baseline MAE: {result['baseline_walk_forward_mae']} ({result['baseline_winner']})")
    print(f"Augmented MAE: {result['augmented_walk_forward_mae']} ({result['augmented_winner']})")
    print(f"Roster-change-magnitude feature {verdict} walk-forward MAE.")

"""backend/ratings/player_development.py

Empirical (not fitted-ML) player aging curve, built from real player-career
history via nba_api's PlayerCareerStats -- and the roster -> team-talent
projection this feeds into win_model's forecast row (see
backend/win_model/train.py and backend/AGENTS.md's roster-projection section).

Everything here must be reproducible by hand, the same standard as
ratings/core.py: "a player at age X historically sees a median change of Y% in
scoring rate the following season" -- not "a model predicts." No fitted
regression, no black box.

This module never calls live_client itself. Callers (refresh_roster_projection.py)
fetch the raw CommonTeamRoster / PlayerCareerStats data and hand dataframes to
the functions here -- the same fetch/compute separation coaching_eval.py and
player_power_rankings.py use relative to their own live data sources.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .coaching_eval import compute_team_season_talent

# Minimum games played in *both* seasons of a year-over-year transition for it
# to count toward the aging curve -- a two-game stretch at some extreme per-36
# rate is noise, not signal about aging.
MIN_GP_FOR_CURVE = 10

# An age bin needs at least this many real transitions before its median is
# trusted. Ages with fewer observations get no curve value -- a player who
# lands there is treated the same as one with too little personal history
# (see MIN_TOTAL_SEASONS_FOR_ADJUSTMENT): unadjusted, flagged, not guessed.
MIN_OBSERVATIONS_PER_AGE_BIN = 5

# "Players with 0-1 prior seasons: no adjustment applied" -- prior seasons =
# recorded seasons before the most recent one, so 0-1 prior means <=2 total
# seasons on record. Not enough personal track record to say a trend is real;
# carry forward their actual last-season numbers unadjusted rather than
# fabricate one from a league-wide curve they have little basis to match.
MIN_TOTAL_SEASONS_FOR_ADJUSTMENT = 3


def _pts_per36(pts_per_game: pd.Series, min_per_game: pd.Series) -> np.ndarray:
    """PTS-per-36, from PerGame-mode career stats (PlayerCareerStats is always
    fetched with per_mode36="PerGame" -- see live_client/endpoints/stats/career_stats.py).
    0 where minutes are 0 rather than dividing by zero."""
    pts = pts_per_game.to_numpy(dtype=float)
    minutes = min_per_game.to_numpy(dtype=float)
    return np.divide(pts, minutes, out=np.zeros_like(pts), where=minutes > 0) * 36


def build_aging_curve(career_histories: list[pd.DataFrame]) -> pd.DataFrame:
    """The empirical aging curve: for every real season-to-season transition
    across `career_histories`, the % change in PTS-per-36, binned by the
    player's age at the *start* of that transition and reduced to a median.

    Parameters
    ----------
    career_histories : one DataFrame per player, each the raw
        `PlayerCareerStats.fetch().to_dataframe()` output -- one row per
        season, columns include SEASON_ID, PLAYER_AGE, GP, MIN, PTS.

    Returns
    -------
    DataFrame indexed by integer age, columns `n_observations` and
    `median_pct_change`. Ages with fewer than MIN_OBSERVATIONS_PER_AGE_BIN
    real transitions are dropped entirely -- see project_player_next_season
    for how a player landing on a missing age is handled.
    """
    transitions = []
    for career in career_histories:
        if career is None or len(career) < 2:
            continue
        c = career.sort_values("SEASON_ID").reset_index(drop=True)
        c = c[c["GP"] >= MIN_GP_FOR_CURVE].reset_index(drop=True)
        if len(c) < 2:
            continue
        per36 = _pts_per36(c["PTS"], c["MIN"])
        ages = c["PLAYER_AGE"].to_numpy(dtype=float)
        for i in range(len(c) - 1):
            start_per36, end_per36, start_age = per36[i], per36[i + 1], ages[i]
            if start_per36 <= 0 or np.isnan(start_age):
                continue
            transitions.append({
                "age": int(round(start_age)),
                "pct_change": (end_per36 - start_per36) / start_per36,
            })

    if not transitions:
        return pd.DataFrame(columns=["n_observations", "median_pct_change"]).rename_axis("age")

    t = pd.DataFrame(transitions)
    curve = t.groupby("age")["pct_change"].agg(n_observations="count", median_pct_change="median")
    return curve[curve["n_observations"] >= MIN_OBSERVATIONS_PER_AGE_BIN]


def project_player_next_season(career_df: pd.DataFrame, aging_curve: pd.DataFrame) -> dict:
    """Projects one player's next-season per-game stats from their real most
    recent season, adjusted by the league-wide aging curve for their age.

    `career_df`: one player's raw PlayerCareerStats dataframe (>=1 row).

    Returns a dict: player_id, last_season_id, projected_age, projected_min,
    projected_pts, development_adjustment_applied, development_pct_change,
    development_note. `development_note` is written to be shown directly in
    a methodology panel, not just logged.
    """
    if career_df is None or len(career_df) == 0:
        raise ValueError("project_player_next_season needs at least one season of history")

    c = career_df.sort_values("SEASON_ID").reset_index(drop=True)
    last = c.iloc[-1]
    last_age = last["PLAYER_AGE"]
    last_min = float(last["MIN"]) if pd.notna(last["MIN"]) else 0.0
    last_pts = float(last["PTS"]) if pd.notna(last["PTS"]) else 0.0
    last_per36 = (last_pts / last_min * 36) if last_min > 0 else 0.0

    n_total_seasons = len(c)
    age_bin = int(round(last_age)) if pd.notna(last_age) else None

    if n_total_seasons < MIN_TOTAL_SEASONS_FOR_ADJUSTMENT:
        applied, pct_change = False, None
        note = (
            f"Only {n_total_seasons} recorded season(s) -- not enough personal history "
            "for a trend. Using actual most-recent-season stats unadjusted."
        )
    elif age_bin is None or age_bin not in aging_curve.index:
        applied, pct_change = False, None
        note = (
            f"No league-wide aging-curve data for age {age_bin}. "
            "Using actual most-recent-season stats unadjusted."
        )
    else:
        applied = True
        pct_change = float(aging_curve.loc[age_bin, "median_pct_change"])
        n_obs = int(aging_curve.loc[age_bin, "n_observations"])
        note = (
            f"Age-{age_bin} players historically see a median {pct_change:+.1%} change "
            f"in scoring rate the following season (n={n_obs} real transitions)."
        )

    projected_per36 = last_per36 * (1 + pct_change) if applied else last_per36
    # Playing time is carried forward unchanged -- projecting minutes is a
    # separate problem this curve doesn't attempt (it's built purely from
    # scoring-rate transitions, not usage/role changes).
    projected_min = last_min
    projected_pts = projected_per36 * projected_min / 36

    return {
        "player_id": last.get("PLAYER_ID"),
        "last_season_id": last.get("SEASON_ID"),
        "projected_age": (float(last_age) + 1) if pd.notna(last_age) else None,
        "projected_min": projected_min,
        "projected_pts": projected_pts,
        "development_adjustment_applied": applied,
        "development_pct_change": pct_change,
        "development_note": note,
    }


def project_team_talent_features(projected_players: pd.DataFrame) -> dict:
    """Aggregates one team's projected per-player stats to the same
    team-season feature shape backend/win_model/data_loader.py's
    calculate_player_features() produces from real historical data --
    avg_age, avg_pts_top10, avg_production_score -- so these values plug
    directly into win_model's existing feature columns rather than requiring
    a schema change (see backend/win_model/train.py).

    All three are restricted to the top 10 players by projected_pts, not the
    full roster (15+ players once bench depth is included) -- matching
    calculate_player_features()'s historical rows, whose source data only
    ever carried ~10 players per team-season, making its plain `.mean()`
    over the whole group implicitly top-10-only already. Averaging the full
    projected roster instead would systematically pull avg_age/
    avg_production_score toward bench-heavy values a historical row never
    had, for no reason other than the live pipeline happening to see the
    deeper roster the historical curation didn't.

    `projected_players`: one row per roster player, the concatenated output
    of project_player_next_season() for that team.
    """
    if projected_players.empty:
        raise ValueError("project_team_talent_features got an empty roster")

    top10 = projected_players.sort_values("projected_pts", ascending=False).head(10)
    prod_score = top10["projected_pts"] / top10["projected_min"].replace(0, 1)

    return {
        "avg_age": float(top10["projected_age"].mean()),
        "avg_pts_top10": float(top10["projected_pts"].mean()),
        "avg_production_score": float(prod_score.mean()),
        "n_players": int(len(projected_players)),
        "n_players_adjusted": int(projected_players["development_adjustment_applied"].sum()),
        "n_players_unadjusted": int((~projected_players["development_adjustment_applied"]).sum()),
    }


# ==========================================================================
# Archetype-segmented multi-stat curves (Players page "Projected 26-27
# Leaders"). Same empirical median-%-change-by-age-bin methodology as
# build_aging_curve/project_player_next_season above (kept untouched --
# win_model's roster-projection pipeline depends on those exact functions),
# extended two ways: (1) more than one stat (the offense/defense composites
# in player_power_rankings.py need TS%, usage%, AST%, TOV%, STL+BLK rate,
# DREB%, and defensive rating -- none of which is "points"), and
# (2) segmented by a simple, explainable scoring archetype, since aging
# patterns genuinely differ by playstyle (rim-reliant bigs/slashers peak
# earlier and decline faster than perimeter shooters, a documented pattern,
# not a guess) -- see refresh_player_projections.py for where the
# league-wide panel this needs actually gets fetched.
# ==========================================================================

# Rule-based, not a clustering model -- per backend/AGENTS.md's ratings/
# transparency requirement, a reader must be able to say plainly which
# bucket a player falls into and why. Checked in this order (rim-reliant
# first): a big who rarely shoots 3s AND rarely gets to the rim would
# otherwise fall through to "Perimeter" by elimination, which is wrong.
RIM_RATE_THRESHOLD = 0.35
THREE_PT_RATE_THRESHOLD = 0.45
ALL_ARCHETYPES_FALLBACK = "All"


def classify_archetype(rim_rate: float, three_pt_rate: float) -> str:
    """rim_rate/three_pt_rate: this player-season's (Restricted Area FGA) /
    FGA and (3PA) / FGA. Unknown (NaN) shot profile classifies as
    "Balanced" -- the neutral middle bucket, not a guess at either extreme.
    """
    if pd.isna(rim_rate) or pd.isna(three_pt_rate):
        return "Balanced"
    if rim_rate >= RIM_RATE_THRESHOLD:
        return "Rim-Reliant"
    if three_pt_rate >= THREE_PT_RATE_THRESHOLD:
        return "Perimeter"
    return "Balanced"


# The composite stats player_power_rankings.py's OFFENSE_COMPONENTS/
# DEFENSE_COMPONENTS actually consume (plus PTS, needed to derive
# USAGE_ADJ_PTS the same way build_player_table() does) -- each projected
# the same way: median %/pt change by (archetype, age) bin. STL_BLK_PER36
# is derived before curve-building (see _historical_panel_with_archetypes in
# refresh_player_projections.py), the rest are already per-game rate/pct
# stats straight from PlayerAdvancedStats.
MULTISTAT_RATE_COLUMNS = (
    "PTS", "TS_PCT", "USG_PCT", "AST_PCT", "TM_TOV_PCT", "STL_BLK_PER36", "DREB_PCT", "DEF_RATING",
)
MIN_OBSERVATIONS_PER_ARCHETYPE_AGE_BIN = 5


def build_archetype_curves(
    panel: pd.DataFrame, stat_columns: tuple[str, ...] = MULTISTAT_RATE_COLUMNS,
) -> dict[str, pd.DataFrame]:
    """One archetype-segmented aging curve per stat in `stat_columns`.

    `panel`: one row per (player, season) with columns PLAYER_ID, SEASON_ID,
    PLAYER_AGE, GP, ARCHETYPE, and every column in `stat_columns`.

    Returns {stat: DataFrame indexed by (archetype, age) with n_observations/
    median_pct_change}. Each stat's curve also carries an `"All"` archetype
    row per age (pooling every archetype together) -- project_player_multistat
    falls back to this when a specific (archetype, age) cell has too few
    real transitions to trust, the same "don't fabricate a trend you don't
    have enough data for" principle as MIN_TOTAL_SEASONS_FOR_ADJUSTMENT above.
    """
    curves: dict[str, pd.DataFrame] = {}
    for stat in stat_columns:
        transitions = []
        for _, player_history in panel.groupby("PLAYER_ID"):
            g = player_history.sort_values("SEASON_ID").reset_index(drop=True)
            g = g[g["GP"] >= MIN_GP_FOR_CURVE].reset_index(drop=True)
            if len(g) < 2:
                continue
            for i in range(len(g) - 1):
                start_val, end_val = g.loc[i, stat], g.loc[i + 1, stat]
                start_age = g.loc[i, "PLAYER_AGE"]
                archetype = g.loc[i, "ARCHETYPE"]
                if pd.isna(start_val) or pd.isna(end_val) or pd.isna(start_age) or start_val == 0:
                    continue
                transitions.append({
                    "age": int(round(start_age)),
                    "archetype": archetype,
                    "pct_change": (end_val - start_val) / abs(start_val),
                })

        if not transitions:
            curves[stat] = pd.DataFrame(columns=["n_observations", "median_pct_change"])
            continue

        t = pd.DataFrame(transitions)
        by_archetype_age = t.groupby(["archetype", "age"])["pct_change"].agg(
            n_observations="count", median_pct_change="median",
        )
        by_age_pooled = t.groupby("age")["pct_change"].agg(n_observations="count", median_pct_change="median")
        by_age_pooled.index = pd.MultiIndex.from_product(
            [[ALL_ARCHETYPES_FALLBACK], by_age_pooled.index], names=["archetype", "age"],
        )
        combined = pd.concat([by_archetype_age, by_age_pooled])
        curves[stat] = combined[combined["n_observations"] >= MIN_OBSERVATIONS_PER_ARCHETYPE_AGE_BIN]

    return curves


def project_player_multistat(
    player_history: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
    archetype: str,
    stat_columns: tuple[str, ...] = MULTISTAT_RATE_COLUMNS,
) -> dict:
    """Projects every stat in `stat_columns` one season forward for one
    player, using their own archetype's curve where there's enough data,
    falling back to the all-archetype curve, falling back to unadjusted --
    same three-tier honesty as project_player_next_season, just per-stat
    instead of once.

    `player_history`: one player's own multi-season panel rows (same shape
    build_archetype_curves takes, filtered to this player), sorted or not.
    """
    if player_history is None or len(player_history) == 0:
        raise ValueError("project_player_multistat needs at least one season of history")

    h = player_history.sort_values("SEASON_ID").reset_index(drop=True)
    last = h.iloc[-1]
    last_age = last["PLAYER_AGE"]
    n_total_seasons = len(h)
    age_bin = int(round(last_age)) if pd.notna(last_age) else None

    result = {
        "player_id": last.get("PLAYER_ID"),
        "archetype": archetype,
        "projected_age": (float(last_age) + 1) if pd.notna(last_age) else None,
    }
    notes = {}
    for stat in stat_columns:
        last_val = last.get(stat)
        applied, pct_change, used_fallback_archetype = False, None, False

        if n_total_seasons < MIN_TOTAL_SEASONS_FOR_ADJUSTMENT or age_bin is None or pd.isna(last_val):
            pass  # not enough personal history, or nothing to project from -- stays unadjusted
        else:
            curve = curves.get(stat, pd.DataFrame())
            if (archetype, age_bin) in curve.index:
                pct_change = float(curve.loc[(archetype, age_bin), "median_pct_change"])
                applied = True
            elif (ALL_ARCHETYPES_FALLBACK, age_bin) in curve.index:
                pct_change = float(curve.loc[(ALL_ARCHETYPES_FALLBACK, age_bin), "median_pct_change"])
                applied = True
                used_fallback_archetype = True

        projected_val = last_val * (1 + pct_change) if applied and pd.notna(last_val) else last_val
        result[f"projected_{stat}"] = projected_val
        result[f"{stat}_adjustment_applied"] = applied
        if used_fallback_archetype:
            notes[stat] = f"Not enough {archetype} data at age {age_bin} -- used the all-archetype curve instead."

    result["development_notes"] = notes
    return result


def team_talent_composite(team_features: pd.DataFrame):
    """The explainable, hand-reproducible summary of every team's *projected*
    roster talent -- reuses backend.ratings.coaching_eval's exact Component
    list and z-score machinery rather than a second parallel composite system.

    This is a transparency artifact for the methodology panel. It is NOT what
    gets fed into win_model's GBM -- that reads the raw recomputed
    avg_age/avg_pts_top10/avg_production_score columns directly, the same
    feature columns the model was already trained on (see
    backend/win_model/train.py). Two different consumers of the same
    projected numbers: one an explainable composite, one a raw model input.

    `team_features`: one row per team with columns Team, avg_age,
    avg_pts_top10, avg_production_score, Payroll -- Payroll is last season's
    known value (see refresh_roster_projection.py for why), everything else
    is this run's projection.
    """
    return compute_team_season_talent(team_features)

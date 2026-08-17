"""backend/win_model/train.py

Runs the full win-model pipeline end to end:
  load master_df -> dedupe + build true next-season target -> walk-forward-tune and
  benchmark KNN vs GBM -> attach prediction intervals to the live forecast -> write
  results + a methodology summary that app.py reads for the "how this was
  calculated" explanation.

Run from repo root:    python -m backend.win_model.train
Run from backend/:      python -m win_model.train
Both work because internal imports here are relative (see backend/AGENTS.md).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone

from .calibration import (
    TOTAL_SEASON_WINS,
    calibrate_season_predictions,
    historical_win_std,
    recenter_interval,
)
from .data_loader import MASTER_DF_FILE, METADATA_FILE, RESULTS_FILE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN, prepare_model_table
from .model import (
    bootstrap_residual_interval,
    compare_models_walk_forward,
    compute_feature_importance,
    gbm_quantile_interval,
)
from .roster_change_features import ROSTER_CHANGE_COLUMN, build_roster_change_features, forecast_roster_change
from .validation import SeasonWalkForwardSplit

# ratings/ is a sibling top-level package, not a submodule of win_model, so
# neither pure-relative nor pure-absolute import works under both of this
# file's supported invocation roots (see backend/AGENTS.md's Imports
# section): relative (`..ratings...`) only resolves from repo-root context
# (`python -m backend.win_model.train`); plain top-level (`ratings...`) only
# resolves from the notebook-style root (`python -m win_model.train`, or
# tests, where backend/ itself is on sys.path). Try relative first, fall back
# to plain -- this is the first place win_model has needed to reach into a
# sibling package, so there's no earlier precedent to match beyond this.
try:
    from ..ratings.player_development import team_talent_composite
except ImportError:
    from ratings.player_development import team_talent_composite

# player_projection_features.py's three columns (avg_age_projected/
# avg_pts_top10_projected/avg_production_score_projected) used to be appended
# here -- validated once (6.781 -> 6.719 wins) and wired in, but that
# validation ran against ratings/player_development.py's
# project_team_talent_features() before its avg_age/avg_production_score
# top-10 bug was fixed (see backend/AGENTS.md and player_development.py's
# docstring). Re-validated after that fix: the improvement doesn't hold
# (6.781 -> 7.016, worse) -- see feature_experiments.player_projection_features
# in the metadata below and player_projection_features.py's own docstring.
# Unwired -- not currently part of EXTENDED_NUMERIC_FEATURES below.
#
# roster_change_features.py's Roster_Change *is* wired in -- validated after
# the real 2025-26 backtest became available (Season=2026, see
# feature_experiments.roster_change_magnitude below): walk-forward MAE
# improves 6.614 -> 6.418 wins, 23 of 30 teams individually better on the
# last (real) fold. Not a uniform fix for every big miss that motivated it
# (helps Philadelphia/Detroit, actually worsens San Antonio/Orlando) -- kept
# because the honest aggregate number is what this project's standard goes
# by, not whether it happens to explain every anecdote that prompted it.
EXTENDED_NUMERIC_FEATURES = NUMERIC_FEATURES + [ROSTER_CHANGE_COLUMN]
FEATURE_COLUMNS = EXTENDED_NUMERIC_FEATURES + CATEGORICAL_FEATURES
INTERVAL_ALPHA = 0.2  # 80% interval (10th-90th percentile)
# Reported together (not just +/-5) so the accuracy story isn't hostage to
# wherever one cutoff happens to fall — see metadata["backtest_accuracy"].
ACCURACY_THRESHOLDS_WINS = [3, 5, 8]

# Written by `python -m backend.ratings.refresh_roster_projection` -- real
# current rosters + the empirical aging curve, aggregated to the same
# avg_age/avg_pts_top10/avg_production_score shape calculate_player_features()
# produces from historical data. Read-only from here: train.py never calls
# live_client itself, matching every other refresh-script/consumer split in
# this project -- see backend/AGENTS.md.
ROSTER_PROJECTION_FILE = Path(__file__).resolve().parents[1] / "outputs" / "roster_projection.json"
ROSTER_PROJECTED_FEATURES = ("avg_age", "avg_pts_top10", "avg_production_score")
# How many top-importance features get their raw per-team value carried into the
# results file (not just named in metadata). 5, not just the 2 the frontend uses
# today, so a chart tweak doesn't require another backend change. Column names
# are whatever the top features actually are this run (e.g. "SOS", "E_L") — not
# hardcoded, since a retrain can change which features rank highest.
N_FEATURE_VALUES_TO_PERSIST = 5

# Plain-language notes for features that would otherwise be a bare, easy-to-
# misread column name in the API/UI. SOS is the one that actually matters here:
# it looks like it could be a third-party rating (the way ESPN/KenPom SOS
# numbers are), but it's entirely self-calculated by this project (see
# load_schedule() in data_loader.py) — worth being explicit about so nobody
# mistakes it for an external benchmark. Covers whatever's in
# feature_values_available; anything not listed here gets a generic fallback
# rather than silently no note at all.
FEATURE_NOTES = {
    "SOS": (
        "Strength of schedule — our own number, not a KenPom or ESPN rating. We build it "
        "from each opponent's win%, point differential, and roster age, averaged across "
        "the full schedule (see load_schedule() in data_loader.py if you want the exact "
        "recipe). Blank for next season's forecast: the schedule hasn't been set yet, so "
        "there are no opponents to average."
    ),
    "E_L": "Eastern Conference losses — one half of the East/West win-loss split.",
    "W_W": "Western Conference wins — one half of the East/West win-loss split.",
    "PLUS_MINUS": "Points scored minus points allowed for the season — the team's full-season point differential.",
    "Payroll": (
        "Total team payroll for the season. For next season's forecast specifically, this "
        "is last season's known figure carried forward — there's no live payroll feed to "
        "draw from, and the real number moves with every trade, extension, and signing all "
        "summer. Treat it as a rough stand-in, not a snapshot of today's books. See the "
        "roster section below for what in this forecast is real-time versus carried forward."
    ),
    "avg_age": "Average age across the team's top 10 scorers, matched to the same top-10 subset avg_pts_top10 uses.",
    "avg_pts_top10": "What the team's ten leading scorers average per game.",
    "avg_production_score": "A rough scoring-efficiency read — points per game divided by minutes per game, averaged across the team's top 10 scorers.",
    "Roster_Change": (
        "Season-over-season roster-talent change — arriving players' own prior production minus "
        "departing players' production, in total season points. Positive means the roster's "
        "incoming talent outweighs who left; negative means the reverse. Uses each player's own "
        "last known real output, never a projection of how they'll do on their new team, so this "
        "can't leak the season being predicted into itself."
    ),
}
_DEFAULT_FEATURE_NOTE = "No additional note recorded for this feature yet."


def _apply_roster_projection(forecast_rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Overrides the forecast row's avg_age/avg_pts_top10/avg_production_score
    with backend/ratings/refresh_roster_projection.py's output (real current
    rosters, projected one season forward via the empirical aging curve) —
    scoped to the forecast row only, per backend/AGENTS.md: this never touches
    `trainable`, so how already-completed historical seasons are trained on is
    unchanged.

    Falls back to the existing stale carry-forward value, per team, whenever
    the projection file is missing or doesn't cover that team — this pipeline
    must keep working (with an honest metadata note) even before the refresh
    script has ever been run, exactly like is_stale()/run_refresh() elsewhere.

    Returns (forecast_rows with overrides applied, a metadata dict describing
    what happened — written into run_pipeline()'s "roster_projection" key).
    """
    forecast_rows = forecast_rows.copy()
    teams = list(forecast_rows["Team"])
    meta = {
        "available": False,
        "season": None,
        "generated_at": None,
        "features_overridden": list(ROSTER_PROJECTED_FEATURES),
        "teams_projected": [],
        "teams_fallback_stale": list(teams),
        "team_talent_composite": None,
        "note": (
            "No roster projection on file yet, so every team's talent numbers here are "
            "carried forward from last season rather than built from an actual current "
            "roster. Run `python -m backend.ratings.refresh_roster_projection` to fix that."
        ),
    }

    if not ROSTER_PROJECTION_FILE.exists():
        return forecast_rows, meta

    try:
        payload = json.loads(ROSTER_PROJECTION_FILE.read_text())
        team_features = payload["team_features"]
    except (json.JSONDecodeError, KeyError):
        meta["note"] = (
            f"{ROSTER_PROJECTION_FILE} exists but couldn't be read, so every team fell back "
            "to last season's carried-forward numbers instead."
        )
        return forecast_rows, meta

    projected_teams = []
    for idx, team in zip(forecast_rows.index, teams):
        features = team_features.get(team)
        if not features:
            continue
        for col in ROSTER_PROJECTED_FEATURES:
            forecast_rows.loc[idx, col] = features[col]
        projected_teams.append(team)

    meta["available"] = True
    meta["season"] = payload.get("season")
    meta["generated_at"] = payload.get("generated_at")
    meta["teams_projected"] = projected_teams
    meta["teams_fallback_stale"] = [t for t in teams if t not in projected_teams]
    meta["note"] = (
        f"Age, top-scorer output, and roster production for {len(projected_teams)} of "
        f"{len(teams)} teams come from real current rosters (season {meta['season']}), "
        "aged forward one year with our empirical development curve — not a repeat of "
        "last season's numbers. "
        + (
            f"The other {len(meta['teams_fallback_stale'])} — "
            f"{', '.join(meta['teams_fallback_stale'])} — had no roster data to project from, "
            "so those still show last season's carried-forward figures."
            if meta["teams_fallback_stale"] else
            "Every team in this forecast is covered."
        )
    )

    # Explainable "how this offseason's projected talent compares league-wide"
    # composite — reuses coaching_eval's z-score machinery (see
    # player_development.team_talent_composite), not a second parallel system.
    # This is a transparency artifact for the methodology panel only; it is
    # NOT fed into the GBM — the model reads the raw recomputed feature
    # columns above, the same columns it was already trained on.
    composite_input = forecast_rows.loc[forecast_rows["Team"].isin(projected_teams),
                                         ["Team", "avg_age", "avg_pts_top10", "avg_production_score", "Payroll"]]
    if len(composite_input) > 1:
        _, breakdowns = team_talent_composite(composite_input)
        meta["team_talent_composite"] = {b.subject_name: b.to_dict() for b in breakdowns}

    return forecast_rows, meta


def run_pipeline(master_df_path=None, write_output: bool = True):
    """Returns (results_df, metadata_dict); optionally writes both to disk."""
    master_df = pd.read_csv(master_df_path or MASTER_DF_FILE)
    table = prepare_model_table(master_df)

    trainable = table[table[TARGET_COLUMN].notna()].reset_index(drop=True)
    forecast_rows = table[table[TARGET_COLUMN].isna()].reset_index(drop=True)

    # Season-over-season roster-talent change (see roster_change_features.py) --
    # a team-season with no computable change (missing panel data) falls back
    # to 0, "no measured change", rather than dropping the row.
    changes = build_roster_change_features(master_df_path or MASTER_DF_FILE)
    trainable = trainable.merge(changes, on=["Season", "Team"], how="left")
    trainable[ROSTER_CHANGE_COLUMN] = trainable[ROSTER_CHANGE_COLUMN].fillna(0.0)

    X = trainable[FEATURE_COLUMNS]
    y = trainable[TARGET_COLUMN]
    groups = trainable["Season"]

    comparison = compare_models_walk_forward(X, y, groups, EXTENDED_NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    winning_search = comparison.winning_search
    fitted_pipeline = winning_search.best_estimator_  # GridSearchCV refits on all of X, y by default

    splitter = SeasonWalkForwardSplit()

    # Computed here (not after oof/forecast, where it used to live) so the top
    # feature names are available to attach raw values to both result sets below.
    importance = compute_feature_importance(fitted_pipeline, X, y, FEATURE_COLUMNS)
    top_feature_names = list(importance.head(N_FEATURE_VALUES_TO_PERSIST).index)

    # Target spread for calibration (see calibration.py) — one fixed number
    # computed once from every real historical outcome, reused identically
    # across every walk-forward fold and the live forecast below. Not
    # recomputed per fold on an expanding window: the *spread* of real NBA
    # seasons isn't a fitted parameter a fold could leak from seeing "the
    # future" of, unlike a model coefficient — it's closer to a physical
    # constant of the sport (like TOTAL_SEASON_WINS itself) than something
    # walk-forward's no-future-leakage discipline is protecting against.
    historical_std = historical_win_std(trainable[TARGET_COLUMN])

    # ---- Out-of-fold walk-forward predictions across history, for backtest display ----
    oof_frames = []
    for train_idx, test_idx in splitter.split(X, y, groups):
        fold_model = clone(fitted_pipeline)
        fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
        preds_raw = fold_model.predict(X.iloc[test_idx])
        # Every row in one fold's test_idx is the same held-out season's full
        # set of teams (SeasonWalkForwardSplit's test set is always one whole
        # season) — exactly what calibrate_season_predictions needs to be
        # calibrating a complete season, not a partial one.
        preds_calibrated = calibrate_season_predictions(preds_raw, historical_std)
        fold_df = pd.DataFrame({
            "Season": trainable.iloc[test_idx]["Season"].to_numpy() + 1,
            "Team": trainable.iloc[test_idx]["Team"].to_numpy(),
            "W": trainable.iloc[test_idx][TARGET_COLUMN].to_numpy(),
            "Pred_Wins": preds_calibrated,
            "Pred_Wins_Raw": preds_raw,
            "Pred_Wins_Lower": np.nan,
            "Pred_Wins_Upper": np.nan,
        })
        for feat in top_feature_names:
            fold_df[feat] = trainable.iloc[test_idx][feat].to_numpy()
        oof_frames.append(fold_df)
    oof = pd.concat(oof_frames, ignore_index=True)
    # Multiple thresholds, not just +/-5: a single cutoff can look artificially
    # bad or good depending on exactly where it falls relative to the error
    # distribution — see ACCURACY_THRESHOLDS_WINS and metadata["backtest_accuracy"].
    oof_abs_error = (oof["Pred_Wins"] - oof["W"]).abs()
    for t in ACCURACY_THRESHOLDS_WINS:
        oof[f"within_{t}"] = oof_abs_error <= t

    walk_forward_mae_uncalibrated = float((oof["Pred_Wins_Raw"] - oof["W"]).abs().mean())
    walk_forward_mae_calibrated = float((oof["Pred_Wins"] - oof["W"]).abs().mean())
    oof = oof.drop(columns=["Pred_Wins_Raw"])  # internal-only, for the MAE comparison above

    # ---- Live forecast: most recent season's completed stats, no known outcome yet ----
    # Talent-relevant features get overridden from the real-current-roster
    # projection where available (see _apply_roster_projection) before this
    # row is used for anything — trainable/X/y above are untouched.
    forecast_rows, roster_projection_meta = _apply_roster_projection(forecast_rows)
    # Roster_Change for the forecast row: real current roster (ratings/
    # refresh_roster_projection.py's fetch) vs. the most recently completed
    # season's real roster -- see roster_change_features.forecast_roster_change.
    # 0.0 (not NaN) whenever it can't be computed, matching trainable's fallback.
    forecast_rows[ROSTER_CHANGE_COLUMN] = [
        forecast_roster_change(team, int(season), ROSTER_PROJECTION_FILE) or 0.0
        for team, season in zip(forecast_rows["Team"], forecast_rows["Season"])
    ]
    X_forecast = forecast_rows[FEATURE_COLUMNS]
    forecast_point = fitted_pipeline.predict(X_forecast)

    if comparison.winner == "gbm":
        lower, upper = gbm_quantile_interval(
            comparison.gbm_search, X, y, X_forecast,
            lower_q=INTERVAL_ALPHA / 2, upper_q=1 - INTERVAL_ALPHA / 2,
        )
        interval_method = "GBM native quantile regression (refits the winning model at the 10th and 90th percentiles)"
    else:
        lower, upper = bootstrap_residual_interval(
            comparison.knn_search, X, y, groups, splitter, X_forecast, alpha=INTERVAL_ALPHA,
        )
        interval_method = "Bootstrap of pooled walk-forward out-of-fold residuals (1000 resamples per team)"

    # Independently-fit quantile models aren't guaranteed to stay on the correct side
    # of the point estimate on every row ("quantile crossing"). Simply clamping the
    # crossed side to the point estimate (upper = max(upper, point)) prevents an
    # invalid interval but produces a degenerate zero-margin one instead — confirmed
    # live: ~9/30 teams in a real run had an upper margin under 1 win while their
    # lower margin was a normal 8-14 wins, which reads as "no upside uncertainty"
    # and isn't true — that team's independently-fit 90th-percentile model just
    # happened to land at/below its own median model's prediction. Where crossing
    # actually happened, mirror the OTHER side's margin instead of collapsing to
    # zero width — an honest fallback ("no trustworthy upper quantile fit for this
    # team, so we're using the lower margin's width as our best estimate of the
    # interval's scale") beats a technically-valid but useless zero-margin interval.
    lower_crossed = lower >= forecast_point
    upper_crossed = upper <= forecast_point
    lower = np.where(lower_crossed, forecast_point - (upper - forecast_point), lower)
    upper = np.where(upper_crossed, forecast_point + (forecast_point - lower), upper)
    # Final safety net in case mirroring itself produced a crossing.
    lower = np.minimum(lower, forecast_point)
    upper = np.maximum(upper, forecast_point)

    # Same calibration applied to every walk-forward fold above, applied here
    # to the live forecast row — all 30 teams' forecast-season predictions are
    # exactly "one season's full set of teams," same shape calibrate_season_predictions
    # expects. The interval gets recentered by each team's own total
    # adjustment (recenter_interval), not recalibrated independently — an
    # interval calibrated separately from its own point estimate could stop
    # bracketing it.
    forecast_point_calibrated = calibrate_season_predictions(forecast_point, historical_std)
    lower, upper = recenter_interval(forecast_point, lower, upper, forecast_point_calibrated)

    forecast = pd.DataFrame({
        "Season": forecast_rows["Season"].to_numpy() + 1,
        "Team": forecast_rows["Team"].to_numpy(),
        "W": np.nan,
        "Pred_Wins": forecast_point_calibrated,
        "Pred_Wins_Lower": lower,
        "Pred_Wins_Upper": upper,
        **{f"within_{t}": np.nan for t in ACCURACY_THRESHOLDS_WINS},
    })
    for feat in top_feature_names:
        forecast[feat] = forecast_rows[feat].to_numpy()

    results = pd.concat([oof, forecast], ignore_index=True).sort_values(["Season", "Team"]).reset_index(drop=True)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_method": (
            "Season-grouped walk-forward cross-validation: trained on all seasons <= N, "
            "validated on season N+1, rolled forward one season at a time across all "
            "available history. No random k-fold CV is used anywhere in this pipeline — "
            "see backend/win_model/validation.py."
        ),
        "target_definition": (
            "Next_W: a team's actual win total in the season following the feature row's "
            "season, built with an explicit groupby-shift on W. Not the same as the master_df "
            "NWins column, which is same-season W despite its name — see features.py."
        ),
        "model_comparison": {
            "candidates": ["KNeighborsRegressor", "HistGradientBoostingRegressor (monotonic)"],
            "knn_walk_forward_mae": round(float(comparison.knn_walk_forward_mae), 3),
            "gbm_walk_forward_mae": round(float(comparison.gbm_walk_forward_mae), 3),
            "winner": comparison.winner,
            "n_walk_forward_folds": splitter.get_n_splits(X, y, groups),
        },
        "calibration": {
            "description": (
                "We adjust the raw model output two ways before showing it to you. First, we "
                "widen or narrow each season's 30 predictions around that season's own average "
                "to match how spread out real NBA win totals actually are — left alone, "
                "regression models like this one flatten the gap between good and bad teams "
                "more than reality does. Second, we shift every team by the same small amount "
                "so the season's predictions add up to exactly 1,230 wins — the real total for "
                "a full slate of games (30 teams, 82 games apiece, two teams per game). Neither "
                "property comes for free from the model itself; both are enforced afterward."
            ),
            "historical_win_std": round(historical_std, 3),
            "target_season_total_wins": TOTAL_SEASON_WINS,
            "walk_forward_mae_uncalibrated": round(walk_forward_mae_uncalibrated, 3),
            "walk_forward_mae_calibrated": round(walk_forward_mae_calibrated, 3),
            "improves_backtest_mae": walk_forward_mae_calibrated < walk_forward_mae_uncalibrated,
            "note": (
                (
                    "This adjustment actually sharpens the backtest, too — walk-forward error "
                    f"drops from {walk_forward_mae_uncalibrated:.3f} to "
                    f"{walk_forward_mae_calibrated:.3f} wins on top of the model-selection numbers "
                    "above, which are measured before any of this is applied."
                ) if walk_forward_mae_calibrated < walk_forward_mae_uncalibrated else (
                    "Worth saying plainly: this adjustment does not sharpen the backtest — walk-"
                    f"forward error moves from {walk_forward_mae_uncalibrated:.3f} to "
                    f"{walk_forward_mae_calibrated:.3f} wins, flat or worse. We keep it anyway, "
                    "because matching the real 82-game season total and the real spread of win "
                    "totals are correct on their own terms, independent of whether they happen "
                    "to shave points off average error. Don't read this as \"calibration helped.\""
                )
            ),
        },
        "feature_experiments": {
            "player_projection_features": {
                "hypothesis": (
                    "Projecting each team's actual historical roster forward with our aging "
                    "curve, and feeding that alongside the usual current-season numbers, "
                    "sharpens the walk-forward backtest."
                ),
                "result": "No longer holds — unwired. This validated positive once (6.781 -> 6.719 "
                           "wins) and shipped, but that run measured "
                           "ratings/player_development.py's project_team_talent_features() before "
                           "a real bug in it was fixed: avg_age and avg_production_score were "
                           "averaging every projected player on the roster (15+ once bench depth is "
                           "included), not the same top-10-by-points subset avg_pts_top10 already "
                           "used — inflating both toward bench-heavy values a real team-season "
                           "never has. Re-tested after that fix: walk-forward error goes from 6.781 "
                           "to 7.016 (worse, not better). The earlier positive result was measuring "
                           "the bug, not the idea. Unwired from FEATURE_COLUMNS accordingly — see "
                           "backend/win_model/player_projection_features.py to re-run the check "
                           "again after any future change to the aging curve or "
                           "project_team_talent_features().",
            },
            "gbm_knn_ensemble": {
                "hypothesis": "Averaging the two candidate models' predictions beats picking the single better one.",
                "result": "It doesn't. GBM alone (6.781 wins MAE) clearly beats a GBM/KNN blend "
                           "(7.211 wins) — KNN trails badly enough on its own (8.283 wins) that "
                           "blending it in just drags GBM's stronger predictions down. We left this "
                           "out of the shipped model — same rule as the calibration finding above: "
                           "report what the backtest actually shows, not what we hoped for.",
            },
            "roster_change_magnitude": {
                "hypothesis": (
                    "Season-over-season roster-talent change (arriving players' prior production "
                    "minus departing players', see Roster_Change in feature_notes) improves walk-"
                    "forward MAE, on top of the existing current-season aggregates — prompted "
                    "directly by this project's first real out-of-sample backtest (Season=2026, "
                    "actual 2025-26 results), whose biggest misses (Philadelphia 76ers -14.3, San "
                    "Antonio Spurs -12.2, Orlando Magic -10.9, Detroit Pistons -10.6 wins, all "
                    "underestimates) were suspected to share real offseason roster change the "
                    "existing features undersell."
                ),
                "result": "It does, on the honest aggregate — walk-forward MAE improves 6.614 -> "
                           "6.418 wins, and 23 of 30 teams individually improve on the most recent "
                           "(real) fold specifically. Worth saying plainly since it complicates the "
                           "tidy version of the hypothesis: it does NOT uniformly fix the four "
                           "misses that motivated it — Philadelphia and Detroit both improve "
                           "(-14.3 -> -12.2, -10.6 -> -10.4), but San Antonio and Orlando actually "
                           "get worse (-12.2 -> -15.5, -10.9 -> -12.5). Those four don't share one "
                           "common cause (see the miss-pattern check this same session ran: prior-"
                           "season underperformance-relative-to-roster-talent correlates weakly "
                           "with the miss direction, r=+0.24, but doesn't explain Detroit or Orlando "
                           "either). Kept anyway, per this project's standard: the honest walk-"
                           "forward number is what decides this, not whether it happens to explain "
                           "every anecdote that prompted building it.",
            },
            "age_curve_residual": {
                "hypothesis": (
                    "A team-level, production-weighted measure of how far each roster player's "
                    "most recent real transition sits above/below player_development.py's "
                    "empirical age curve (the residual, not the raw curve output) improves "
                    "walk-forward MAE, on top of the existing current-season aggregates."
                ),
                "result": "Helps in isolation (vs. plain NUMERIC_FEATURES: 6.614 -> 6.514 wins) but "
                           "hurts once stacked on the real shipped baseline (NUMERIC_FEATURES + "
                           "Roster_Change: 6.425 -> 6.528 wins, +0.103). The isolated number alone "
                           "would have been misleading -- this feature's signal overlaps with what "
                           "Roster_Change already captures (both describe roster-talent change "
                           "year over year, just measured differently: transaction-based arrival/"
                           "departure production vs. per-player aging-curve deviation), so most of "
                           "its isolated lift disappears, and what's left is net negative, once "
                           "Roster_Change is already in the model. Not wired into FEATURE_COLUMNS "
                           "-- see backend/win_model/age_curve_residual_features.py to re-run the "
                           "check again after any future change to Roster_Change or the aging "
                           "curve itself.",
            },
            "defense_composite": {
                "hypothesis": (
                    "win_model's talent features (avg_pts_top10, avg_production_score) are purely "
                    "offensive. Adding a defensive analog -- reusing "
                    "ratings/player_power_rankings.py's existing DEFENSE_COMPONENTS "
                    "(STL_BLK_PER36, DEF_RATING, DREB_PCT) rather than inventing a second rating "
                    "system, aggregated to the same top-10-players shape -- improves walk-forward "
                    "MAE. This was this session's own leading hypothesis going in."
                ),
                "result": "Barely helps in isolation (vs. plain NUMERIC_FEATURES: 6.614 -> 6.608 "
                           "wins, +0.006) and hurts the most of any feature tested once stacked on "
                           "the real shipped baseline (NUMERIC_FEATURES + Roster_Change: 6.425 -> "
                           "6.618 wins, +0.193) -- the largest regression of the three features "
                           "tested this session, despite being the one most expected to matter. "
                           "Not wired into FEATURE_COLUMNS -- see "
                           "backend/win_model/defense_composite_features.py to re-run the check "
                           "again after any future change to DEFENSE_COMPONENTS or Roster_Change.",
            },
            "coach_quality": {
                "hypothesis": (
                    "The team's current coach's career average wins-above-expectation (expanding "
                    "window, Season <= N, reusing coaching_eval.coach_wins_above_expectation(), "
                    "requiring at least MIN_TOTAL_SEASONS_FOR_ADJUSTMENT seasons of track record "
                    "-- no fabricated value for a first-year coach) improves walk-forward MAE."
                ),
                "result": "Barely helps in isolation (vs. plain NUMERIC_FEATURES: 6.614 -> 6.607 "
                           "wins, +0.007; 121 of 300 rows had no qualifying coach track record and "
                           "were correctly excluded, not fabricated) but hurts once stacked on the "
                           "real shipped baseline (NUMERIC_FEATURES + Roster_Change: 6.425 -> "
                           "6.486 wins, +0.061). Same overlap story as the other two: whatever "
                           "signal a coach's career record carries about roster quality is already "
                           "represented, at least partially, by Roster_Change and the existing "
                           "talent features. Not wired into FEATURE_COLUMNS -- see "
                           "backend/win_model/coach_quality_features.py to re-run the check again "
                           "after any future change to Roster_Change or coach attribution data.",
            },
            "recency_weighting": {
                "hypothesis": (
                    "Weighting training rows by recency (sample_weight = decay_rate ** "
                    "seasons_ago, fold-relative so early folds don't leak dataset-size "
                    "information) so the model favors how the league plays now over how it "
                    "played a decade ago improves walk-forward MAE. GBM only -- "
                    "KNeighborsRegressor.fit() has no sample_weight parameter at all, so KNN "
                    "structurally can't be recency-weighted this way."
                ),
                "result": "Helps in isolation (vs. plain NUMERIC_FEATURES: 6.615 -> 6.525 wins "
                           "at decay_rate=0.95) but loses once stacked on the real shipped "
                           "baseline (NUMERIC_FEATURES + Roster_Change: best stacked decay_rate "
                           "is 1.0 -- i.e. no weighting at all -- at 6.434 wins). Same overlap "
                           "story as the other three: same isolated-win, stacked-loss pattern. "
                           "Not wired into FEATURE_COLUMNS or the training Pipeline -- see "
                           "backend/win_model/recency_weighting.py to re-run the check again "
                           "after any future change to Roster_Change or the season range in "
                           "master_df.csv.",
            },
            "schedule_simulation": {
                "hypothesis": (
                    "Treating a team's predicted win percentage as uniform across all 82 games "
                    "ignores schedule strength -- some teams play a harder slate than others. "
                    "Simulating the real schedule game-by-game (log5 win probability per matchup, "
                    "home-court edge calibrated from this project's own historical Home_W/Home_L "
                    "split, Monte Carlo averaged over 10,000 simulated seasons) instead of "
                    "assuming a flat win rate improves win-total accuracy."
                ),
                "result": "ACCEPTED -- the one hypothesis this session that survived the honest "
                           "test. Pooled across every backtestable season (2017-18 through "
                           "2025-26, 270 team-seasons, real historical schedules fetched live via "
                           "nba_api's ScheduleLeagueV2), walk-forward MAE improves 6.835 -> 6.768 "
                           "wins -- real but modest, and it clearly hurts in both "
                           "pandemic-disrupted seasons (2019-20, 2020-21) while helping in most "
                           "normal ones. Not a FEATURE_COLUMNS addition -- this is a downstream "
                           "adjustment applied to Pred_Wins after training, not a model input, so "
                           "it can't live in train.py's own pipeline (it needs Pred_Wins as its "
                           "rating input, which train.py is what produces -- see "
                           "refresh_schedule_simulation.py for why this is a separate pass, run "
                           "after train.py, not a training-time step). Re-run "
                           "backend/win_model/schedule_simulation_backtest.py to re-check this "
                           "after any change to Roster_Change or the walk-forward calibration "
                           "step.",
            },
        },
        "winning_model": {
            "type": type(fitted_pipeline.steps[-1][1]).__name__,
            "best_params": {k.split("__")[-1]: v for k, v in winning_search.best_params_.items()},
            "monotonic_increasing_features": (
                sorted(m for m in ["WIN%", "PLUS_MINUS"]) if comparison.winner == "gbm" else None
            ),
        },
        "backtest_accuracy": {
            "thresholds_wins": ACCURACY_THRESHOLDS_WINS,
            "overall": {
                str(t): round(float(oof[f"within_{t}"].mean()), 4) for t in ACCURACY_THRESHOLDS_WINS
            },
            "n_oof_predictions": int(len(oof)),
            "note": (
                "This is out-of-sample accuracy — every prediction here came from a model that "
                f"had never seen that season's result, pooled across all {int(len(oof))} "
                "team-seasons we've backtested. We show three thresholds on purpose, because a "
                "single cutoff can flatter or unfairly bury the model depending on exactly where "
                "it lands. A team's win total is a genuinely hard thing to call a year out — "
                "injuries, trades, a young player's leap, a coaching change — which is exactly "
                "why Vegas's own preseason win totals and ESPN's BPI land in a similar range at "
                "tight thresholds. Small sample here, too: these numbers will firm up as more "
                "seasons get backtested, not because anything's broken today."
            ),
        },
        "top_feature_importance": [
            {"feature": f, "importance_mae_increase": round(float(v), 4)}
            for f, v in importance.head(15).items()
        ],
        # Which of the above also have a raw per-team value attached to each row in
        # the results file (results has 15 ranked names above but only these have a
        # matching column — see N_FEATURE_VALUES_TO_PERSIST) — e.g. for a chart
        # plotting the top-2 features against each other, per team.
        "feature_values_available": top_feature_names,
        # Plain-language caveats for the features above — SOS in particular is
        # easy to mistake for a third-party rating; see FEATURE_NOTES.
        "feature_notes": {f: FEATURE_NOTES.get(f, _DEFAULT_FEATURE_NOTE) for f in top_feature_names},
        "prediction_interval": {
            "method": interval_method,
            "coverage": f"{int((1 - INTERVAL_ALPHA) * 100)}% ({int(INTERVAL_ALPHA / 2 * 100)}th-{int((1 - INTERVAL_ALPHA / 2) * 100)}th percentile)",
        },
        "n_training_rows": int(len(trainable)),
        "n_teams": int(trainable["Team"].nunique()),
        "feature_seasons_used": sorted(int(s) for s in trainable["Season"].unique()),
        "forecast_target_season": int(forecast["Season"].iloc[0]) if len(forecast) else None,
        # Which forecast-row talent inputs are real current data vs. projected
        # vs. known-stale — see _apply_roster_projection. Historical (trainable)
        # rows are entirely unaffected; this section only ever describes the
        # live forecast row.
        "roster_projection": roster_projection_meta,
    }

    if write_output:
        results.to_csv(RESULTS_FILE, index=False)
        METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    return results, metadata


if __name__ == "__main__":
    results_df, meta = run_pipeline()
    print(f"Winner: {meta['model_comparison']['winner']} "
          f"(KNN MAE={meta['model_comparison']['knn_walk_forward_mae']}, "
          f"GBM MAE={meta['model_comparison']['gbm_walk_forward_mae']})")
    print(f"Wrote {len(results_df)} rows to {RESULTS_FILE}")
    print(f"Wrote methodology to {METADATA_FILE}")

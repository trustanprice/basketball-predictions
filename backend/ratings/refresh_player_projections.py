"""backend/ratings/refresh_player_projections.py

Scheduled refresh job for the players page's "Projected 26-27 Leaders" view:
projects every current-roster player's stats one season forward via
player_development.py's archetype-segmented aging curves, then runs the
projected numbers through the EXACT SAME top_offensive_players/
top_defensive_players composite player_power_rankings.py already uses for
the real (actual-stats) leaders -- not a second parallel ranking system.

Pipeline:
  1. Real current rosters for all 30 teams (TeamRoster, same endpoint/season
     convention as refresh_roster_projection.py).
  2. A multi-season historical panel (season totals + advanced metrics + shot
     locations, N_HISTORICAL_SEASONS seasons, each a handful of *league-wide*
     calls -- not per-player -- see player_development.py's module docstring
     for why this is the efficient shape vs. career_stats.py's per-player
     endpoint) used both to classify each player's current scoring archetype
     and to build the archetype-segmented aging curves.
  3. Each current-roster player's stats projected one season forward
     (player_development.project_player_multistat).
  4. Projected numbers reshaped into the same season_totals/advanced_stats
     dataframe shape build_player_table() expects, so the composite runs
     completely unchanged.

Run manually: python -m backend.ratings.refresh_player_projections
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.live_client.client import NBAStatsClient
from backend.live_client.endpoints.stats.advanced_metrics import PlayerAdvancedStats
from backend.live_client.endpoints.stats.season_totals import PlayerSeasonTotals
from backend.live_client.endpoints.stats.shot_locations import PlayerShotLocations
from backend.live_client.endpoints.stats.team_roster import TeamRoster
from backend.live_client.lookups.loader import load_teams
from backend.ratings.player_development import (
    MULTISTAT_RATE_COLUMNS,
    build_archetype_curves,
    classify_archetype,
    project_player_multistat,
)
from backend.ratings.player_power_rankings import build_player_table, top_defensive_players, top_offensive_players
from backend.ratings.refresh_roster_projection import current_roster_season_start_year

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "player_projections.json"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60

# Bounded, recent range -- each season here is 3 *league-wide* calls (season
# totals, advanced metrics, shot locations), not one per player, so this
# stays cheap even at N=6 (18 calls total for the whole curve-building
# panel) -- a deliberately smaller/different tradeoff than
# refresh_roster_projection.py's per-player PlayerCareerStats approach,
# chosen specifically to build an archetype x age curve without the request
# volume that already caused real rate-limiting once (see backend/AGENTS.md).
N_HISTORICAL_SEASONS = 6
REQUEST_PACING_SECONDS = 0.6

PROJECTED_LEADERS_NOTE = (
    "PRESEASON PROJECTION -- there's no in-season ranking yet, because the season hasn't "
    "tipped off. Every number here starts from that player's real most recent season and "
    "ages it forward using a straightforward rule: how have players of the same scoring "
    "archetype and age typically trended the following year (see "
    "backend/ratings/player_development.py for the actual medians)? That's a lookup against "
    "real history, not a model's guess. Check back once games are being played -- these "
    "rankings will switch over to real, in-season performance then."
)


def is_stale(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> bool:
    if not OUTPUT_FILE.exists():
        return True
    try:
        payload = json.loads(OUTPUT_FILE.read_text())
        generated_at = datetime.fromisoformat(payload["generated_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return True
    return (datetime.now(timezone.utc) - generated_at).total_seconds() > max_age_seconds


def _season_string(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _fetch_season_panel(season: str, client: NBAStatsClient) -> pd.DataFrame:
    """One season's merged panel: PLAYER_ID, SEASON_ID, PLAYER_AGE, GP, ARCHETYPE,
    + every column in MULTISTAT_RATE_COLUMNS. League-wide (three calls total),
    not per-player."""
    totals = PlayerSeasonTotals(season=season, per_mode="PerGame", client=client).fetch().to_dataframe()
    advanced = PlayerAdvancedStats(season=season, client=client).fetch().to_dataframe()
    shots = PlayerShotLocations(season=season, per_mode="PerGame", client=client).fetch().to_dataframe()

    three_pt_zones = ["Left Corner 3_FGA", "Right Corner 3_FGA", "Above the Break 3_FGA"]
    shots = shots.copy()
    shots["_total_fga"] = shots[[c for c in shots.columns if c.endswith("_FGA")]].sum(axis=1)
    shots["_rim_rate"] = (shots["Restricted Area_FGA"] / shots["_total_fga"]).where(shots["_total_fga"] > 0)
    shots["_three_pt_rate"] = (
        shots[[c for c in three_pt_zones if c in shots.columns]].sum(axis=1) / shots["_total_fga"]
    ).where(shots["_total_fga"] > 0)

    panel = totals.merge(advanced, on=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID"], suffixes=("", "_adv"))
    # totals/advanced may each carry their own AGE column (collision handled
    # by the suffixes above, so it survives as "AGE" or "AGE_adv" depending
    # on which side had it) -- drop whichever survived so the merge below
    # unambiguously takes shot_locations' AGE (the one this function actually
    # verified the shape of) as the single "AGE" column, not "AGE_x"/"AGE_y".
    panel = panel.drop(columns=[c for c in ("AGE", "AGE_adv") if c in panel.columns])
    panel = panel.merge(
        shots[["PLAYER_ID", "AGE", "_rim_rate", "_three_pt_rate"]].rename(columns={"AGE": "PLAYER_AGE"}),
        on="PLAYER_ID", how="inner",
    )

    panel["STL_BLK_PER36"] = (panel["STL"] + panel["BLK"]) / panel["MIN"].replace(0, 1) * 36
    panel["ARCHETYPE"] = [
        classify_archetype(r, t) for r, t in zip(panel["_rim_rate"], panel["_three_pt_rate"])
    ]
    panel["SEASON_ID"] = season
    return panel[["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "SEASON_ID", "PLAYER_AGE", "GP", "MIN", "ARCHETYPE", *MULTISTAT_RATE_COLUMNS]]


def run_refresh(target_season_start_year: int | None = None, write_output: bool = True) -> dict:
    start_year = target_season_start_year or current_roster_season_start_year()
    roster_season = _season_string(start_year)
    historical_seasons = [_season_string(start_year - 1 - i) for i in range(N_HISTORICAL_SEASONS)]

    teams = load_teams()

    with NBAStatsClient() as client:
        panels = []
        for i, season in enumerate(historical_seasons):
            if i > 0:
                time.sleep(REQUEST_PACING_SECONDS)
            panels.append(_fetch_season_panel(season, client))
        full_panel = pd.concat(panels, ignore_index=True)

        rosters = {}
        for i, (_, row) in enumerate(teams.iterrows()):
            if i > 0:
                time.sleep(REQUEST_PACING_SECONDS)
            rosters[row["full_name"]] = TeamRoster(
                team_id=int(row["team_id"]), season=roster_season, client=client,
            ).fetch().to_dataframe()

    curves = build_archetype_curves(full_panel)

    projections = []
    for team_name, roster in rosters.items():
        for player_id, player_name in zip(roster["PLAYER_ID"], roster["PLAYER"]):
            history = full_panel[full_panel["PLAYER_ID"] == int(player_id)].sort_values("SEASON_ID")
            if history.empty:
                continue
            last = history.iloc[-1]
            archetype = last["ARCHETYPE"]
            proj = project_player_multistat(history, curves, archetype=archetype)
            proj["player_name"] = player_name
            proj["team_id"] = int(last["TEAM_ID"])
            proj["team_name"] = team_name
            # Playing time is carried forward unchanged, same principle as
            # player_development.project_player_next_season -- projecting
            # minutes/role is a separate problem this curve doesn't attempt.
            proj["projected_min"] = float(last["MIN"])
            proj["projected_gp"] = float(last["GP"])
            projections.append(proj)

    if not projections:
        raise ValueError("No current-roster players matched the historical panel -- nothing to project.")

    proj_df = pd.DataFrame(projections)
    # Reshape into build_player_table()'s expected input shape so the
    # offense/defense composite runs completely unchanged on projected
    # numbers -- see module docstring. STL/BLK are split back out of the
    # single projected STL_BLK_PER36 rate arbitrarily (all into STL, none
    # into BLK) since build_player_table only ever consumes their *sum*
    # (STL_BLK_PER36's own numerator), never STL/BLK individually.
    season_totals = pd.DataFrame({
        "PLAYER_ID": proj_df["player_id"],
        "PLAYER_NAME": proj_df["player_name"],
        "TEAM_ID": proj_df["team_id"],
        "GP": proj_df["projected_gp"],
        "MIN": proj_df["projected_min"],
        "PTS": proj_df["projected_PTS"],
        "STL": proj_df["projected_STL_BLK_PER36"] * proj_df["projected_min"] / 36,
        "BLK": 0.0,
    })
    advanced_stats = pd.DataFrame({
        "PLAYER_ID": proj_df["player_id"],
        "PLAYER_NAME": proj_df["player_name"],
        "TEAM_ID": proj_df["team_id"],
        "USG_PCT": proj_df["projected_USG_PCT"],
        "TS_PCT": proj_df["projected_TS_PCT"],
        "AST_PCT": proj_df["projected_AST_PCT"],
        "TM_TOV_PCT": proj_df["projected_TM_TOV_PCT"],
        "DREB_PCT": proj_df["projected_DREB_PCT"],
        "DEF_RATING": proj_df["projected_DEF_RATING"],
    })

    player_table = build_player_table(season_totals, advanced_stats)
    offense = [b.to_dict() for b in top_offensive_players(player_table, n=50)]
    defense = [b.to_dict() for b in top_defensive_players(player_table, n=50)]

    payload = {
        "season": _season_string(start_year),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": PROJECTED_LEADERS_NOTE,
        "historical_seasons_used": historical_seasons,
        "n_players_projected": int(len(proj_df)),
        "n_qualified_players": int(len(player_table)),
        "offense": offense,
        "defense": defense,
    }

    if write_output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2, default=str))

    return payload


if __name__ == "__main__":
    result = run_refresh()
    print(f"Refreshed player projections for {result['season']} ({result['n_players_projected']} players)")
    print(f"Wrote {OUTPUT_FILE}")

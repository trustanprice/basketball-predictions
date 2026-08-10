"""backend/ratings/refresh_roster_projection.py

Scheduled refresh job: for every team, fetches the real current roster
(CommonTeamRoster) and each roster player's career history
(PlayerCareerStats), builds the league-wide empirical aging curve from that
same pooled history, projects each roster one season forward, and aggregates
to the team-level talent features backend/win_model/data_loader.py's
calculate_player_features() would have produced from real historical data --
avg_age, avg_pts_top10, avg_production_score.

This is the *only* place backend.ratings.player_development's live_client
dependency gets exercised -- backend/win_model/train.py reads the cached JSON
this writes for its forecast row, it never calls live_client directly. Same
separation refresh_player_ratings.py uses for player_power_rankings, and the
same reason: NBA.com rate limits + per-request latency make a live call per
API request wrong for a request-serving API -- see backend/AGENTS.md.

Deliberately does not touch payroll: nba_api has no payroll endpoint, and the
existing payroll figures already live in master_df (data_loader.load_payroll).
backend/win_model/train.py is where those get combined with this script's
output -- see its roster-projection wiring section.

"Reachable history" for the aging curve = the career histories of every
player currently on an NBA roster (fetched here anyway, to get each player's
own most recent season) -- not an exhaustive fetch of every player in league
history, which would be substantial additional NBA.com load for a marginal
accuracy gain over data that's already league-wide and cross-era (rookies
through 15-year veterans).

Run manually:  python -m backend.ratings.refresh_roster_projection
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.live_client.client import NBAStatsClient
from backend.live_client.endpoints.stats.career_stats import PlayerCareerStats
from backend.live_client.endpoints.stats.team_roster import TeamRoster
from backend.live_client.lookups.loader import load_teams

from .player_development import build_aging_curve, project_player_next_season, project_team_talent_features

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "roster_projection.json"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60

# A full refresh fires one PlayerCareerStats call per unique roster player --
# roughly 400-500 across 30 teams. Confirmed by hitting the real client: with
# no pacing at all, stats.nba.com starts read-timing-out requests well before
# that count (observed directly while building this). Even with this client's
# existing per-request retry/backoff (see live_client/client.py), that's
# request *volume* hitting a rate limit, not transient network flakiness --
# retrying the same request faster doesn't fix it. This delay is the fix;
# 0.6s keeps a full refresh under ~6 minutes, acceptable for an offline job.
REQUEST_PACING_SECONDS = 0.6


def current_roster_season_start_year() -> int:
    """Default season for a *roster* fetch, when the caller doesn't already
    know which season win_model is forecasting (train.py passes that
    explicitly instead -- see its roster-projection wiring section). July, not
    October: refresh_player_ratings.current_nba_season() uses an October
    cutoff because it answers "which season's box scores exist right now,"
    but free agency and trades reassemble next season's roster all through
    the summer, well before opening night -- by July, "the current roster"
    already means the *upcoming* season, not the one that just finished.
    """
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def is_stale(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> bool:
    """Same contract as refresh_player_ratings.is_stale() -- see that
    docstring. Note the *file's* staleness threshold (default 24h) is
    separate from TeamRoster's own cache TTL (6h, see
    live_client/endpoints/stats/team_roster.py) -- this one governs how often
    the whole projection pipeline re-runs; that one governs how long a single
    team's cached roster response is trusted within a run.
    """
    if not OUTPUT_FILE.exists():
        return True
    try:
        payload = json.loads(OUTPUT_FILE.read_text())
        generated_at = datetime.fromisoformat(payload["generated_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return True
    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age_seconds > max_age_seconds


def _season_string(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def run_refresh(target_season_start_year: int | None = None, write_output: bool = True) -> dict:
    """Fetches every team's real current roster, projects it one season
    forward via the empirical aging curve, and aggregates to the team-level
    talent features win_model's forecast row consumes.

    `target_season_start_year`: e.g. 2026 for the "2026-27" roster. Pass the
    season win_model is actually forecasting (forecast row's Season + 1) so
    this stays correctly synced regardless of when the refresh actually runs
    -- see backend/win_model/train.py. Defaults to
    current_roster_season_start_year() for a standalone manual run.
    """
    start_year = target_season_start_year or current_roster_season_start_year()
    season = _season_string(start_year)
    teams = load_teams()  # team_id, abbreviation, full_name

    with NBAStatsClient() as client:
        rosters: dict[str, pd.DataFrame] = {}
        for i, (_, row) in enumerate(teams.iterrows()):
            if i > 0:
                time.sleep(REQUEST_PACING_SECONDS)
            roster = TeamRoster(team_id=int(row["team_id"]), season=season, client=client).fetch().to_dataframe()
            rosters[row["full_name"]] = roster

        # One PlayerCareerStats call per unique roster player, reused for both
        # "most recent season" (the projection base) and the pooled
        # league-wide aging curve -- see module docstring's "reachable
        # history" note. Paced (see REQUEST_PACING_SECONDS) -- this is ~400-500
        # calls for a full 30-team refresh.
        all_player_ids = sorted({int(pid) for roster in rosters.values() for pid in roster["PLAYER_ID"]})
        careers: dict[int, pd.DataFrame] = {}
        for i, player_id in enumerate(all_player_ids):
            if i > 0:
                time.sleep(REQUEST_PACING_SECONDS)
            careers[player_id] = PlayerCareerStats(player_id=player_id, client=client).fetch().to_dataframe()

    aging_curve = build_aging_curve(list(careers.values()))

    team_features = {}
    player_detail_by_team = {}
    for team_name, roster in rosters.items():
        projections = []
        for player_id, player_name in zip(roster["PLAYER_ID"], roster["PLAYER"]):
            career = careers.get(int(player_id))
            if career is None or career.empty:
                # No career-stats row at all (e.g. just-signed two-way/undrafted
                # player with no NBA box score yet) -- excluded rather than
                # fabricated; n_players below reflects only players we could
                # actually project.
                continue
            proj = project_player_next_season(career, aging_curve)
            proj["player_name"] = player_name
            projections.append(proj)

        if not projections:
            continue
        proj_df = pd.DataFrame(projections)
        team_features[team_name] = project_team_talent_features(proj_df)
        player_detail_by_team[team_name] = proj_df.drop(columns=["player_id"]).to_dict(orient="records")

    payload = {
        "season": season,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aging_curve": {
            str(age): {
                "n_observations": int(row["n_observations"]),
                "median_pct_change": round(float(row["median_pct_change"]), 4),
            }
            for age, row in aging_curve.iterrows()
        },
        "n_players_in_aging_curve_sample": len(all_player_ids),
        "team_features": team_features,
        "player_detail": player_detail_by_team,
    }

    if write_output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2, default=str))

    return payload


if __name__ == "__main__":
    result = run_refresh()
    print(f"Refreshed roster projection for {result['season']} ({len(result['team_features'])} teams)")
    print(f"Wrote {OUTPUT_FILE}")

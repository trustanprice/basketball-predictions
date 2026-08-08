"""backend/live_client/lookups/loader.py

Static player/team ID<->name tables. Not fetched live — see backend/AGENTS.md and
data/AGENTS.md for why this is a client dependency, not historical backtest data.

teams.csv is hand-populated (30 rows, IDs stable for decades — low risk of typos
mattering enough to hand-verify against stats.nba.com before relying on them in
anything beyond local development). players.csv ships as an empty, schema-only
file on purpose: NBA.com has thousands of historical player IDs, and hand-writing
even a sample risks silently wrong IDs corrupting downstream ratings joins. Run
`refresh_players_lookup()` once (needs network) to populate it for real from
NBA.com's own `commonallplayers` endpoint — the actual source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

LOOKUPS_DIR = Path(__file__).resolve().parent
TEAMS_FILE = LOOKUPS_DIR / "teams.csv"
PLAYERS_FILE = LOOKUPS_DIR / "players.csv"


def load_teams() -> pd.DataFrame:
    """Returns columns: team_id, abbreviation, full_name (30 rows)."""
    return pd.read_csv(TEAMS_FILE)


def load_players() -> pd.DataFrame:
    """Returns columns: player_id, full_name, team_id, is_active.

    Empty until `refresh_players_lookup()` has been run once — see module docstring.
    """
    return pd.read_csv(PLAYERS_FILE)


def team_id_for_abbreviation(abbreviation: str) -> int:
    teams = load_teams()
    match = teams.loc[teams["abbreviation"] == abbreviation, "team_id"]
    if match.empty:
        raise KeyError(f"Unknown team abbreviation: {abbreviation!r}")
    return int(match.iloc[0])


def team_name_for_id(team_id: int) -> str:
    teams = load_teams()
    match = teams.loc[teams["team_id"] == team_id, "full_name"]
    if match.empty:
        raise KeyError(f"Unknown team_id: {team_id!r}")
    return match.iloc[0]


def refresh_players_lookup(client=None) -> pd.DataFrame:
    """Populate players.csv from NBA.com's `commonallplayers` endpoint (the same
    source nba_api's own player-index tooling uses). Requires network access —
    not run automatically by anything in this package; call it manually when the
    lookup needs updating (e.g. after a season's roster moves settle)."""
    from ..client import NBAStatsClient
    from ..response import NBAResponse

    owned_client = client is None
    client = client or NBAStatsClient()
    try:
        raw = client.get_json(
            "https://stats.nba.com/stats/commonallplayers",
            params={"LeagueID": "00", "Season": "2024-25", "IsOnlyCurrentSeason": "0"},
        )
    finally:
        if owned_client:
            client.close()

    df = NBAResponse(raw, result_set_name="CommonAllPlayers").to_dataframe()
    players = pd.DataFrame({
        "player_id": df["PERSON_ID"],
        "full_name": df["DISPLAY_FIRST_LAST"],
        "team_id": df["TEAM_ID"],
        "is_active": df["ROSTERSTATUS"].astype(int) == 1,
    })
    players.to_csv(PLAYERS_FILE, index=False)
    return players

"""backend/live_client/lookups/loader.py

Static player/team ID<->name tables. Not fetched live — see backend/AGENTS.md and
data/AGENTS.md for why this is a client dependency, not historical backtest data.

Sourced from nba_api.stats.static (teams/players), not hand-maintained CSVs —
nba_api ships this data bundled with the package (5,103 players, 30 teams,
confirmed by inspection), so keeping a second hand-written copy would just be a
duplicate that can drift. This is genuinely static (no network call — it's data
shipped inside the nba_api package itself), unlike everything else under
live_client/, which is why it's fine to import at module load rather than behind
an Endpoint/fetch()/cache() path.

Note: nba_api's static player records do NOT include team_id (a player's team
affiliation isn't a "static" fact — it's a roster/season fact, which is a
separate, not-yet-built unit of work — see backend/AGENTS.md). Only team_id,
abbreviation, full_name, and player_id, full_name, is_active are covered here.
"""

from __future__ import annotations

import pandas as pd
from nba_api.stats.static import players as _nba_api_players
from nba_api.stats.static import teams as _nba_api_teams


def load_teams() -> pd.DataFrame:
    """Returns columns: team_id, abbreviation, full_name (30 rows)."""
    raw = _nba_api_teams.get_teams()
    return pd.DataFrame({
        "team_id": [t["id"] for t in raw],
        "abbreviation": [t["abbreviation"] for t in raw],
        "full_name": [t["full_name"] for t in raw],
    })


def load_players() -> pd.DataFrame:
    """Returns columns: player_id, full_name, is_active (~5,100 rows, active and
    historical). No team_id — see module docstring."""
    raw = _nba_api_players.get_players()
    return pd.DataFrame({
        "player_id": [p["id"] for p in raw],
        "full_name": [p["full_name"] for p in raw],
        "is_active": [p["is_active"] for p in raw],
    })


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


def player_id_for_name(full_name: str) -> int:
    players = load_players()
    match = players.loc[players["full_name"] == full_name, "player_id"]
    if match.empty:
        raise KeyError(f"Unknown player full_name: {full_name!r}")
    return int(match.iloc[0])

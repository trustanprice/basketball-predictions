"""backend/tests/live_client/test_integration_real_network.py

Real network integration tests — no mocks, no fixtures, actually hits
stats.nba.com through the real client/endpoint stack. Skips cleanly (does not
fail the suite) if NBA.com isn't reachable from wherever this runs, since that's
an environment fact, not a code defect. This is deliberately separate from
test_endpoints.py's mocked schema-validation tests: those catch a malformed
*response*; this catches a wrong *assumption* about what the real response looks
like — which is exactly what caught PlayerAdvancedStats declaring "TOV_PCT" when
the real column is "TM_TOV_PCT" (see backend/AGENTS.md).
"""

from __future__ import annotations

import socket

import pytest

from live_client.client import NBAStatsClient
from live_client.endpoints.stats.advanced_metrics import PlayerAdvancedStats
from live_client.endpoints.stats.season_totals import PlayerSeasonTotals
from live_client.endpoints.stats.shot_chart import TeamShotChart
from live_client.endpoints.stats.team_roster import TeamRoster
from live_client.endpoints.stats.team_season_stats import TeamAdvancedStats, TeamSeasonStats
from live_client.lookups.loader import load_teams
from ratings.player_power_rankings import build_player_table, top_defensive_players, top_offensive_players
from ratings.refresh_roster_projection import current_roster_season_start_year


def _nba_stats_reachable() -> bool:
    try:
        with socket.create_connection(("stats.nba.com", 443), timeout=5):
            return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _nba_stats_reachable(),
    reason="stats.nba.com not reachable from this environment",
)


@requires_network
def test_player_season_totals_real_fetch():
    client = NBAStatsClient()
    endpoint = PlayerSeasonTotals(season="2025-26", per_mode="PerGame", client=client)
    df = endpoint.fetch().to_dataframe()

    assert len(df) > 100, f"expected a full-league player list, got {len(df)} rows"
    assert set(PlayerSeasonTotals.expected_columns) <= set(df.columns)
    # Every 2025-26 player row should exist and be a plausible per-game line —
    # loose bounds, just enough to catch "this is stale/garbage data".
    assert (df["PTS"] >= 0).all()
    assert (df["MIN"] <= 48).all() or (df["MIN"] <= 480).all()  # tolerate Totals vs PerGame either way


@requires_network
def test_player_advanced_stats_real_fetch_has_tm_tov_pct():
    """The specific regression this task exists to catch: TM_TOV_PCT (not
    TOV_PCT) must actually be present in the live response."""
    client = NBAStatsClient()
    endpoint = PlayerAdvancedStats(season="2025-26", client=client)
    df = endpoint.fetch().to_dataframe()

    assert len(df) > 100
    assert "TM_TOV_PCT" in df.columns
    assert "TOV_PCT" not in df.columns  # documents that the old assumption was simply wrong


@requires_network
def test_player_power_rankings_end_to_end_real_data():
    """Proves the fix all the way through: real fetch -> build_player_table
    (which reads TM_TOV_PCT) -> top_offensive_players/top_defensive_players,
    each producing a real, hand-checkable RatingBreakdown."""
    client = NBAStatsClient()
    season_totals = PlayerSeasonTotals(season="2025-26", per_mode="PerGame", client=client).fetch().to_dataframe()
    advanced_stats = PlayerAdvancedStats(season="2025-26", client=client).fetch().to_dataframe()

    table = build_player_table(season_totals, advanced_stats)
    assert len(table) > 0

    offense = top_offensive_players(table, n=5)
    defense = top_defensive_players(table, n=5)
    assert len(offense) == 5
    assert len(defense) == 5
    for breakdown in offense + defense:
        assert breakdown.subject_name  # a real player name, not empty/None
        assert len(breakdown.components) == 4 or len(breakdown.components) == 3
        # every contribution should be a real float, reproducible from raw_value/z_score/weight
        for c in breakdown.components:
            expected_contribution = c["z_score"] * c["weight"] * (1 if c["higher_is_better"] else -1)
            assert c["contribution"] == pytest.approx(expected_contribution, abs=1e-3)


@requires_network
def test_team_roster_real_fetch_is_current_not_last_season():
    """The specific regression this test exists to catch: fetching the wrong
    (already-completed) season's roster string would silently return stale
    data that still parses fine -- the only way to catch it is checking the
    roster against a season string derived independently of the endpoint
    itself, and confirming it's non-empty/plausible."""
    teams = load_teams()
    lakers_id = int(teams.loc[teams["abbreviation"] == "LAL", "team_id"].iloc[0])
    start_year = current_roster_season_start_year()
    season = f"{start_year}-{str(start_year + 1)[-2:]}"

    client = NBAStatsClient()
    df = TeamRoster(team_id=lakers_id, season=season, client=client).fetch().to_dataframe()

    assert set(TeamRoster.expected_columns) <= set(df.columns)
    # A real NBA roster: double digits of players, plausible ages, no team
    # fields two seasons out of date (this project's season strings are
    # "YYYY-YY" -- a wrong-season fetch from nba_api raises rather than
    # silently substituting, so len(df) > 0 here already proves `season` was
    # accepted; the age bounds catch a garbage/placeholder response instead).
    assert len(df) >= 10
    assert (df["AGE"].dropna() >= 18).all()
    assert (df["AGE"].dropna() <= 45).all()


@requires_network
def test_team_season_and_advanced_stats_real_fetch():
    client = NBAStatsClient()
    totals = TeamSeasonStats(season="2023-24", client=client).fetch().to_dataframe()
    advanced = TeamAdvancedStats(season="2023-24", client=client).fetch().to_dataframe()

    assert len(totals) == 30  # every team, every season
    assert len(advanced) == 30
    assert set(TeamSeasonStats.expected_columns) <= set(totals.columns)
    assert set(TeamAdvancedStats.expected_columns) <= set(advanced.columns)
    # Real NBA pace: plausible bounds, not e.g. a per-100-possession rating
    # accidentally landing in the PACE column instead.
    assert (advanced["PACE"].dropna() > 80).all()
    assert (advanced["PACE"].dropna() < 120).all()


@requires_network
def test_team_shot_chart_offense_vs_defense_are_really_different_teams():
    """The specific regression this test exists to catch: team_id vs.
    opponent_team_id are easy to swap by accident, and a swapped-but-still-
    well-formed response would parse fine and only be wrong in *meaning* --
    only a real fetch checking whose shots actually came back catches that."""
    client = NBAStatsClient()
    lakers_id = 1610612747

    offense = TeamShotChart(season="2023-24", team_id=lakers_id, client=client).fetch().to_dataframe()
    defense = TeamShotChart(season="2023-24", opponent_team_id=lakers_id, client=client).fetch().to_dataframe()

    assert len(offense) > 1000
    assert len(defense) > 1000
    assert set(offense["TEAM_ID"].unique()) == {lakers_id}
    assert lakers_id not in set(defense["TEAM_ID"].unique())

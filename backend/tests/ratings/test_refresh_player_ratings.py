import json
from datetime import datetime, timedelta, timezone

import pytest

from ratings import refresh_player_ratings


@pytest.fixture(autouse=True)
def _isolated_output_file(tmp_path, monkeypatch):
    """Every test gets its own OUTPUT_FILE so nothing here can touch the real
    backend/outputs/player_power_rankings.json."""
    fake_path = tmp_path / "player_power_rankings.json"
    monkeypatch.setattr(refresh_player_ratings, "OUTPUT_FILE", fake_path)
    return fake_path


def test_is_stale_true_when_file_missing():
    assert refresh_player_ratings.is_stale() is True


def test_is_stale_false_for_fresh_file(_isolated_output_file):
    payload = {"generated_at": datetime.now(timezone.utc).isoformat()}
    _isolated_output_file.write_text(json.dumps(payload))
    assert refresh_player_ratings.is_stale(max_age_seconds=3600) is False


def test_is_stale_true_for_old_file(_isolated_output_file):
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    _isolated_output_file.write_text(json.dumps({"generated_at": old.isoformat()}))
    assert refresh_player_ratings.is_stale(max_age_seconds=24 * 60 * 60) is True


def test_is_stale_true_for_malformed_file(_isolated_output_file):
    _isolated_output_file.write_text("not valid json")
    assert refresh_player_ratings.is_stale() is True


def test_is_stale_true_when_generated_at_missing(_isolated_output_file):
    _isolated_output_file.write_text(json.dumps({"season": "2025-26"}))
    assert refresh_player_ratings.is_stale() is True


def test_current_nba_season_format():
    season = refresh_player_ratings.current_nba_season()
    start_str, end_str = season.split("-")
    assert len(start_str) == 4 and len(end_str) == 2
    assert int(end_str) == (int(start_str) + 1) % 100


def test_current_nba_season_known_dates(monkeypatch):
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 11, 15, tzinfo=tz)  # Nov -> season start year = 2025

    monkeypatch.setattr(refresh_player_ratings, "datetime", _FixedDatetime)
    assert refresh_player_ratings.current_nba_season() == "2025-26"

    class _FixedDatetimeOffseason(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 1, tzinfo=tz)  # March -> still season starting 2025

    monkeypatch.setattr(refresh_player_ratings, "datetime", _FixedDatetimeOffseason)
    assert refresh_player_ratings.current_nba_season() == "2025-26"

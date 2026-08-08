"""In-game NBA.com live endpoints (cdn.nba.com)."""

from .live_boxscore import LiveBoxScore
from .scoreboard import TodaysScoreboard

__all__ = ["TodaysScoreboard", "LiveBoxScore"]

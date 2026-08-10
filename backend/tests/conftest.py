import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

# backend/AGENTS.md: tests run with `pytest` from backend/ and import packages as
# top-level (`from win_model...`), matching the notebook-style import root. Make
# that work regardless of whether pytest is invoked as `pytest` or `python -m pytest`,
# and regardless of the invocation's cwd.
sys.path.insert(0, str(BACKEND_DIR))

# backend/api/ and backend/ratings/refresh_player_ratings.py are repo-root-context
# only (never imported from notebooks) and use absolute `backend.X` imports to
# reach sibling top-level packages (e.g. live_client) — see backend/AGENTS.md's
# Imports section. Add repo root too, so tests can import them the same way
# uvicorn/the cron job does, without affecting the backend/-root imports above.
sys.path.insert(0, str(REPO_ROOT))

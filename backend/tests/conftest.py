import sys
from pathlib import Path

# backend/AGENTS.md: tests run with `pytest` from backend/ and import packages as
# top-level (`from win_model...`), matching the notebook-style import root. Make
# that work regardless of whether pytest is invoked as `pytest` or `python -m pytest`,
# and regardless of the invocation's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

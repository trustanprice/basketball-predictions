from pathlib import Path
import os, glob, itertools
import pandas as pd
from src.utils import team_map, nba_teams

# ---------- Project paths (defaults) ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]      # repo root (…/Basketball-Predictions)
DATA_RAW     = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED   = PROJECT_ROOT / "data" / "processed"
TEAM_STATS_DIR   = DATA_RAW / "team-stats"
PLAYER_STATS_DIR = DATA_RAW / "player-stats"
MASTER_STATS_DIR = DATA_RAW / "master-stats"

# TEAM STATS
TEAM_RECORDS_FILE = TEAM_STATS_DIR / "team-records.csv"
TEAM_STATS_FILE   = TEAM_STATS_DIR / "team-stats.csv"
COACH_FILE        = TEAM_STATS_DIR / "coach.csv"
DRAFT_FILE        = TEAM_STATS_DIR / "draft.csv"
PAYROLL_FILE      = TEAM_STATS_DIR / "team-payroll.csv"
SOS_FILE          = TEAM_STATS_DIR / "team-sos.csv"

# STREAMLIT APP
RESULTS_FILE      = MASTER_STATS_DIR / "results_2025.csv"
HEADSHOT_PATH     = DATA_PROCESSED / "fa25-headshot.JPG"
LOGO_PATH         = DATA_PROCESSED / "logo.png"

def _ensure_exists(p: Path, kind="file"):
    if not p.exists():
        raise FileNotFoundError(f"Expected {kind} at: {p}\n"
                                f"Tip: adjust PROJECT_ROOT or pass an explicit path.")

def load_team_records(path: str | Path = TEAM_RECORDS_FILE) -> pd.DataFrame:
    p = Path(path)
    _ensure_exists(p)
    df = pd.read_csv(p)

    split_cols = ["Home", "Road", "E", "W", "Pre-ASG", "Post-ASG"]
    for col in split_cols:
        # be defensive if a column is missing
        if col in df.columns:
            df[[f"{col}_W", f"{col}_L"]] = df[col].str.split("-", expand=True).astype(int)
    df = df.drop(columns=[c for c in split_cols if c in df.columns])
    return df

def load_team_stats(path: str | Path = TEAM_STATS_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p); return pd.read_csv(p)

def load_final_results(path: str | Path = RESULTS_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p); return pd.read_csv(p)

def merge_team_data(stats_df: pd.DataFrame, records_df: pd.DataFrame) -> pd.DataFrame:
    return pd.merge(stats_df, records_df, on=["Team", "Season"], how="outer")

def load_coaches(path: str | Path = COACH_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p)
    df = pd.read_csv(p)
    if "Tm" in df.columns:
        df["Team"] = df["Tm"].map(team_map)
        df = df.drop(columns=["Tm"])
    return df

def load_draft(path: str | Path = DRAFT_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p)
    df = pd.read_csv(p)
    if "Tm" in df.columns:
        df["Team"] = df["Tm"].map(team_map)
        df = df.drop(columns=["Tm"])
    df["Pk"] = pd.to_numeric(df["Pk"], errors="coerce")
    df["FirstRound"]  = (df["Pk"] <= 30).astype(int)
    df["SecondRound"] = (df["Pk"] >  30).astype(int)
    draft_df_cleaned = (
        df.groupby(["Season", "Team"], as_index=False)
          .agg(FirstRoundPicks=("FirstRound","sum"),
               SecondRoundPicks=("SecondRound","sum"))
    )
    all_seasons = draft_df_cleaned["Season"].unique()
    full_index  = pd.DataFrame(list(itertools.product(all_seasons, nba_teams)),
                               columns=["Season","Team"])
    draft_df_full = pd.merge(full_index, draft_df_cleaned, on=["Season","Team"], how="left")
    draft_df_full[["FirstRoundPicks","SecondRoundPicks"]] = \
        draft_df_full[["FirstRoundPicks","SecondRoundPicks"]].fillna(0).astype(int)
    return draft_df_full

def load_payroll(path: str | Path = PAYROLL_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p)
    df = pd.read_csv(p)
    df["Team"] = df["Team"].str.strip()  # fix stray spaces
    payroll_long = df.melt(id_vars=["Team"], var_name="Season", value_name="Payroll")
    payroll_long["Season"] = payroll_long["Season"].astype(int)
    return payroll_long

def load_players(path: str | Path = PLAYER_STATS_DIR) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p, kind="folder")
    files = sorted(glob.glob(str(p / "*-player-stats.csv")))
    if not files:
        raise FileNotFoundError(f"No '*-player-stats.csv' files found under {p}")
    dfs = []
    for file in files:
        season = int(Path(file).name.split("-")[0])
        dfx = pd.read_csv(file)
        dfx["Season"] = season
        dfs.append(dfx)
    players_df = pd.concat(dfs, ignore_index=True)
    players_df = players_df[~players_df["Team"].isin(["2TM","3TM","4TM"])]
    players_df["Team"] = players_df["Team"].map(team_map).fillna(players_df["Team"])
    return players_df

def load_sos(path: str | Path = SOS_FILE) -> pd.DataFrame:
    p = Path(path); _ensure_exists(p)
    df = pd.read_csv(p)
    # Only rename columns that match acronyms in team_map
    rename_subset = {k: v for k, v in team_map.items() if k in df.columns}
    if rename_subset:
        df = df.rename(columns=rename_subset)
    return df

# ======================
# FRONT OFFICE MERGE
# ======================

def merge_front_office(
    coach_df: pd.DataFrame,
    draft_df: pd.DataFrame,
    team_payroll_df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """
    Merge coaches, draft data, and (optionally) payroll on Team and Season.
    Adds Coach_Count (distinct coaches per team/season).
    """
    # Merge coach + draft
    front_office_df = pd.merge(
        coach_df,
        draft_df,
        on=["Team", "Season"],
        how="inner"
    )

    # Add Coach_Count
    coach_counts = (
        coach_df.groupby(["Team", "Season"])["Coach"]
        .nunique()
        .reset_index()
        .rename(columns={"Coach": "Coach_Count"})
    )
    front_office_df = pd.merge(
        front_office_df,
        coach_counts,
        on=["Team", "Season"],
        how="left"
    )

    # Optionally merge payroll
    if team_payroll_df is not None:
        front_office_df = pd.merge(
            front_office_df,
            team_payroll_df,
            on=["Team", "Season"],
            how="left"
        )

    return front_office_df





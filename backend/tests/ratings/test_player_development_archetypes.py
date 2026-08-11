import pandas as pd
import pytest

from ratings.player_development import (
    MIN_TOTAL_SEASONS_FOR_ADJUSTMENT,
    ALL_ARCHETYPES_FALLBACK,
    build_archetype_curves,
    classify_archetype,
    project_player_multistat,
)


def test_classify_archetype_rim_reliant():
    assert classify_archetype(rim_rate=0.5, three_pt_rate=0.05) == "Rim-Reliant"


def test_classify_archetype_perimeter():
    assert classify_archetype(rim_rate=0.1, three_pt_rate=0.6) == "Perimeter"


def test_classify_archetype_balanced():
    assert classify_archetype(rim_rate=0.2, three_pt_rate=0.2) == "Balanced"


def test_classify_archetype_rim_checked_before_perimeter():
    # A center who takes almost nothing but rim shots and zero 3s -- must
    # not fall through to "Perimeter" by elimination.
    assert classify_archetype(rim_rate=0.6, three_pt_rate=0.0) == "Rim-Reliant"


def test_classify_archetype_unknown_shot_profile_is_balanced():
    assert classify_archetype(rim_rate=float("nan"), three_pt_rate=0.3) == "Balanced"


def _panel_row(player_id, season, age, archetype, gp=70, **stats):
    row = {"PLAYER_ID": player_id, "SEASON_ID": str(season), "PLAYER_AGE": age, "GP": gp, "ARCHETYPE": archetype}
    row.update(stats)
    return row


# Five "Rim-Reliant" players, identical engineered trend: flat TS_PCT at
# 24->25, then an exact -10% drop at 25->26 -- five observations meets
# MIN_OBSERVATIONS_PER_ARCHETYPE_AGE_BIN (5) exactly, so both bins are
# populated and hand-checkable: 0.0 at age 24, -0.10 at age 25.
RIM_RELIANT_PANEL = pd.DataFrame([
    _panel_row(100 + i, 2016 + s, 24 + s, "Rim-Reliant", TS_PCT=ts)
    for i in range(5)
    for s, ts in enumerate([0.60, 0.60, 0.54])
])

# Only two "Perimeter" players -- below the observation-count floor, so the
# archetype-specific cell must not survive, only the pooled "All" one.
PERIMETER_PANEL = pd.DataFrame([
    _panel_row(200 + i, 2016 + s, 24 + s, "Perimeter", TS_PCT=ts)
    for i in range(2)
    for s, ts in enumerate([0.58, 0.58, 0.61])
])

FULL_PANEL = pd.concat([RIM_RELIANT_PANEL, PERIMETER_PANEL], ignore_index=True)


def test_build_archetype_curves_recovers_engineered_trend_per_archetype():
    curves = build_archetype_curves(FULL_PANEL, stat_columns=("TS_PCT",))
    ts_curve = curves["TS_PCT"]
    assert ts_curve.loc[("Rim-Reliant", 25), "median_pct_change"] == pytest.approx(-0.10)
    assert ts_curve.loc[("Rim-Reliant", 25), "n_observations"] == 5


def test_build_archetype_curves_drops_thin_archetype_cells_but_keeps_pooled():
    curves = build_archetype_curves(FULL_PANEL, stat_columns=("TS_PCT",))
    ts_curve = curves["TS_PCT"]
    # Only 2 Perimeter observations at age 25 -- below the floor, dropped.
    assert ("Perimeter", 25) not in ts_curve.index
    # But the pooled "All" curve at age 25 must exist (5 Rim-Reliant + 2
    # Perimeter = 7 pooled observations, above the floor).
    assert (ALL_ARCHETYPES_FALLBACK, 25) in ts_curve.index


def test_project_player_multistat_uses_own_archetype_when_available():
    curves = build_archetype_curves(FULL_PANEL, stat_columns=("TS_PCT",))
    # A 6th Rim-Reliant player, 3 total seasons on record (meets
    # MIN_TOTAL_SEASONS_FOR_ADJUSTMENT), currently age 25.
    history = pd.DataFrame([_panel_row(999, 2015 + s, 23 + s, "Rim-Reliant", TS_PCT=0.60) for s in range(3)])
    result = project_player_multistat(history, curves, archetype="Rim-Reliant", stat_columns=("TS_PCT",))

    assert result["TS_PCT_adjustment_applied"] is True
    assert result["projected_TS_PCT"] == pytest.approx(0.60 * 0.90)
    assert result["development_notes"] == {}


def test_project_player_multistat_falls_back_to_pooled_archetype_and_flags_it():
    curves = build_archetype_curves(FULL_PANEL, stat_columns=("TS_PCT",))
    # A Perimeter player at the same age, 3 total seasons on record -- too
    # few Perimeter-specific observations, must fall back to the pooled
    # curve and say so.
    history = pd.DataFrame([_panel_row(998, 2015 + s, 23 + s, "Perimeter", TS_PCT=0.58) for s in range(3)])
    result = project_player_multistat(history, curves, archetype="Perimeter", stat_columns=("TS_PCT",))

    assert result["TS_PCT_adjustment_applied"] is True
    assert "TS_PCT" in result["development_notes"]
    assert "all-archetype curve" in result["development_notes"]["TS_PCT"]


def test_project_player_multistat_no_adjustment_for_thin_personal_history():
    curves = build_archetype_curves(FULL_PANEL, stat_columns=("TS_PCT",))
    assert MIN_TOTAL_SEASONS_FOR_ADJUSTMENT == 3
    history = pd.DataFrame([_panel_row(997, 2020, 25, "Rim-Reliant", TS_PCT=0.60)])  # 1 season on record
    result = project_player_multistat(history, curves, archetype="Rim-Reliant", stat_columns=("TS_PCT",))

    assert result["TS_PCT_adjustment_applied"] is False
    assert result["projected_TS_PCT"] == pytest.approx(0.60)


def test_project_player_multistat_requires_at_least_one_season():
    with pytest.raises(ValueError):
        project_player_multistat(pd.DataFrame(), {}, archetype="Balanced")

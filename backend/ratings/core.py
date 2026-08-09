"""backend/ratings/core.py

Shared z-score/weighted-composite engine for backend/ratings/. Every number this
package produces must be reproducible by hand: raw value -> z-score -> weight ->
contribution -> summed composite. This module is that scaffolding, used by both
player_power_rankings.py and coaching_eval.py so neither duplicates it — see
backend/AGENTS.md's ratings/ conventions.

This module never makes HTTP calls and never imports from live_client or
win_model — it's pure computation over whatever dataframe its caller hands it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Component:
    """One weighted input into a composite rating.

    name : label shown in the explanation (e.g. "True Shooting %").
    column : the dataframe column this reads from.
    weight : contribution weight — all components of one composite must sum to 1.0.
    higher_is_better : if False, the z-score is negated before weighting (e.g.
        turnover rate — a *lower* number is the good direction).
    """
    name: str
    column: str
    weight: float
    higher_is_better: bool = True


def zscore(series: pd.Series) -> pd.Series:
    """(x - mean) / population std, over whatever population `series` contains
    (the caller decides the comparison group — e.g. "qualified players this
    season," not literally every player in NBA history).

    A zero-variance column (every subject identical on this input) returns all
    zeros rather than dividing by zero — it contributes nothing to the ranking,
    which is the correct behavior when an input can't discriminate between subjects.
    """
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


@dataclass
class RatingBreakdown:
    """The full, hand-reproducible trail behind one composite score. Every field
    here is exactly what backend/AGENTS.md requires be reconstructable: raw input,
    z-score, weight, and each component's contribution to the total."""
    subject_id: object
    subject_name: str
    composite_score: float
    components: list = field(default_factory=list)  # list[dict]: name, column, raw_value, z_score, weight, higher_is_better, contribution

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "composite_score": round(float(self.composite_score), 4),
            "components": self.components,
        }


def compute_composite(
    df: pd.DataFrame,
    components: list[Component],
    id_col: str,
    name_col: str,
) -> tuple[pd.Series, list[RatingBreakdown]]:
    """Z-scores each component's column across `df`, applies its weight (negated
    when higher_is_better=False), and sums to one composite score per row.

    Returns (composite scores aligned to df.index, one RatingBreakdown per row).
    Raises ValueError if the weights don't sum to ~1.0 — silently renormalizing
    would make the documented weights lie about what's actually driving the score.
    """
    if df.empty:
        raise ValueError("compute_composite got an empty dataframe")

    total_weight = sum(c.weight for c in components)
    if not np.isclose(total_weight, 1.0, atol=1e-6):
        raise ValueError(f"Component weights must sum to 1.0, got {total_weight}")

    signed_z = {}
    raw_z = {}
    for c in components:
        z = zscore(df[c.column])
        raw_z[c.name] = z
        signed_z[c.name] = z if c.higher_is_better else -z

    composite = pd.Series(0.0, index=df.index)
    for c in components:
        composite = composite + signed_z[c.name] * c.weight

    breakdowns = []
    for idx in df.index:
        comp_rows = [
            {
                "name": c.name,
                "column": c.column,
                "raw_value": df.at[idx, c.column],
                "z_score": round(float(raw_z[c.name].at[idx]), 4),
                "weight": c.weight,
                "higher_is_better": c.higher_is_better,
                "contribution": round(float(signed_z[c.name].at[idx] * c.weight), 4),
            }
            for c in components
        ]
        breakdowns.append(RatingBreakdown(
            subject_id=df.at[idx, id_col],
            subject_name=df.at[idx, name_col],
            composite_score=composite.at[idx],
            components=comp_rows,
        ))

    return composite, breakdowns

"""Ability-based probability adjustment and Top1 eligibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

ThresholdMode = Literal["none", "soft", "hard", "zero_tilt"]
ThresholdScope = Literal["all", "female_only"]


@dataclass(frozen=True)
class AbilityThreshold:
    mode: ThresholdMode = "none"
    strength: float = 0.0
    scope: ThresholdScope = "all"
    threshold_offset: float = 0.0

    def __post_init__(self) -> None:
        if self.mode not in ("none", "soft", "hard", "zero_tilt"):
            raise ValueError(f"unsupported ability-threshold mode: {self.mode}")
        if self.scope not in ("all", "female_only"):
            raise ValueError(f"unsupported ability-threshold scope: {self.scope}")
        if not np.isfinite(self.strength) or self.strength < 0:
            raise ValueError("ability-threshold strength must be finite and non-negative")
        if not np.isfinite(self.threshold_offset):
            raise ValueError("ability-threshold offset must be finite")


def adjust_probabilities(
    frame: pd.DataFrame,
    prob_col: str,
    rule: AbilityThreshold,
    race_col: str = "race_id",
    ability_col: str = "ability_z",
    requirement_col: str = "required_ability_z",
    female_only_col: str = "female_only",
) -> pd.DataFrame:
    """Return normalized probabilities and a separate Top1 eligibility mask.

    Hard exclusions only affect purchase selection. They never set a horse's
    predicted win probability to zero. The explicit ``zero_tilt`` mode does
    assign zero below its ability cutoff; missing inputs remain eligible.
    """
    required = {race_col, prob_col, ability_col, requirement_col, female_only_col}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise KeyError(f"missing ability-threshold input columns: {', '.join(missing)}")
    out = frame.copy()
    probabilities = pd.to_numeric(out[prob_col], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or (probabilities < 0).any():
        raise ValueError("probabilities must be finite and non-negative")
    totals = pd.Series(probabilities, index=out.index).groupby(out[race_col]).transform("sum")
    if (totals <= 0).any():
        raise ValueError("each race must have positive total probability")
    probabilities = probabilities / totals.to_numpy()

    ability = pd.to_numeric(out[ability_col], errors="coerce").to_numpy(dtype=float)
    requirement = pd.to_numeric(out[requirement_col], errors="coerce").to_numpy(dtype=float)
    female_only = out[female_only_col].fillna(False).astype(bool).to_numpy()
    applies = np.ones(len(out), dtype=bool)
    if rule.scope == "female_only":
        applies = female_only
    shortfall = requirement - ability
    known = np.isfinite(ability) & np.isfinite(requirement) & applies

    scores = probabilities.copy()
    eligible = np.ones(len(out), dtype=bool)
    threshold_fallback = np.zeros(len(out), dtype=bool)
    if rule.mode == "soft" and rule.strength:
        log_scores = np.log(np.clip(probabilities, 1e-15, 1.0))
        log_scores[known] -= rule.strength * np.square(np.maximum(shortfall[known], 0.0))
        grouped = pd.Series(log_scores, index=out.index)
        maxima = grouped.groupby(out[race_col]).transform("max").to_numpy()
        weights = np.exp(grouped.to_numpy() - maxima)
        totals = pd.Series(weights, index=out.index).groupby(out[race_col]).transform("sum")
        scores = weights / totals.to_numpy()
    elif rule.mode == "hard":
        eligible[known] = shortfall[known] <= rule.strength
    elif rule.mode == "zero_tilt":
        excess = ability - requirement - rule.threshold_offset
        eligible[known] = excess[known] >= 0.0
        log_scores = np.full(len(out), -np.inf, dtype=float)
        positive_probabilities = probabilities > 0
        log_scores[positive_probabilities] = np.log(probabilities[positive_probabilities])
        tilt = np.minimum(rule.strength * np.maximum(excess, 0.0), 700.0)
        log_scores[known] += tilt[known]
        log_scores[~known & positive_probabilities] = np.log(probabilities[~known & positive_probabilities])
        log_scores[~eligible] = -np.inf

        grouped = pd.Series(log_scores, index=out.index)
        maxima = grouped.groupby(out[race_col]).transform("max").to_numpy()
        fallback = ~np.isfinite(maxima)
        if fallback.any():
            fallback_races = out.loc[fallback, race_col].unique()
            fallback_mask = out[race_col].isin(fallback_races).to_numpy()
            eligible[fallback_mask] = True
            threshold_fallback[fallback_mask] = True
            log_scores[fallback_mask] = -np.inf
            positive_fallback = fallback_mask & (probabilities > 0)
            log_scores[positive_fallback] = np.log(probabilities[positive_fallback])
            grouped = pd.Series(log_scores, index=out.index)
            maxima = grouped.groupby(out[race_col]).transform("max").to_numpy()
        weights = np.exp(log_scores - maxima)
        totals = pd.Series(weights, index=out.index).groupby(out[race_col]).transform("sum")
        scores = weights / totals.to_numpy()

    out["adjusted_probability"] = scores
    out["candidate_eligible"] = eligible
    out["threshold_fallback"] = threshold_fallback
    out["ability_shortfall"] = np.where(known, shortfall, np.nan)
    return out


def select_top1(
    frame: pd.DataFrame,
    prob_col: str = "adjusted_probability",
    race_col: str = "race_id",
    number_col: str = "umaban",
) -> pd.DataFrame:
    """Choose highest-scoring eligible runner, falling back safely if none qualify."""
    required = {race_col, prob_col, number_col, "candidate_eligible"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise KeyError(f"missing Top1 selection columns: {', '.join(missing)}")
    out = frame.copy()
    out["_number_order"] = pd.to_numeric(out[number_col], errors="coerce")
    has_candidate = out["candidate_eligible"].astype(bool).groupby(out[race_col]).transform("any")
    out["_selectable"] = out["candidate_eligible"].astype(bool) | ~has_candidate
    out["eligibility_fallback"] = ~has_candidate
    selected = out.sort_values(
        [race_col, "_selectable", prob_col, "_number_order"],
        ascending=[True, False, False, True],
        kind="stable",
    ).drop_duplicates(race_col, keep="first")
    return selected.drop(columns=["_selectable", "_number_order"]).reset_index(drop=True)

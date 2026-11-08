"""Derive past-run sectional labels without inventing missing observations."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

TIME_COLUMN: Final = "time_sec"
LAST3F_COLUMN: Final = "last3f_sec"


def derive_sectional_features(
    runs: pd.DataFrame,
    race_column: str = "race_id",
    time_column: str = TIME_COLUMN,
    last3f_column: str = LAST3F_COLUMN,
) -> pd.DataFrame:
    """Return E=T-L3 and the observed-field gap at 600m, preserving invalid values as missing.

    The completeness flag applies to the rows supplied by the caller. If those rows omit
    non-finishers, it does not claim that their position at 600m is known.
    """
    required = {race_column, time_column, last3f_column}
    missing = required.difference(runs.columns)
    if missing:
        raise ValueError(f"missing sectional input columns: {sorted(missing)}")
    if runs[race_column].isna().any():
        raise ValueError(f"{race_column} must not contain missing values")

    result = runs.copy()
    time = pd.to_numeric(result[time_column], errors="coerce")
    last3f = pd.to_numeric(result[last3f_column], errors="coerce")
    valid_time = np.isfinite(time) & (time > 0)
    valid_last3f = np.isfinite(last3f) & (last3f > 0)
    valid = valid_time & valid_last3f & (last3f < time)

    result["early_elapsed_sec"] = (time - last3f).where(valid)
    result["sectional_quality_flag"] = np.select(
        [
            ~valid_time,
            valid_time & ~valid_last3f,
            valid_time & valid_last3f & (last3f >= time),
        ],
        ["invalid_finish_time", "missing_last3f", "invalid_last3f"],
        default="valid",
    )
    grouped = result.assign(_valid_early=result["early_elapsed_sec"].notna()).groupby(
        race_column, sort=False, dropna=False
    )
    observed_min = result.groupby(race_column, sort=False)["early_elapsed_sec"].transform("min")
    result["gap_to_leader_600_sec"] = (result["early_elapsed_sec"] - observed_min).where(
        result["early_elapsed_sec"].notna()
    )
    result["leader_observed_complete"] = grouped["_valid_early"].transform("all").astype(bool)
    return result

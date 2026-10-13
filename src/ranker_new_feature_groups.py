"""Definitions and validation helpers for the four experimental Ranker groups.

The production feature list is imported but never mutated.  This module only
describes experiment columns and the 16 pre-registered ON/OFF configurations.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable

from .backtest import RANKER_MARGIN_CORRECTION_FEATURES


GROUPS: dict[str, tuple[str, ...]] = {
    "G1": (
        "horse_course_aptitude",
        "horse_distance_aptitude",
        "horse_course_distance_aptitude",
        "horse_distance_delta_aptitude",
        "horse_distance_change",
        "horse_same_course_distance_experience",
        "horse_course_aptitude_sample_count",
        "horse_course_distance_sample_count",
    ),
    "G2": (
        "horse_surface_aptitude",
        "horse_condition_aptitude",
        "horse_surface_change",
        "horse_condition_sample_count",
        "surface_aptitude_sample_count",
        "horse_distance_delta_sample_count",
    ),
    "G3": (
        "jockey_rides",
        "jockey_win_rate",
        "jockey_place_rate",
        "jockey_recent_added_value",
        "jockey_pair_aptitude",
        "jockey_pair_sample_count",
        "jockey_condition_aptitude",
        "jockey_condition_sample_count",
        "jockey_condition_match",
    ),
    "G4": (
        "performance_slope_last3",
        "performance_change_last3",
        "performance_volatility_last5",
        "performance_peak_delta",
        "performance_trend_confidence",
        "age_x_performance_trend",
        "layoff_days",
        "layoff_x_performance_change",
    ),
}

GROUP_NAMES = {
    "G1": "馬自身の距離・コース適性",
    "G2": "芝・ダート・馬場状態適性",
    "G3": "騎手能力・騎手と馬の相性",
    "G4": "馬の成長・衰退・能力変化",
}
GROUP_KEYS = tuple(GROUPS)
BASELINE_FEATURES = tuple(RANKER_MARGIN_CORRECTION_FEATURES)
EXPERIMENT_FEATURES = tuple(dict.fromkeys(BASELINE_FEATURES + tuple(
    feature for group in GROUP_KEYS for feature in GROUPS[group]
)))


@dataclass(frozen=True)
class Configuration:
    index: int
    mask: str
    enabled_groups: tuple[str, ...]
    features: tuple[str, ...]


def configuration_mask(index: int) -> str:
    if not 0 <= index < 16:
        raise ValueError(f"configuration index must be in [0, 15], got {index}")
    return "".join("1" if index & (1 << position) else "0" for position in range(4))


def configuration_features(mask: str) -> tuple[str, ...]:
    if len(mask) != 4 or any(bit not in "01" for bit in mask):
        raise ValueError(f"configuration mask must be four binary characters, got {mask!r}")
    enabled = {key for key, bit in zip(GROUP_KEYS, mask) if bit == "1"}
    return BASELINE_FEATURES + tuple(
        feature for key in GROUP_KEYS for feature in GROUPS[key] if key in enabled
    )


def configurations() -> tuple[Configuration, ...]:
    return tuple(
        Configuration(
            index=index,
            mask=configuration_mask(index),
            enabled_groups=tuple(key for key, bit in zip(GROUP_KEYS, configuration_mask(index)) if bit == "1"),
            features=configuration_features(configuration_mask(index)),
        )
        for index in range(16)
    )


def validate_catalog(available_features: Iterable[str] | None = None) -> dict:
    available = set(available_features) if available_features is not None else None
    experimental = {feature for group in GROUPS.values() for feature in group}
    bloodline = tuple(feature for feature in EXPERIMENT_FEATURES if any(
        token in feature.lower() for token in ("sire", "dam", "blood", "pedigree")
    ))
    return {
        "baseline_count": len(BASELINE_FEATURES),
        "experimental_count": len(experimental),
        "duplicate_experimental_features": sorted(
            feature for feature in experimental
            if sum(feature in group for group in GROUPS.values()) > 1
        ),
        "bloodline_features": list(bloodline),
        "missing_from_source": sorted(experimental - available) if available is not None else [],
        "configuration_count": len(configurations()),
        "ok": (
            len(BASELINE_FEATURES) == 86
            and not bloodline
            and not any(feature in BASELINE_FEATURES for feature in experimental)
            and (available is None or experimental <= available)
        ),
    }


def feature_quality_summary(frame) -> object:
    """Return a CSV-ready feature quality table without using target columns."""
    rows = []
    for group, features in GROUPS.items():
        for feature in features:
            values = frame[feature] if feature in frame else None
            if values is None:
                rows.append({"group": group, "feature": feature, "available": False})
                continue
            numeric = values
            rows.append({
                "group": group,
                "feature": feature,
                "available": True,
                "missing_rate": float(numeric.isna().mean()),
                "sample_count": int(numeric.notna().sum()),
                "mean": float(numeric.mean()),
                "std": float(numeric.std()),
                "min": float(numeric.min()),
                "max": float(numeric.max()),
                "unique_count": int(numeric.nunique(dropna=True)),
            })
    import pandas as pd
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import json
    print(json.dumps(validate_catalog(), ensure_ascii=False, indent=2))

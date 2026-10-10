"""ペースの5段階表示(ユーザー向け後処理)。内部計算は連続値秒数のまま。閾値は学習期の実ペース偏差の分位点。"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from raceverse.config import PACE_BUCKETS
from raceverse.pace_residuals import group_key


def fit_display_thresholds(groups: np.ndarray, actual_delta: np.ndarray, quantiles: List[float]) -> Dict[str, np.ndarray]:
    """コース群ごとに4つの閾値(昇順)。サンプルの少ない群は '__global__' にフォールバック。"""
    thresholds = {"__global__": _strict(np.quantile(actual_delta, quantiles))}
    for key in np.unique(groups):
        mask = groups == key
        if mask.sum() >= 200:
            thresholds[key] = _strict(np.quantile(actual_delta[mask], quantiles))
    return thresholds


def _strict(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float).copy()
    for i in range(1, len(values)):
        if values[i] <= values[i - 1]:
            values[i] = values[i - 1] + 1e-6
    return values


def thresholds_for(thresholds: Dict[str, np.ndarray], surface: str, distance_m: int) -> np.ndarray:
    return thresholds.get(group_key(surface, distance_m), thresholds["__global__"])


def pace_display_bucket_index(pace_delta_sec: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    """0=VERY_FAST ... 4=VERY_SLOW。数値が小さい(速い)ほど若い番号。"""
    if not np.all(np.diff(thresholds) > 0):
        raise ValueError("thresholds must be strictly increasing")
    return np.searchsorted(thresholds, pace_delta_sec, side="right")


def pace_display_bucket(pace_delta_sec: float, thresholds) -> str:
    return PACE_BUCKETS[int(pace_display_bucket_index(np.asarray([pace_delta_sec]), np.asarray(thresholds))[0])]

"""時系列OOF残差からの連続値ペース抽選(仕様6.6)。

隊列の不確実性はシミュレーション側で別途生成されるため、OOF残差はレース単位(16疑似隊列の予測平均との差)で作り、
隊列由来の分散を二重に数えないよう分散を補正する(kappa)。補正係数・抽選・トランケーションはすべて学習期のデータのみで決める。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

MIN_KAPPA = 0.25


def distance_band(distance_m: int) -> str:
    if distance_m <= 1200:
        return "sprint"
    if distance_m <= 1600:
        return "mile"
    if distance_m <= 2000:
        return "middle"
    return "long"


def group_key(surface: str, distance_m: int) -> str:
    return f"{surface}_{distance_band(distance_m)}"


@dataclass
class PaceBounds:
    """ペース予測値の範囲(学習期の実ペース偏差の分位点)。乱数は使わず、範囲外の外挿だけを丸める。"""
    groups: Dict[str, np.ndarray]
    global_bounds: np.ndarray

    @classmethod
    def fit(cls, groups: np.ndarray, actual_delta: np.ndarray, quantiles: List[float], min_rows: int) -> "PaceBounds":
        bounds = {key: np.quantile(actual_delta[groups == key], quantiles)
                  for key in np.unique(groups) if (groups == key).sum() >= min_rows}
        return cls(bounds, np.quantile(actual_delta, quantiles))

    def for_group(self, key: str) -> np.ndarray:
        return self.groups.get(key, self.global_bounds)

    def clip(self, key: str, pace_delta: np.ndarray) -> np.ndarray:
        lo, hi = self.for_group(key)
        return np.clip(pace_delta, lo, hi)


@dataclass
class PaceResidualSampler:
    pools: Dict[str, np.ndarray]
    global_pool: np.ndarray
    bounds: Dict[str, np.ndarray]       # group -> [lo, hi] 学習期の実ペース偏差の分位点
    global_bounds: np.ndarray
    kappa: float
    min_pool: int
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def fit(
        cls,
        groups: np.ndarray,          # [races] group_key
        residual: np.ndarray,        # [races] y - mean(y_hat over draws)
        draw_variance: np.ndarray,   # [races] 疑似隊列間の予測分散
        actual_delta: np.ndarray,    # [races] 学習期の実ペース偏差
        quantiles: List[float],
        min_pool: int,
    ) -> "PaceResidualSampler":
        var_e = float(np.var(residual))
        kappa = float(np.sqrt(max(1.0 - float(np.mean(draw_variance)) / var_e, MIN_KAPPA ** 2))) if var_e > 0 else 1.0
        kappa = max(kappa, MIN_KAPPA)
        pools, bounds = {}, {}
        for key in np.unique(groups):
            mask = groups == key
            if mask.sum() >= min_pool:
                pools[key] = residual[mask] * kappa
                bounds[key] = np.quantile(actual_delta[mask], quantiles)
        sampler = cls(pools, residual * kappa, bounds, np.quantile(actual_delta, quantiles), kappa, min_pool)
        return sampler

    def pool_for(self, key: str) -> np.ndarray:
        pool = self.pools.get(key)
        if pool is None:
            self.warnings.append(f"pace residual pool for {key} is small; fell back to global pool")
            return self.global_pool
        return pool

    def bounds_for(self, key: str) -> np.ndarray:
        return self.bounds.get(key, self.global_bounds)

    def draw_error(self, rng: np.random.Generator, key: str, size: int) -> np.ndarray:
        return rng.choice(self.pool_for(key), size=size, replace=True)

    def draw(self, rng: np.random.Generator, key: str, mu_delta: np.ndarray) -> np.ndarray:
        """mu_delta[S] + 残差。学習期の分位点範囲外なら再抽選し、最後まで外れたものだけ範囲端に丸める。"""
        lo, hi = self.bounds_for(key)
        draw = mu_delta + self.draw_error(rng, key, mu_delta.shape[0])
        for _ in range(5):
            bad = (draw < lo) | (draw > hi)
            if not bad.any():
                break
            draw[bad] = mu_delta[bad] + self.draw_error(rng, key, int(bad.sum()))
        return np.clip(draw, lo, hi)

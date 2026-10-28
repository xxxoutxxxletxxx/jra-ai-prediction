"""決着時計モデル(仕様8章)。ペース回帰とは別モデル(標準化+Ridge)。

  T_win_mean = T_course_baseline(as-of Ridge) + f(馬場速度bias, 出走馬能力, 連続値ペース, 隊列)
  T_win_sampled = T_win_mean + 時系列OOF残差からの抽選

教師値は「実際の勝ち時計 - 基準時計」。説明変数のペース・隊列は当時の情報だけで作ったOOF予測(実ラップは使わない)。
ペース二次項・コース群交互作用を含め、スロー=遅い/ハイ=速いという直線仮定に縛られない。
レベル(アブレーション): baseline / +track_bias / +field_ability / +pace(=full)。
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from raceverse.schemas import RaceContext, TrackContext

TIME_FEATURES = [
    "track_bias", "bias_n_eff", "ability_max", "ability_top3", "ability_mean", "ability_std", "field_size",
    "pace", "pace_sq", "pace_x_turf", "pace_x_sprint", "pace_x_long",
    "front_group_size", "q_top3", "front_competition", "outside_front_pressure",
]
_I = {n: i for i, n in enumerate(TIME_FEATURES)}
TIME_LEVELS: Dict[str, List[str]] = {
    "baseline": [],
    "track_bias": ["track_bias", "bias_n_eff"],
    "field_ability": ["track_bias", "bias_n_eff", "ability_max", "ability_top3", "ability_mean", "ability_std", "field_size"],
    "full": TIME_FEATURES,
}
FORMATION_COLUMNS = ["front_group_size", "q_top3", "front_competition", "outside_front_pressure"]


def ability_stats(ability: np.ndarray) -> np.ndarray:
    values = np.asarray(ability, dtype=float)
    known = np.isfinite(values)
    default = float(np.median(values[known])) if known.any() else 0.0
    values = np.where(known, values, default)
    s = np.sort(values)[::-1]
    return np.array([s[0], s[:3].mean(), values.mean(), values.std(), len(values)])


def time_features(ctx: RaceContext, track: TrackContext, pace: np.ndarray, formation: np.ndarray) -> np.ndarray:
    """pace: [S] 連続値ペース偏差(秒), formation: [S,4] (FORMATION_COLUMNS順)。戻り値 [S, F]。"""
    s = pace.shape[0]
    out = np.zeros((s, len(TIME_FEATURES)))
    out[:, _I["track_bias"]] = track.track_bias_sec
    out[:, _I["bias_n_eff"]] = np.log1p(track.effective_sample_size)
    a = ability_stats(ctx.ability)
    for name, value in zip(["ability_max", "ability_top3", "ability_mean", "ability_std", "field_size"], a):
        out[:, _I[name]] = value
    out[:, _I["pace"]] = pace
    out[:, _I["pace_sq"]] = pace ** 2
    out[:, _I["pace_x_turf"]] = pace * (1.0 if ctx.surface == "turf" else 0.0)
    out[:, _I["pace_x_sprint"]] = pace * (1.0 if ctx.distance_m <= 1400 else 0.0)
    out[:, _I["pace_x_long"]] = pace * (1.0 if ctx.distance_m >= 2000 else 0.0)
    for j, name in enumerate(FORMATION_COLUMNS):
        out[:, _I[name]] = formation[:, j]
    return out


def level_columns(level: str) -> List[int]:
    return [_I[n] for n in TIME_LEVELS[level]]


class TimeModel:
    """レベルごとのRidge。baseline は説明変数なし(切片=学習期の平均残差のみ)。"""

    def __init__(self, level: str, alpha: float):
        self.level = level
        self.cols = level_columns(level)
        self.alpha = alpha
        self.intercept_ = 0.0
        self.pipe_ = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "TimeModel":
        if not self.cols:
            self.intercept_ = float(np.mean(y))
            return self
        self.pipe_ = Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=self.alpha))])
        self.pipe_.fit(x[:, self.cols], y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.pipe_ is None:
            return np.full(x.shape[0], self.intercept_)
        return self.pipe_.predict(x[:, self.cols])

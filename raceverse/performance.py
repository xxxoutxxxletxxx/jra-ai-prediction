"""各馬の相対走破性能(仕様8.4)。レース内で中心化した「勝ち馬基準ではなく平均基準の時計偏差(秒)」を回帰する。

目的変数 z_i = 馬iの走破時計 - 出走馬の平均走破時計(正=遅い)。説明変数はすべてレース内で中心化:
  ability_c            既存Ranker能力指標
  q_c, slot_c          抽選した序盤位置・グループ内の外寄り度(隊列)
  q_x_pace             序盤位置 x 連続値ペース偏差(前残り/差し有利の展開適性)
  closing_x_pace       過去の上がり相対(代理指標) x ペース偏差
シミュレーションでは共通ショック(ペース・レース内の位置取り有利不利のランダム勾配)と
各馬固有ノイズ(OOF残差の標準化プールから抽選)を分けて与える。時計は個別に決めて着順を作るため、時計順=着順が保証される。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from raceverse.course_bias import bias_feature_block
from raceverse.schemas import RaceContext

GOING_ABILITY_FEATURES = [f"ability_c_x_going_{going}" for going in (2, 3, 4)]
PERF_FEATURES = ["ability_c", "q_c", "slot_c", "q_x_pace", "closing_x_pace"] + GOING_ABILITY_FEATURES
STYLE_DRAW_FEATURES = ["style_win_bias_c", "style_place_bias_c", "draw_win_bias_c", "draw_place_bias_c",
                       "style_draw_interaction_c"]
PACE_BIAS_FEATURES = ["pace_style_win_bias_c", "pace_style_place_bias_c", "pace_draw_interaction_c"]
PERF_FEATURES += STYLE_DRAW_FEATURES + PACE_BIAS_FEATURES
_I = {n: i for i, n in enumerate(PERF_FEATURES)}
PERF_LEVELS: Dict[str, List[str]] = {
    "base": ["ability_c"] + GOING_ABILITY_FEATURES,
    "formation": ["ability_c", "q_c", "slot_c"] + GOING_ABILITY_FEATURES,
    "pace": ["ability_c", "q_c", "slot_c", "q_x_pace", "closing_x_pace"] + GOING_ABILITY_FEATURES,
    # コース別の脚質・枠順バイアスを加えた版(目的変数・既存特徴量は同じ)
    "formation_bias": ["ability_c", "q_c", "slot_c"] + STYLE_DRAW_FEATURES + GOING_ABILITY_FEATURES,
    "pace_bias": ["ability_c", "q_c", "slot_c", "q_x_pace", "closing_x_pace"] + STYLE_DRAW_FEATURES + PACE_BIAS_FEATURES + GOING_ABILITY_FEATURES,
}
PACE_DEPENDENT_LEVELS = ("pace", "pace_bias")
PACELESS_FALLBACK = {"pace": "formation", "pace_bias": "formation_bias"}


def _center(values: np.ndarray) -> np.ndarray:
    return values - values.mean(axis=-1, keepdims=True)


def static_runner_features(ctx: RaceContext) -> Dict[str, np.ndarray]:
    """隊列・ペースに依らない馬ごとの特徴([N])。"""
    ability = ctx.ability.astype(float)
    known_ability = np.isfinite(ability)
    ability_default = float(np.median(ability[known_ability])) if known_ability.any() else 0.0
    ability = np.where(known_ability, ability, ability_default)
    closing = ctx.closing_skill.astype(float)
    closing = np.where(np.isfinite(closing), closing, np.nanmean(closing) if np.isfinite(closing).any() else 0.0)
    return {
        "ability_c": _center(ability),
        "closing_c": _center(closing),
    }


def perf_features(ctx: RaceContext, q_adj: np.ndarray, slot: np.ndarray, pace: np.ndarray) -> np.ndarray:
    """[S,N,F]。q_adj/slot [S,N], pace [S]。"""
    s, n = q_adj.shape
    static = static_runner_features(ctx)
    q_c = _center(q_adj)
    out = np.zeros((s, n, len(PERF_FEATURES)))
    out[:, :, _I["ability_c"]] = static["ability_c"][None, :]
    out[:, :, _I["q_c"]] = q_c
    out[:, :, _I["slot_c"]] = _center(slot.astype(float))
    out[:, :, _I["q_x_pace"]] = q_c * pace[:, None]
    out[:, :, _I["closing_x_pace"]] = static["closing_c"][None, :] * pace[:, None]
    if ctx.going in (2, 3, 4):
        out[:, :, _I[f"ability_c_x_going_{ctx.going}"]] = static["ability_c"][None, :]
    if ctx.bias is not None:
        wakuban = ctx.wakuban if ctx.wakuban is not None else derive_wakuban(ctx.umaban)
        for name, value in bias_feature_block(ctx.bias, wakuban, q_adj, pace).items():
            out[:, :, _I[name]] = _center(value)  # 既存仕様どおりレース内で中心化
    return out


def derive_wakuban(umaban: np.ndarray) -> np.ndarray:
    """枠番が無いときの近似(馬番を頭数に応じて8枠へ)。実データでは出走表の枠番を使う。"""
    n = len(umaban)
    if n <= 8:
        return np.asarray(umaban, dtype=int)
    return np.clip(np.ceil(np.asarray(umaban, dtype=float) * 8.0 / n).astype(int), 1, 8)


def level_indices(level: str) -> List[int]:
    return [_I[n] for n in PERF_LEVELS[level]]


@dataclass
class PerfModel:
    level: str
    coef: np.ndarray
    intercept: float
    sigma0: float
    sigma1: float
    std_pool: np.ndarray        # OOF標準化残差(中心化済み)
    tau_q: float                # 共通ショック: レースごとのq_c勾配のSD
    tau_slot: float
    winsor: np.ndarray
    n_train_rows: int

    def mean_dev(self, features: np.ndarray) -> np.ndarray:
        cols = level_indices(self.level)
        return features[:, :, cols] @ self.coef + self.intercept

    def draw_noise(self, rng: np.random.Generator, mu: np.ndarray) -> np.ndarray:
        rel = mu - mu.min(axis=1, keepdims=True)
        sigma = np.maximum(self.sigma0 + self.sigma1 * rel, 0.05)
        u = rng.choice(self.std_pool, size=mu.shape, replace=True)
        return sigma * u


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float):
    """切片つき閉形式Ridge(切片は非正則化)。"""
    xm, ym = x.mean(axis=0), y.mean()
    xc, yc = x - xm, y - ym
    gram = xc.T @ xc + alpha * np.eye(x.shape[1])
    coef = np.linalg.solve(gram, xc.T @ yc)
    return coef, float(ym - xm @ coef)

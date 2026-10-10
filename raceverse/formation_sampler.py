"""序盤隊列サンプラー(仕様3〜5章)。すべて NumPy でシミュレーション次元(S)にベクトル化する。

  1. 各馬: 過去最大10走から1走を重み付き抽選(1走前・2走前が最大、以降1ずつ減)。コーナー系列は同一走から採用。
  2. 抽選元の騎手と今回の騎手が違う場合だけ、先行度の差で位置を補正。
  3. q昇順にアンカー固定でグループ化(閾値0.08)、グループ内は馬番昇順で内→外。
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from raceverse.config import FormationConfig
from raceverse.schemas import Formation, RaceContext


def history_weights(hist_q: np.ndarray, base_weights: np.ndarray) -> np.ndarray:
    """[N,K] 有効な過去走だけで正規化した重み。有効走が無い馬は全0(コールドスタート)。"""
    k = hist_q.shape[1]
    w = np.where(np.isfinite(hist_q), base_weights[None, :k], 0.0)
    total = w.sum(axis=1, keepdims=True)
    return np.divide(w, total, out=np.zeros_like(w), where=total > 0)


def anchor_groups(q_sorted: np.ndarray, threshold: float) -> np.ndarray:
    """昇順qに対し、先頭(アンカー)から threshold 以内を同グループにする。連鎖的な拡張はしない。"""
    s, n = q_sorted.shape
    group = np.zeros((s, n), dtype=np.int16)
    anchor = q_sorted[:, 0].copy()
    current = np.zeros(s, dtype=np.int16)
    for j in range(1, n):
        new_group = (q_sorted[:, j] - anchor) > threshold
        current = current + new_group.astype(np.int16)
        anchor = np.where(new_group, q_sorted[:, j], anchor)
        group[:, j] = current
    return group


def arrange_formation(q: np.ndarray, threshold: float):
    """q[S,N](馬番昇順の列) -> group, lateral_slot, early_order, q_rank_order。"""
    s, n = q.shape
    order_q = np.argsort(q, axis=1, kind="stable")  # 同値は馬番の小さい方が前
    q_sorted = np.take_along_axis(q, order_q, axis=1)
    group_sorted = anchor_groups(q_sorted, threshold)
    group = np.empty_like(group_sorted)
    np.put_along_axis(group, order_q, group_sorted, axis=1)

    horse_index = np.broadcast_to(np.arange(n), (s, n))
    key = group.astype(np.int32) * (n + 1) + horse_index  # グループ内は馬番昇順
    order_g = np.argsort(key, axis=1, kind="stable")
    group_in_order = np.take_along_axis(group, order_g, axis=1)
    positions = np.broadcast_to(np.arange(n), (s, n))
    change = np.ones((s, n), dtype=bool)
    change[:, 1:] = group_in_order[:, 1:] != group_in_order[:, :-1]
    start = np.maximum.accumulate(np.where(change, positions, 0), axis=1)
    slot_in_order = positions - start
    slot = np.empty_like(slot_in_order)
    np.put_along_axis(slot, order_g, slot_in_order, axis=1)
    early_order = np.empty_like(order_g)
    np.put_along_axis(early_order, order_g, positions.copy(), axis=1)
    return group, slot, early_order, order_q


def sample_formation(
    ctx: RaceContext,
    rng: np.random.Generator,
    n_sims: int,
    cfg: FormationConfig,
    frontness: np.ndarray,
) -> Formation:
    """frontness: jockey_idx で引ける配列(末尾=未知騎手の事前値)。"""
    n = ctx.n
    base_w = np.asarray(cfg.recency_weights, dtype=float)
    weights = history_weights(ctx.hist_q, base_w)
    cold = weights.sum(axis=1) == 0
    cum = np.cumsum(weights, axis=1)
    u = rng.random((n_sims, n))
    idx = (u[:, :, None] > cum[None, :, :]).sum(axis=2)
    idx = np.minimum(idx, weights.shape[1] - 1)
    horse_range = np.arange(n)
    q_hist = np.nan_to_num(ctx.hist_q, nan=0.5)[horse_range[None, :], idx]
    prior_q = rng.random((n_sims, n))  # 履歴なしの明示的事前分布: U(0,1)
    q_sampled = np.where(cold[None, :], prior_q, q_hist)

    sampled_j = ctx.hist_j[horse_range[None, :], idx]
    current_j = ctx.jockey_idx[None, :]
    known = (sampled_j >= 0) & (current_j >= 0) & ~cold[None, :]
    adjusted = known & (sampled_j != current_j)
    f_current = frontness[ctx.jockey_idx][None, :]
    f_sampled = frontness[sampled_j]
    shift = cfg.jockey_change_alpha * (f_current - f_sampled)
    q_adj = np.clip(q_sampled - np.where(adjusted, shift, 0.0), 0.0, 1.0)
    unknown = int(((sampled_j < 0) & ~cold[None, :]).sum())

    group, slot, early_order, order_q = arrange_formation(q_adj, cfg.group_threshold)
    return Formation(q_sampled, q_adj, adjusted, group, slot, early_order, order_q, cold, unknown)

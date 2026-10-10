"""隊列から機械的に生成するペース説明変数(仕様6.3 + Pace Impact改修)。ルールは固定、影響係数は実ラップから回帰で学習する。

入力は「その試行で抽選した隊列」と発走前に確定している情報だけ。当該レースの実通過順位は使わない。
Pace Impact(秒, 負=ペースを速くする)は月次スナップショット(snap)から引く。無ければ0として扱う。
"""

from __future__ import annotations

import warnings
from typing import Dict, List

import numpy as np

from raceverse.schemas import Formation, RaceContext

TRACKS = [f"{i:02d}" for i in range(1, 11)]
LEAD_Q_CUT = 0.15
TOP_K = 5
SHORT_FIRST_TURN_M = 350.0
FRONT_FRAC = 0.25      # 先行集団 = 前方から ceil(25%) 頭(最低 FRONT_MIN 頭)
FRONT_MIN = 3
CONTEST_SCALE = 0.05   # 位置差がこの値で競り合いの重みが 1/e

LEGACY_NUMERIC = [
    "front_group_size", "lead_candidates", "q_top3", "front_competition", "front_q_spread",
    "leader_margin_in_q", "group_size_top2", "outside_front_count", "outside_front_pressure",
    "front_group_avg_horse_no_pct", "lead_horse_number_pct", "leader_jockey_lead_tempo",
    "top3_jockey_lead_tempo", "chaser_tempo", "leader_jockey_frontness", "top3_frontness",
    "distance_km", "first_turn_distance_100m", "field_size", "course_week", "meet_day",
    "season_sin", "season_cos", "is_turf", "short_first_turn",
    "outside_front_pressure_x_short_first_turn", "front_competition_x_short_first_turn",
    "front_group_size_x_turf",
]
LEGACY_JOCKEY = ["leader_jockey_lead_tempo", "top3_jockey_lead_tempo", "chaser_tempo",
                 "leader_jockey_frontness", "top3_frontness"]
# 隊列・コースだけで決まる新特徴(馬・騎手の個体情報を含まない)
NEW_STRUCT = [
    "chase2_q_gap", "chase3_q_gap", "front_cluster_q_range", "front_cluster_q_std", "front_cluster_density",
    "outside_front_ratio", "outside_front_ratio_x_short_first_turn", "outside_front_ratio_x_first_turn",
    "q_p10", "q_p25", "q_p50", "q_p75", "q_std_all", "front_group_ratio", "second_group_ratio",
    "n_groups_ratio", "q_gap_front_to_rest", "lead_candidates_ratio", "n_q_le25_ratio", "n_q_le50_ratio",
]
# 馬の過去位置取り履歴から作る特徴(Pace Impactではない)
NEW_HISTORY = [
    "leader_lead_experience", "chase2_frontness_gap", "chase3_frontness_gap", "contest_lead_rate_index",
    "front_lead_rate_sum", "front_lead_rate_max", "topfront3_mean_q", "topfront3_min_q",
]
# Pace Impact(実ラップ残差の縮小推定)を使う特徴
NEW_IMPACT = [
    "leader_horse_lead_impact", "leader_jockey_lead_impact", "leader_horse_x_jockey_lead",
    "chase2_horse_chase_impact", "chase3_horse_chase_impact", "chase2_jockey_chase_impact",
    "chase3_jockey_chase_impact", "contest_pressure_index",
    "front_impact_mean", "front_impact_sum", "front_impact_min", "front_impact_max", "front_impact_fast2_mean",
    "front_impact_neg_sum", "front_impact_pos_sum", "front_jockey_impact_mean", "front_jockey_impact_sum",
    "front_jockey_impact_min", "outside_front_impact_pressure", "inside_front_impact_pressure",
    "inout_pressure_diff", "fast_pressure_outside_share", "outside_front_impact_mean",
    "inside_front_impact_mean", "inout_pressure_diff_x_first_turn", "field_presence_impact_sum",
    "field_presence_impact_min",
]
NUMERIC_FEATURES = LEGACY_NUMERIC + NEW_STRUCT + NEW_HISTORY + NEW_IMPACT
CATEGORICAL_FEATURES = [f"track_{t}" for t in TRACKS] + [f"going_turf_{g}" for g in range(1, 5)] + [
    f"going_dirt_{g}" for g in range(1, 5)]
FEATURE_NAMES: List[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES
FEATURE_INDEX = {name: i for i, name in enumerate(FEATURE_NAMES)}
_INDEX = FEATURE_INDEX
IMPACT_FEATURE_NAMES = NEW_IMPACT + NEW_HISTORY
# 実隊列の残差(Pace Impactの元)を作るベース回帰は構造特徴だけを使い、馬・騎手の個体情報を入れない
STRUCT_FEATURE_NAMES = [n for n in LEGACY_NUMERIC if n not in LEGACY_JOCKEY] + NEW_STRUCT + CATEGORICAL_FEATURES
STRUCT_COLUMNS = [FEATURE_INDEX[n] for n in STRUCT_FEATURE_NAMES]
LEGACY_COLUMNS = [FEATURE_INDEX[n] for n in LEGACY_NUMERIC + CATEGORICAL_FEATURES]


def front_count(n: int) -> int:
    """先行集団の頭数。頭数に比例させ(25%)、少頭数でも最低3頭。"""
    return int(min(n, max(FRONT_MIN, np.ceil(FRONT_FRAC * n))))


def front_count_array(n: np.ndarray) -> np.ndarray:
    return np.minimum(n, np.maximum(FRONT_MIN, np.ceil(FRONT_FRAC * n)))


def _by_index(snap: Dict[str, np.ndarray], key: str, idx, n: int) -> np.ndarray:
    """snap[key][idx]。idx=-1 は末尾(未知馬・未知騎手の既定値)。snapに無い/idxが無ければ長さnの0。"""
    arr = snap.get(key)
    if arr is None or idx is None:
        return np.zeros(n)
    return np.asarray(arr, dtype=float)[idx]


def horse_frontness(ctx: RaceContext) -> np.ndarray:
    """直近5走の平均序盤位置から作る先行傾向(1=常に先頭)。履歴なしは0.5。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean_q = np.nanmean(ctx.hist_q[:, :5].astype(float), axis=1)
    return 1.0 - np.where(np.isfinite(mean_q), mean_q, 0.5)


def race_constant_features(ctx: RaceContext, first_turn_default: float) -> np.ndarray:
    """レース固定の特徴量(コース・環境)。"""
    values = np.zeros(len(FEATURE_NAMES))
    first_turn = ctx.first_turn_distance_m if np.isfinite(ctx.first_turn_distance_m) else first_turn_default
    angle = 2 * np.pi * (ctx.month - 1) / 12.0
    turf = 1.0 if ctx.surface == "turf" else 0.0
    short = 1.0 if first_turn < SHORT_FIRST_TURN_M else 0.0
    values[_INDEX["distance_km"]] = ctx.distance_m / 1000.0
    values[_INDEX["first_turn_distance_100m"]] = first_turn / 100.0
    values[_INDEX["field_size"]] = ctx.n
    values[_INDEX["course_week"]] = ctx.course_week
    values[_INDEX["meet_day"]] = ctx.meet_day
    values[_INDEX["season_sin"]] = np.sin(angle)
    values[_INDEX["season_cos"]] = np.cos(angle)
    values[_INDEX["is_turf"]] = turf
    values[_INDEX["short_first_turn"]] = short
    if f"track_{ctx.track}" in _INDEX:
        values[_INDEX[f"track_{ctx.track}"]] = 1.0
    going_name = f"going_{ctx.surface}_{ctx.going}"
    if going_name in _INDEX:
        values[_INDEX[going_name]] = 1.0
    return values


def pace_features(
    ctx: RaceContext,
    formation: Formation,
    snap: Dict[str, np.ndarray],
    first_turn_default: float = 400.0,
) -> np.ndarray:
    """[S, F] の特徴量行列。snap は Dataset.snapshot(month) の辞書(frontness, lead_tempo, Pace Impact各種)。"""
    frontness = snap.get("frontness")
    lead_tempo = snap.get("lead_tempo")
    q = formation.q_adj
    s, n = q.shape
    order = formation.q_rank_order
    k = min(TOP_K, n)
    top = order[:, :k]
    q_top = np.take_along_axis(q, top, axis=1)
    umaban_pct = np.arange(n) / max(n - 1, 1)
    pct_top = umaban_pct[top]
    out = np.zeros((s, len(FEATURE_NAMES)))
    out[:] = race_constant_features(ctx, first_turn_default)[None, :]

    group = formation.group
    out[:, _INDEX["front_group_size"]] = (group == 0).sum(axis=1)
    out[:, _INDEX["lead_candidates"]] = (q <= LEAD_Q_CUT).sum(axis=1)
    out[:, _INDEX["q_top3"]] = q_top[:, : min(3, k)].mean(axis=1)
    out[:, _INDEX["front_competition"]] = (1.0 / (1.0 + (q_top - q_top[:, :1]) / 0.05)).sum(axis=1)
    out[:, _INDEX["front_q_spread"]] = q_top.std(axis=1)
    out[:, _INDEX["leader_margin_in_q"]] = (q_top[:, 1] - q_top[:, 0]) if k > 1 else 0.0
    out[:, _INDEX["group_size_top2"]] = (group <= 1).sum(axis=1)
    out[:, _INDEX["outside_front_count"]] = (pct_top > 0.5).sum(axis=1)
    out[:, _INDEX["outside_front_pressure"]] = ((1.0 - q_top) * pct_top).mean(axis=1)
    in_front = group == 0
    out[:, _INDEX["front_group_avg_horse_no_pct"]] = (in_front * umaban_pct[None, :]).sum(axis=1) / in_front.sum(axis=1)
    out[:, _INDEX["lead_horse_number_pct"]] = pct_top[:, 0]

    jockey = ctx.jockey_idx
    zeros_n = np.zeros(n)
    frontness_n = frontness[jockey] if frontness is not None else zeros_n
    tempo_n = lead_tempo[jockey] if lead_tempo is not None else zeros_n
    tempo_top = tempo_n[top]
    front_top = frontness_n[top]
    out[:, _INDEX["leader_jockey_lead_tempo"]] = tempo_top[:, 0]
    out[:, _INDEX["top3_jockey_lead_tempo"]] = tempo_top[:, : min(3, k)].mean(axis=1)
    out[:, _INDEX["chaser_tempo"]] = tempo_top[:, 1:k].mean(axis=1) if k > 1 else 0.0
    out[:, _INDEX["leader_jockey_frontness"]] = front_top[:, 0]
    out[:, _INDEX["top3_frontness"]] = front_top[:, : min(3, k)].mean(axis=1)

    short = out[:, _INDEX["short_first_turn"]]
    out[:, _INDEX["outside_front_pressure_x_short_first_turn"]] = out[:, _INDEX["outside_front_pressure"]] * short
    out[:, _INDEX["front_competition_x_short_first_turn"]] = out[:, _INDEX["front_competition"]] * short
    out[:, _INDEX["front_group_size_x_turf"]] = out[:, _INDEX["front_group_size"]] * out[:, _INDEX["is_turf"]]
    _fill_pace_impact_features(out, ctx, formation, snap, umaban_pct)
    return out


def _fill_pace_impact_features(out: np.ndarray, ctx: RaceContext, formation: Formation,
                               snap: Dict[str, np.ndarray], umaban_pct: np.ndarray) -> None:
    """全頭隊列(A:先頭 B:2-3番手 C:先行集団 D:内外 E:全頭分布)の特徴量。頭数で割って正規化する。"""
    q, order = formation.q_adj, formation.q_rank_order
    s, n = q.shape
    rows = np.arange(s)
    q_sorted = np.take_along_axis(q, order, axis=1)
    kf = front_count(n)
    top = order[:, :kf]
    hidx, jidx = ctx.horse_idx, ctx.jockey_idx
    h_lead, h_chase = _by_index(snap, "h_lead", hidx, n), _by_index(snap, "h_chase", hidx, n)
    h_front, h_presence = _by_index(snap, "h_front", hidx, n), _by_index(snap, "h_presence", hidx, n)
    n_lead = _by_index(snap, "h_n_lead", hidx, n)
    lead_rate = n_lead / (_by_index(snap, "h_n_runs", hidx, n) + 5.0)
    j_lead, j_chase = _by_index(snap, "j_lead", jidx, n), _by_index(snap, "j_chase", jidx, n)
    j_front = _by_index(snap, "j_front", jidx, n)
    frontness = horse_frontness(ctx)
    short = out[:, _INDEX["short_first_turn"]]
    first_turn = out[:, _INDEX["first_turn_distance_100m"]]

    def put(name: str, values: np.ndarray) -> None:
        out[:, _INDEX[name]] = values

    # A. 先頭馬
    lead, c2, c3 = order[:, 0], order[:, 1], order[:, 2]
    put("leader_horse_lead_impact", h_lead[lead])
    put("leader_jockey_lead_impact", j_lead[lead])
    put("leader_horse_x_jockey_lead", h_lead[lead] * j_lead[lead])
    put("leader_lead_experience", np.log1p(n_lead[lead]))

    # B. 2〜3番手
    gap2, gap3 = q_sorted[:, 1] - q_sorted[:, 0], q_sorted[:, 2] - q_sorted[:, 0]
    put("chase2_q_gap", gap2)
    put("chase3_q_gap", gap3)
    put("chase2_horse_chase_impact", h_chase[c2])
    put("chase3_horse_chase_impact", h_chase[c3])
    put("chase2_jockey_chase_impact", j_chase[c2])
    put("chase3_jockey_chase_impact", j_chase[c3])
    put("chase2_frontness_gap", frontness[c2] - frontness[lead])
    put("chase3_frontness_gap", frontness[c3] - frontness[lead])
    k2, k3 = np.exp(-gap2 / CONTEST_SCALE), np.exp(-gap3 / CONTEST_SCALE)
    put("contest_lead_rate_index", 10.0 * lead_rate[lead] * (k2 * lead_rate[c2] + k3 * lead_rate[c3]))
    fast_leader = np.maximum(-h_lead[lead], 0.0)
    put("contest_pressure_index", k2 * (fast_leader + np.maximum(-h_chase[c2], 0.0))
        + k3 * (fast_leader + np.maximum(-h_chase[c3], 0.0)))

    # C. 先行集団(平均で薄まらないよう min / 上位2頭 / 負側合計も持つ)
    fh, fj = h_front[top], j_front[top]
    put("front_impact_mean", fh.mean(axis=1))
    put("front_impact_sum", fh.sum(axis=1))
    put("front_impact_min", fh.min(axis=1))
    put("front_impact_max", fh.max(axis=1))
    put("front_impact_fast2_mean", np.sort(fh, axis=1)[:, : min(2, kf)].mean(axis=1))
    put("front_impact_neg_sum", np.minimum(fh, 0.0).sum(axis=1))
    put("front_impact_pos_sum", np.maximum(fh, 0.0).sum(axis=1))
    put("front_jockey_impact_mean", fj.mean(axis=1))
    put("front_jockey_impact_sum", fj.sum(axis=1))
    put("front_jockey_impact_min", fj.min(axis=1))
    q_front = q_sorted[:, :kf]
    q_range = q_front[:, -1] - q_front[:, 0]
    put("front_cluster_q_range", q_range)
    put("front_cluster_q_std", q_front.std(axis=1))
    put("front_cluster_density", kf / (q_range + 0.05))
    put("front_lead_rate_sum", lead_rate[top].sum(axis=1))
    put("front_lead_rate_max", lead_rate[top].max(axis=1))

    # D. 枠順と内外(馬番の後半半分を外側とする)
    outside = (umaban_pct > 0.5)[top]
    pressure = np.maximum(-fh, 0.0)
    out_p, in_p = (pressure * outside).sum(axis=1), (pressure * ~outside).sum(axis=1)
    n_out, n_in = outside.sum(axis=1), (~outside).sum(axis=1)
    put("outside_front_ratio", n_out / kf)
    put("outside_front_ratio_x_short_first_turn", n_out / kf * short)
    put("outside_front_ratio_x_first_turn", n_out / kf * first_turn)
    put("outside_front_impact_pressure", out_p)
    put("inside_front_impact_pressure", in_p)
    put("inout_pressure_diff", out_p - in_p)
    put("fast_pressure_outside_share", out_p / (out_p + in_p + 0.05))
    put("outside_front_impact_mean", (fh * outside).sum(axis=1) / np.maximum(n_out, 1))
    put("inside_front_impact_mean", (fh * ~outside).sum(axis=1) / np.maximum(n_in, 1))
    put("inout_pressure_diff_x_first_turn", (out_p - in_p) * first_turn)

    # E. 全頭の位置取り分布(頭数で割って比較可能にする)
    for name, p in (("q_p10", 0.10), ("q_p25", 0.25), ("q_p50", 0.50), ("q_p75", 0.75)):
        pos = p * (n - 1)
        lo, hi = int(np.floor(pos)), int(np.ceil(pos))
        put(name, q_sorted[:, lo] + (pos - lo) * (q_sorted[:, hi] - q_sorted[:, lo]))
    put("q_std_all", q.std(axis=1))
    group = formation.group
    g0 = (group == 0).sum(axis=1)
    put("front_group_ratio", g0 / n)
    put("second_group_ratio", (group == 1).sum(axis=1) / n)
    put("n_groups_ratio", (group.max(axis=1) + 1) / n)
    last_front = q_sorted[rows, g0 - 1]
    next_group = q_sorted[rows, np.minimum(g0, n - 1)]
    put("q_gap_front_to_rest", np.where(g0 < n, next_group - last_front, 0.0))
    put("lead_candidates_ratio", (q <= LEAD_Q_CUT).mean(axis=1))
    put("n_q_le25_ratio", (q <= 0.25).mean(axis=1))
    put("n_q_le50_ratio", (q <= 0.50).mean(axis=1))
    top_front_ability = np.argsort(-frontness, kind="stable")[:3]
    q_top_ability = q[:, top_front_ability]
    put("topfront3_mean_q", q_top_ability.mean(axis=1))
    put("topfront3_min_q", q_top_ability.min(axis=1))
    put("field_presence_impact_sum", np.full(s, h_presence.sum()))
    put("field_presence_impact_min", np.full(s, h_presence.min()))

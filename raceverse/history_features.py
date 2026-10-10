"""厳密な時系列(as-of)履歴特徴量: 近走の序盤位置取り・騎手・上がり・休養日数。

出走行ごとに「その行より前の出走」だけを参照する。同一馬が同日に2回走ることはないため、
日付昇順で並べた直前k走を取れば、対象レース当日以降の情報は構造的に入らない。
"""

from __future__ import annotations

from dataclasses import dataclass

import warnings

import numpy as np
import pandas as pd


@dataclass
class RunHistory:
    q: np.ndarray            # [R, K] 過去走の序盤相対位置(0=先頭,1=最後方)。無効はNaN。列0=1走前
    jockey: np.ndarray       # [R, K] 過去走の騎手idx(不明=-1)
    corner_idx: np.ndarray   # [R, K] 過去走の位置取りが何コーナー目か(0=無効)
    closing_skill: np.ndarray  # [R] 直近5走の上がり相対(負=速い)の平均。履歴なしNaN
    rest_days: np.ndarray    # [R] 前走からの日数。履歴なしNaN
    n_prior: np.ndarray      # [R] 過去出走数(DB内)


def build_run_history(runs: pd.DataFrame, n_hist: int = 10, closing_window: int = 5) -> RunHistory:
    """runs の行順に整列した RunHistory を返す。"""
    count = len(runs)
    horse_codes = pd.factorize(runs["horse_id"])[0]
    dates = runs["date"].to_numpy().astype("datetime64[D]").astype(np.int64)
    order = np.lexsort((dates, horse_codes))
    sorted_horse = horse_codes[order]
    q_sorted = runs["q_early"].to_numpy(dtype=np.float32)[order]
    jockey_sorted = runs["jockey_idx"].to_numpy(dtype=np.int32)[order]
    corner_sorted = runs["early_corner_idx"].to_numpy(dtype=np.int8)[order]
    closing_sorted = runs["closing_rel"].to_numpy(dtype=np.float32)[order]
    date_sorted = dates[order]

    hist_q = np.full((count, n_hist), np.nan, dtype=np.float32)
    hist_j = np.full((count, n_hist), -1, dtype=np.int32)
    hist_c = np.zeros((count, n_hist), dtype=np.int8)
    closing_stack = np.full((count, closing_window), np.nan, dtype=np.float32)
    rest = np.full(count, np.nan, dtype=np.float32)
    n_prior = np.zeros(count, dtype=np.int32)
    positions = np.arange(count)
    for k in range(1, n_hist + 1):
        valid = np.zeros(count, dtype=bool)
        valid[k:] = sorted_horse[k:] == sorted_horse[:-k]
        source = np.where(valid, positions - k, 0)
        hist_q[order, k - 1] = np.where(valid, q_sorted[source], np.nan)
        hist_j[order, k - 1] = np.where(valid, jockey_sorted[source], -1)
        hist_c[order, k - 1] = np.where(valid, corner_sorted[source], 0)
        if k <= closing_window:
            closing_stack[order, k - 1] = np.where(valid, closing_sorted[source], np.nan)
        if k == 1:
            rest[order] = np.where(valid, date_sorted - date_sorted[source], np.nan)
        n_prior[order] += valid.astype(np.int32)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        skill = np.nanmean(closing_stack, axis=1)
    return RunHistory(hist_q, hist_j, hist_c, skill.astype(np.float32), rest, n_prior)

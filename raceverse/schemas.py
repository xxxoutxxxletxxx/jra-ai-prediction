"""RACEVERSE のデータ構造。RaceContext は発走前に利用可能な情報だけを持つ(結果は含めない)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class RaceBias:
    """レース単位のコースバイアス(すべて対数比率。0=平均。予測対象レースより前の確定結果だけから作る)。"""
    style_win: np.ndarray        # [4] 逃げ/先行/差し/追込
    style_place: np.ndarray      # [4]
    style_n: np.ndarray          # [4] コース条件での集計出走数
    style_n_meet: np.ndarray     # [4] 同開催(これまでの開催日)での集計出走数
    draw_win: np.ndarray         # [8] 枠番1-8
    draw_place: np.ndarray       # [8]
    draw_n: np.ndarray           # [8]
    draw_n_meet: np.ndarray      # [8]
    inter: np.ndarray            # [4,3] 脚質 x 枠グループ(内/中/外)の相互作用(周辺効果を除いた分)
    pstyle_win: np.ndarray       # [3,4] ペース(速/中/遅) x 脚質: 同コース脚質バイアスからの差分
    pstyle_place: np.ndarray     # [3,4]
    pdraw: np.ndarray            # [3,3] ペース x 枠グループ: 同コース枠バイアスからの差分
    front_q: float = 0.30
    stalk_q: float = 0.70
    pace_edges: Optional[np.ndarray] = None


@dataclass
class RaceContext:
    race_id: str
    date: pd.Timestamp
    track: str
    surface: str
    distance_m: int
    layout: str
    going: int
    class_group: str
    age_class: str
    meet_id: str
    meet_day: int
    course_week: int
    month: int
    first_turn_distance_m: float
    first_turn_missing: bool
    early_ref: float            # 学習期のみで求めた標準前半ラップ(秒)。NaN=基準なし
    early_section_m: float
    win_time_base: float        # 学習期のみで求めた基準勝ち時計(秒)。NaN=基準なし
    month_idx: int              # 騎手プロフィールのスナップショット月
    # 出走馬(馬番昇順)
    horse_ids: List[str]
    umaban: np.ndarray
    jockey_idx: np.ndarray
    hist_q: np.ndarray          # [N,K]
    hist_j: np.ndarray          # [N,K]
    closing_skill: np.ndarray   # [N]
    rest_days: np.ndarray       # [N]
    age: np.ndarray
    weight_carried: np.ndarray
    ability: np.ndarray         # [N] 既存Rankerのraw score。欠損NaN
    odds: np.ndarray            # [N] 確定オッズ(参考値; 発走前スナップショットではない)
    track_context: Optional["TrackContext"] = None
    warnings: List[str] = field(default_factory=list)
    horse_idx: Optional[np.ndarray] = None  # [N] データセット内の馬ID(Pace Impactの参照用)
    wakuban: Optional[np.ndarray] = None    # [N] 枠番(1-8)
    bias: Optional[RaceBias] = None         # コース別の脚質・枠順バイアス(未設定=特徴量は0)

    @property
    def n(self) -> int:
        return len(self.horse_ids)


@dataclass
class TrackContext:
    """馬場速度の参照結果(仕様7.4)。"""
    track_bias_sec: float
    effective_sample_size: float
    fallback_level: str
    source_counts: Dict[str, int]
    reference_race_ids: List[str]
    reference_cutoff: str
    going_changed: bool
    bias_by_window: Dict[str, float] = field(default_factory=dict)


@dataclass
class Formation:
    q_sampled: np.ndarray   # [S,N]
    q_adj: np.ndarray       # [S,N]
    adjusted: np.ndarray    # [S,N] 騎手変更補正が掛かったか
    group: np.ndarray       # [S,N] 前後グループID(先頭=0)
    lateral_slot: np.ndarray  # [S,N] グループ内の内からの位置(0=最内)
    early_order: np.ndarray   # [S,N] (group, 馬番)順の0始まり順序
    q_rank_order: np.ndarray  # [S,N] q昇順に並べた馬index(先頭が最前方)
    cold_start: np.ndarray  # [N]
    unknown_jockey_runs: int = 0

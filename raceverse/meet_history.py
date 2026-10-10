"""前日・先週・前開催・前年同時期の参照レース抽出(仕様7.1, 7.2)。

すべて同一競馬場・同一芝ダ・確定済み(対象レース日より前の日付)のレースだけを候補にする。
同じ race_id が複数の窓に入る場合は優先度の高い窓に1回だけ数える(重複排除)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

SOURCES = ["previous_day", "previous_week", "previous_meet", "previous_year_same_season"]


@dataclass
class Candidates:
    rows: np.ndarray        # races DataFrame の行位置
    source: List[str]
    gap_days: np.ndarray    # 対象日 - 参照日


class MeetIndex:
    def __init__(self, races: pd.DataFrame, week_window_days: int, year_window_days: int, meet_last_days: int):
        eligible = races[~races["is_upcoming"] & races["track_resid"].notna()]
        self.week_window = week_window_days
        self.year_window = year_window_days
        self.meet_last_days = meet_last_days
        self.by_key: Dict[Tuple[str, str], Tuple[np.ndarray, np.ndarray]] = {}
        days = eligible["date"].to_numpy().astype("datetime64[D]").astype(np.int64)
        position = eligible.index.to_numpy()
        keys = list(zip(eligible["track"].to_numpy(), eligible["surface"].to_numpy()))
        frame = pd.DataFrame({"key": keys, "day": days, "pos": position}).sort_values(["day", "pos"])
        for key, group in frame.groupby("key"):
            self.by_key[key] = (group["day"].to_numpy(), group["pos"].to_numpy())
        all_days = races["date"].to_numpy().astype("datetime64[D]").astype(np.int64)
        starts = pd.Series(all_days, index=races.index).groupby(races["meet_id"]).min()
        self.meet_start = races["meet_id"].map(starts).to_numpy()
        self._cache: Dict[Tuple[str, str, int, int, bool], Candidates] = {}

    def candidates(self, track: str, surface: str, target_day: int, meet_start_day: int,
                   need_previous_meet: Optional[bool] = None) -> Candidates:
        """previous_meet は 前日+先週 が空のとき(開幕週)に必ず含める。need_previous_meet=True で強制追加。"""
        cache_key = (track, surface, target_day, meet_start_day, bool(need_previous_meet))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        days, pos = self.by_key.get((track, surface), (np.array([], dtype=np.int64), np.array([], dtype=np.int64)))
        taken: set = set()
        rows: List[int] = []
        source: List[str] = []
        gaps: List[int] = []

        def add(mask: np.ndarray, label: str) -> None:
            for p, d in zip(pos[mask], days[mask]):
                if p in taken:
                    continue
                taken.add(p)
                rows.append(int(p))
                source.append(label)
                gaps.append(int(target_day - d))

        add(days == target_day - 1, "previous_day")
        week_mask = (days >= target_day - self.week_window) & (days <= target_day - 2)
        if week_mask.any():
            latest = days[week_mask].max()
            add(week_mask & (days >= latest - 2), "previous_week")
        has_recent = len(rows) > 0
        if (not has_recent) or need_previous_meet:
            before = days < meet_start_day
            if before.any():
                last = days[before].max()
                add(before & (days >= last - self.meet_last_days), "previous_meet")
        year_center = target_day - 364
        year_mask = (days >= year_center - self.year_window) & (days <= year_center + self.year_window)
        add(year_mask, "previous_year_same_season")
        result = Candidates(np.asarray(rows, dtype=int), source, np.asarray(gaps, dtype=int))
        self._cache[cache_key] = result
        return result

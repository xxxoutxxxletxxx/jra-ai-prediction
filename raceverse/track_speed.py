"""馬場速度(直近開催の時計の出やすさ)の推定(仕様7.3, 7.4)。

参照レースhごとに  track_speed_residual(h) = 勝ち時計(h) - T_base(h)  (負=基準より速い)。
T_base は参照レースの月初より前のデータだけで学習したRidge基準時計(baselines.walk_forward_baseline)。
距離・コース・クラス・馬場が違うレースを秒数のまま混ぜず、この残差を信用度重みつきで頑健集計する。
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from raceverse.config import TrackSpeedConfig
from raceverse.meet_history import MeetIndex
from raceverse.pace_residuals import distance_band
from raceverse.periods import floor_timestamp, period_start
from raceverse.schemas import TrackContext


class TrackSpeedBuilder:
    def __init__(self, races: pd.DataFrame, cfg: TrackSpeedConfig, unit: str = "month"):
        self.cfg = cfg
        self.unit = unit
        self.races = races
        self.index = MeetIndex(races, cfg.previous_week_window_days, cfg.previous_year_window_days,
                               cfg.previous_meet_last_days)
        self.resid = races["track_resid"].to_numpy()
        self.going = races["going"].to_numpy()
        self.layout = races["layout"].to_numpy()
        self.band = np.array([distance_band(d) for d in races["distance_m"]])
        self.race_ids = races["race_id"].to_numpy()
        self._scale = self._scale_by_month()

    def _scale_by_month(self):
        """期間(月 / 週)pの残差標準偏差 = pより前の期間の確定レースだけで計算(累積)。"""
        frame = self.races[~self.races["is_upcoming"] & self.races["track_resid"].notna()]
        months = period_start(frame["date"], self.unit)
        grouped = frame["track_resid"].groupby(months)
        n = grouped.size().cumsum()
        s1 = grouped.sum().cumsum()
        s2 = (frame["track_resid"] ** 2).groupby(months).sum().cumsum()
        var = (s2 / n - (s1 / n) ** 2).clip(lower=0)
        sd = np.sqrt(var)
        keys = sd.index.to_numpy()
        # 月mに使うのは m より前の最後の月までの累積
        return keys, sd.to_numpy()

    def _resid_scale(self, date: pd.Timestamp) -> float:
        keys, values = self._scale
        month = np.datetime64(floor_timestamp(date, self.unit))
        pos = np.searchsorted(keys, month, side="left") - 1
        return float(values[pos]) if pos >= 0 and values[pos] > 0 else 1.0

    def build_as_of(self, row_pos: int, going_override: Optional[int] = None) -> TrackContext:
        cfg = self.cfg
        race = self.races.iloc[row_pos]
        if going_override is not None:
            race = race.copy()
            race["going"] = int(going_override)
        date = race["date"]
        target_day = int(np.datetime64(date, "D").astype(np.int64))
        meet_start = int(self.index.meet_start[row_pos])
        scale = self._resid_scale(date)

        def weigh(cand):
            w = np.zeros(len(cand.rows))
            for i, (p, src) in enumerate(zip(cand.rows, cand.source)):
                weight = cfg.source_priority[src]
                if src in ("previous_day", "previous_week"):
                    weight *= 0.5 ** (cand.gap_days[i] / cfg.recency_half_life_days)
                if self.going[p] != race["going"]:
                    weight *= cfg.going_mismatch_weight
                if self.band[p] != distance_band(int(race["distance_m"])):
                    weight *= cfg.distance_band_mismatch_weight
                if self.layout[p] != race["layout"]:
                    weight *= cfg.layout_mismatch_weight
                w[i] = weight
            return w

        cand = self.index.candidates(race["track"], race["surface"], target_day, meet_start)
        weights = weigh(cand)
        recent_total = sum(w for w, s in zip(weights, cand.source) if s in ("previous_day", "previous_week"))
        if recent_total < cfg.min_effective_samples and "previous_meet" not in cand.source:
            cand = self.index.candidates(race["track"], race["surface"], target_day, meet_start, True)
            weights = weigh(cand)

        counts = {s: int(sum(1 for x in cand.source if x == s)) for s in
                  ("previous_day", "previous_week", "previous_meet", "previous_year_same_season")}
        if len(cand.rows) == 0:
            return TrackContext(0.0, 0.0, "historical_course_prior", counts, [],
                                str((date - pd.Timedelta(days=1)).date()), False)

        resid = np.clip(self.resid[cand.rows], -cfg.winsor_sigma * scale, cfg.winsor_sigma * scale)
        total = weights.sum()
        bias = float((weights * resid).sum() / (total + cfg.shrinkage_k))
        n_eff = float(total ** 2 / (weights ** 2).sum()) if total > 0 else 0.0
        by_window: Dict[str, float] = {}
        for src in counts:
            mask = np.array([s == src for s in cand.source])
            if mask.any() and weights[mask].sum() > 0:
                by_window[src] = float((weights[mask] * resid[mask]).sum() / weights[mask].sum())
        level = next((s for s in ("previous_day", "previous_week", "previous_meet", "previous_year_same_season")
                      if counts[s] > 0), "historical_course_prior")
        going_changed = bool(len(cand.rows) and (np.mean([self.going[p] != race["going"] for p in cand.rows]) >= 0.5))
        return TrackContext(
            track_bias_sec=bias,
            effective_sample_size=n_eff,
            fallback_level=level,
            source_counts=counts,
            reference_race_ids=[str(self.race_ids[p]) for p in cand.rows],
            reference_cutoff=str((date - pd.Timedelta(days=1)).date()),
            going_changed=going_changed,
            bias_by_window=by_window,
        )

"""騎手プロフィール(先行度・逃げ時ペース傾向)。月次スナップショットで as-of を保証する。

月mのレースには「月m より前の月に確定した騎乗」だけから作った統計を使う(同月内の先行レースは使わない=安全側)。

  frontness(j)   = (n*(1-mean_q) + k*prior)/(n+k)                  仕様4.2
  lead_tempo(j)  = (n*mean(ref_early - actual_early) + k*prior)/(n+k)  仕様6.4 (正=標準より速く刻む)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

from raceverse.periods import period_index


def month_index(dates: pd.Series, base: pd.Timestamp, unit: str = "month") -> np.ndarray:
    """期間番号。unit="week" なら月曜始まりの週番号(名前は月次時代の互換のため month_index のまま)。"""
    return period_index(dates, base, unit)


@dataclass
class JockeyProfiles:
    base_month: pd.Timestamp
    n_q: np.ndarray        # [M+1, J] 月m開始時点の累積サンプル数
    sum_q: np.ndarray
    n_lead: np.ndarray
    sum_tempo: np.ndarray
    frontness_k: float
    tempo_k: float

    @classmethod
    def build(
        cls,
        runs: pd.DataFrame,
        races: pd.DataFrame,
        n_jockeys: int,
        base_month: pd.Timestamp,
        n_months: int,
        frontness_k: float,
        tempo_k: float,
        lead_rank_cut: int,
        unit: str = "month",
    ) -> "JockeyProfiles":
        race_info = races.set_index("race_id")[["early_split_sec", "early_ref"]]
        frame = runs[~runs["race_id"].isin(set(races.loc[races["is_upcoming"], "race_id"]))]
        frame = frame[frame["jockey_idx"] >= 0]
        m = month_index(frame["date"], base_month, unit)
        n_q = np.zeros((n_months + 1, n_jockeys))
        sum_q = np.zeros_like(n_q)
        n_lead = np.zeros_like(n_q)
        sum_tempo = np.zeros_like(n_q)

        has_q = frame["q_early"].notna().to_numpy()
        np.add.at(n_q, (m[has_q], frame["jockey_idx"].to_numpy()[has_q]), 1.0)
        np.add.at(sum_q, (m[has_q], frame["jockey_idx"].to_numpy()[has_q]), frame["q_early"].to_numpy()[has_q])

        actual = frame["race_id"].map(race_info["early_split_sec"]).to_numpy()
        ref = frame["race_id"].map(race_info["early_ref"]).to_numpy()
        lead = (frame["early_rank"].to_numpy() >= 1) & (frame["early_rank"].to_numpy() <= lead_rank_cut)
        lead &= np.isfinite(actual) & np.isfinite(ref)
        np.add.at(n_lead, (m[lead], frame["jockey_idx"].to_numpy()[lead]), 1.0)
        np.add.at(sum_tempo, (m[lead], frame["jockey_idx"].to_numpy()[lead]), (ref - actual)[lead])

        # 月mの値 = m より前の月の累積
        for arr in (n_q, sum_q, n_lead, sum_tempo):
            np.cumsum(arr, axis=0, out=arr)
            arr[1:] = arr[:-1].copy()
            arr[0] = 0.0
        return cls(base_month, n_q, sum_q, n_lead, sum_tempo, frontness_k, tempo_k)

    def snapshot(self, month: int) -> Dict[str, np.ndarray]:
        """月 month 時点の jockey_idx 別 frontness / lead_tempo。末尾要素(index -1)は未知騎手用の事前値。"""
        month = int(np.clip(month, 0, self.n_q.shape[0] - 1))
        n_q, s_q = self.n_q[month], self.sum_q[month]
        total_n = n_q.sum()
        prior_front = 1.0 - (s_q.sum() / total_n) if total_n > 0 else 0.5
        mean_q = np.divide(s_q, n_q, out=np.zeros_like(s_q), where=n_q > 0)
        raw_front = np.where(n_q > 0, 1.0 - mean_q, prior_front)
        k = self.frontness_k
        frontness = (n_q * raw_front + k * prior_front) / (n_q + k)

        n_l, s_t = self.n_lead[month], self.sum_tempo[month]
        total_l = n_l.sum()
        prior_tempo = s_t.sum() / total_l if total_l > 0 else 0.0
        raw_tempo = np.divide(s_t, n_l, out=np.zeros_like(s_t), where=n_l > 0)
        tk = self.tempo_k
        tempo = (n_l * raw_tempo + tk * prior_tempo) / (n_l + tk)
        return {
            "frontness": np.append(frontness, prior_front),
            "lead_tempo": np.append(tempo, prior_tempo),
            "n_q": np.append(n_q, 0.0),
            "n_lead": np.append(n_l, 0.0),
        }

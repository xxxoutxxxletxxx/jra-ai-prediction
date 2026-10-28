"""再学習・as-of スナップショットの単位(月次 / 週次)を一か所で扱う。

月次: 月 m のレースは m 月初より前の確定結果だけを使う。
週次: 週 w(月曜始まり)のレースは w の月曜より前の確定結果だけを使う。
JRAの開催は土日が中心なので、週次なら「先週までの結果」で今週を予測する形になる。
"""

from __future__ import annotations

from typing import List, Union

import numpy as np
import pandas as pd

UNITS = ("month", "week")
Dates = Union[pd.Series, pd.DatetimeIndex]


def validate_unit(unit: str) -> str:
    if unit not in UNITS:
        raise ValueError(f"unsupported refit unit '{unit}'; expected one of {UNITS}")
    return unit


def period_start(dates: pd.Series, unit: str = "month") -> pd.Series:
    """各日付が属する期間の開始日(月初 / 月曜)。"""
    validate_unit(unit)
    if unit == "week":
        return dates.dt.to_period("W-SUN").dt.start_time
    return dates.dt.to_period("M").dt.to_timestamp()


def floor_timestamp(ts: pd.Timestamp, unit: str = "month") -> pd.Timestamp:
    return period_start(pd.Series([pd.Timestamp(ts)]), unit).iloc[0]


def next_period(ts: pd.Timestamp, unit: str = "month") -> pd.Timestamp:
    validate_unit(unit)
    start = floor_timestamp(ts, unit)
    return start + (pd.Timedelta(days=7) if unit == "week" else pd.offsets.MonthBegin(1))


def period_index(dates: pd.Series, base: pd.Timestamp, unit: str = "month") -> np.ndarray:
    """base(期間の開始日)を0とした期間番号。"""
    validate_unit(unit)
    if unit == "week":
        days = (period_start(dates, unit) - floor_timestamp(base, unit)).dt.days
        return (days // 7).to_numpy(dtype=int)
    return ((dates.dt.year - base.year) * 12 + (dates.dt.month - base.month)).to_numpy(dtype=int)


def timestamp_period_index(ts: pd.Timestamp, base: pd.Timestamp, unit: str = "month") -> int:
    return int(period_index(pd.Series([pd.Timestamp(ts)]), base, unit)[0])


def period_range(start: pd.Timestamp, end: pd.Timestamp, unit: str = "month") -> List[pd.Timestamp]:
    """[start, end) に開始日が入る期間の開始日リスト(startは期間の開始日に切り下げる)。"""
    validate_unit(unit)
    first = floor_timestamp(start, unit)
    out: List[pd.Timestamp] = []
    current = first
    while current < pd.Timestamp(end):
        out.append(current)
        current = next_period(current, unit)
    return out

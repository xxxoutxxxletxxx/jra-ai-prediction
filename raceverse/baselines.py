"""月次Walk-Forwardのコース基準モデル(Ridge)。基準時計 T_base と基準前半ラップ reference_early_split に使う。

各レースの基準値は「そのレースが属する月の月初より前に確定したデータだけ」で学習したモデルの予測値。
これにより参照レースの時計残差・ペース偏差も、その時点以前の情報だけで定義される(仕様7.3, 6.1)。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from raceverse.periods import period_start

CATEGORICAL = ["course_key", "class_group", "age_class", "going_key"]


def _frame_for_design(races: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(index=races.index)
    frame["course_key"] = (races["track"] + "|" + races["surface"] + "|" + races["distance_m"].astype(str)
                           + "|" + races["layout"].astype(str))
    frame["class_group"] = races["class_group"].astype(str)
    frame["age_class"] = races["age_class"].astype(str)
    frame["going_key"] = races["surface"] + "_" + races["going"].astype(str)
    return frame


class BaselineModel:
    """コース(場・芝ダ・距離・コース形態)・クラス・年齢条件・馬場を説明変数にしたRidge回帰。"""

    def __init__(self, alpha: float = 2.0):
        self.alpha = alpha
        self.columns_: List[str] = []
        self.model_: Optional[Ridge] = None

    def _design(self, races: pd.DataFrame, fit: bool) -> np.ndarray:
        cats = _frame_for_design(races)
        parts = []
        names: List[str] = []
        for column in CATEGORICAL:
            dummies = pd.get_dummies(cats[column], prefix=column, dtype=float)
            parts.append(dummies)
        dist = races["distance_m"].to_numpy(dtype=float) / 1000.0
        turf = (races["surface"] == "turf").to_numpy(dtype=float)
        numeric = pd.DataFrame({"dist": dist, "dist_turf": dist * turf, "dist_sq": dist ** 2}, index=races.index)
        parts.append(numeric)
        design = pd.concat(parts, axis=1)
        if fit:
            self.columns_ = list(design.columns)
        design = design.reindex(columns=self.columns_, fill_value=0.0)
        return design.to_numpy(dtype=float)

    def fit(self, races: pd.DataFrame, target: str) -> "BaselineModel":
        x = self._design(races, fit=True)
        self.model_ = Ridge(alpha=self.alpha).fit(x, races[target].to_numpy(dtype=float))
        return self

    def predict(self, races: pd.DataFrame) -> np.ndarray:
        return self.model_.predict(self._design(races, fit=False))


def month_start(dates: pd.Series, unit: str = "month") -> pd.Series:
    return period_start(dates, unit)


def walk_forward_baseline(
    races: pd.DataFrame,
    target: str,
    first_month: pd.Timestamp,
    alpha: float = 2.0,
    unit: str = "month",
) -> pd.Series:
    """races の各行に、所属期間(月 / 週)の開始日より前のデータだけで学習したモデルの予測を付ける。first_month より前はNaN。"""
    result = pd.Series(np.nan, index=races.index, dtype=float)
    months = month_start(races["date"], unit)
    valid = races[target].notna() & ~races["is_upcoming"]
    for month in sorted(months[months >= first_month].unique()):
        train = races[valid & (races["date"] < month)]
        target_rows = races[months == month]
        if len(train) < 500 or target_rows.empty:
            continue
        model = BaselineModel(alpha).fit(train, target)
        result.loc[target_rows.index] = model.predict(target_rows)
    return result


def fit_current_baseline(races: pd.DataFrame, target: str, as_of: pd.Timestamp, alpha: float = 2.0) -> BaselineModel:
    """as_of より前の確定データだけで学習した基準モデル(未開催レースの予測用)。"""
    train = races[races[target].notna() & ~races["is_upcoming"] & (races["date"] < as_of)]
    return BaselineModel(alpha).fit(train, target)

"""連続値ペース(前半ラップ偏差, 秒)の線形回帰(仕様6.1, 6.2)。5クラス分類器は作らない。

教師値: pace_delta_sec = actual_early_split_sec - reference_early_split_sec  (負=速い)
モデル: StandardScaler + Ridge。標準化は学習データだけで fit し、評価期へそのまま適用する。
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def make_pace_regressor(alpha: float) -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=alpha))])


def fit_pace_regressor(x: np.ndarray, y: np.ndarray, weight: np.ndarray, alpha: float) -> Pipeline:
    model = make_pace_regressor(alpha)
    model.fit(x, y, scale__sample_weight=weight, ridge__sample_weight=weight)
    return model


def rolling_oof_predictions(
    x: np.ndarray,
    y: np.ndarray,
    weight: np.ndarray,
    dates: pd.Series,
    alpha: float,
    first_month: pd.Timestamp,
    min_rows: int,
) -> np.ndarray:
    """月次ローリング・オリジン。各月の行は「その月より前の行だけ」で学習したモデルで予測する。

    同一レース由来の行は同じ日付なので学習と評価にまたがらない。first_monthより前・学習不足の月はNaN。
    """
    months = dates.dt.to_period("M").dt.to_timestamp().to_numpy()
    pred = np.full(len(y), np.nan)
    date_values = dates.to_numpy()
    for month in np.unique(months[months >= np.datetime64(first_month)]):
        train = date_values < month
        if train.sum() < min_rows:
            continue
        model = fit_pace_regressor(x[train], y[train], weight[train], alpha)
        rows = months == month
        pred[rows] = model.predict(x[rows])
    return pred

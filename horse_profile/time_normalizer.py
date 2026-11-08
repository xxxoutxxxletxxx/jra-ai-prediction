"""Condition-only time baselines fitted on the caller's training window."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL_CONDITIONS = (
    "track",
    "track_cd",
    "surface",
    "going",
    "class_code",
    "age_class_code",
)


class ConditionTimeNormalizer:
    """Estimate an expected time from race conditions, never from a target-race result."""

    def __init__(
        self,
        extra_numeric: Sequence[str] = (),
        ridge_alpha: float = 10.0,
    ) -> None:
        self.extra_numeric = tuple(extra_numeric)
        self.ridge_alpha = ridge_alpha
        self.pipeline_: Pipeline | None = None
        self.constant_: float | None = None
        self.numeric_columns_: tuple[str, ...] = ()
        self.residual_sd_sec_: float | None = None

    def _features(self, frame: pd.DataFrame, *, fitting: bool) -> pd.DataFrame:
        required = {"distance_m", *CATEGORICAL_CONDITIONS, *self.extra_numeric}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"missing time-normalizer columns: {sorted(missing)}")

        features = frame[list(CATEGORICAL_CONDITIONS)].copy()
        for column in CATEGORICAL_CONDITIONS:
            features[column] = features[column].astype("string").fillna("__missing__").astype(str)
        numeric_columns = ("distance_m",) + self.extra_numeric
        numeric = frame[list(numeric_columns)].apply(pd.to_numeric, errors="coerce")
        if fitting:
            self.numeric_medians_ = numeric.median().fillna(0.0)
        features[list(numeric_columns)] = numeric.fillna(self.numeric_medians_)
        return features

    def fit(
        self,
        frame: pd.DataFrame,
        target: pd.Series,
    ) -> "ConditionTimeNormalizer":
        target_values = pd.to_numeric(target, errors="coerce")
        valid = target_values.notna() & np.isfinite(target_values)
        if not valid.any():
            raise ValueError("cannot fit a time baseline without valid training outcomes")
        train = frame.loc[valid].copy()
        y = target_values.loc[valid].to_numpy(dtype=float)
        features = self._features(train, fitting=True)
        self.numeric_columns_ = ("distance_m",) + self.extra_numeric
        if len(train) < 2:
            self.constant_ = float(y[0])
            residuals = np.zeros_like(y)
        else:
            transformer = ColumnTransformer(
                [
                    ("conditions", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL_CONDITIONS)),
                    ("numeric", StandardScaler(), list(self.numeric_columns_)),
                ],
                remainder="drop",
            )
            self.pipeline_ = Pipeline(
                [
                    ("features", transformer),
                    ("regressor", Ridge(alpha=self.ridge_alpha)),
                ]
            )
            self.pipeline_.fit(features, y)
            residuals = y - self.pipeline_.predict(features)
        self.residual_sd_sec_ = float(np.sqrt(np.mean(np.square(residuals))))
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.pipeline_ is None and self.constant_ is None:
            raise RuntimeError("time normalizer has not been fitted")
        if self.constant_ is not None:
            return np.full(len(frame), self.constant_, dtype=float)
        features = self._features(frame, fitting=False)
        assert self.pipeline_ is not None
        return np.asarray(self.pipeline_.predict(features), dtype=float)

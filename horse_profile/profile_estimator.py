"""As-of Horse Profile snapshots with empirical-Bayes shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from horse_profile.sectional_features import derive_sectional_features
from horse_profile.time_normalizer import ConditionTimeNormalizer

PROFILE_MODEL_VERSION: Final = "horse-profile-v1"
REQUIRED_HISTORY_COLUMNS: Final = {
    "race_id",
    "date",
    "horse_id",
    "time_sec",
    "last3f_sec",
    "surface",
    "distance_m",
}
CONDITION_COLUMNS: Final = ("surface", "distance_bucket_m", "going")


@dataclass(frozen=True)
class HorseProfileSnapshot:
    as_of_datetime: pd.Timestamp
    train_cutoff_datetime: pd.Timestamp
    profiles: pd.DataFrame
    condition_responses: pd.DataFrame
    time_normalizer: ConditionTimeNormalizer
    closing_normalizer: ConditionTimeNormalizer | None
    time_aleatoric_sd_sec: float
    time_prior_sd_sec: float
    model_version: str = PROFILE_MODEL_VERSION


def _finite_positive(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.where(np.isfinite(numeric) & (numeric > 0))


def _position_fraction(frame: pd.DataFrame) -> pd.Series:
    field_size = pd.to_numeric(frame.get("field_size"), errors="coerce")
    if field_size is None:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    fractions = pd.Series(np.nan, index=frame.index, dtype=float)
    for column in ("c1", "c2", "c3", "c4"):
        if column not in frame:
            continue
        rank = pd.to_numeric(frame[column], errors="coerce")
        valid = rank.notna() & (rank >= 1) & (rank <= field_size) & fractions.isna() & (field_size > 1)
        fractions.loc[valid] = (rank.loc[valid] - 1) / (field_size.loc[valid] - 1)
    return fractions


def _variance_components(values: pd.DataFrame, value_column: str) -> tuple[float, float, float]:
    valid = values[["horse_id", value_column]].dropna()
    if valid.empty:
        return 0.0, 1.0, 1.0
    grouped = valid.groupby("horse_id", sort=False)[value_column]
    means = grouped.mean()
    counts = grouped.size()
    if len(valid) > len(means):
        within_sum = sum(float(((group - group.mean()) ** 2).sum()) for _, group in grouped)
        within_var = within_sum / (len(valid) - len(means))
    else:
        within_var = float(valid[value_column].var(ddof=1)) if len(valid) > 1 else 1.0
    within_var = max(within_var, 1e-6)
    prior_mean = float(valid[value_column].mean())
    mean_variance = float(np.average(np.square(means - prior_mean), weights=counts))
    sampling_variance = float(np.average(within_var / counts, weights=counts))
    prior_var = max(mean_variance - sampling_variance, within_var * 1e-3, 1e-6)
    return prior_mean, within_var, prior_var


def _posterior(
    values: pd.DataFrame,
    value_column: str,
    prior_mean: float,
    within_var: float,
    prior_var: float,
) -> pd.DataFrame:
    grouped = values.dropna(subset=[value_column]).groupby("horse_id", sort=False)[value_column]
    rows = []
    for horse_id, series in grouped:
        n = len(series)
        posterior_var = 1.0 / (n / within_var + 1.0 / prior_var)
        mean = posterior_var * (series.mean() * n / within_var + prior_mean / prior_var)
        rows.append((horse_id, float(mean), float(np.sqrt(posterior_var)), n))
    return pd.DataFrame(rows, columns=["horse_id", "mean", "sd", "support"])


class HorseProfileEstimator:
    """Build a reproducible snapshot using only completed runs before the as-of date."""

    def __init__(self, ridge_alpha: float = 10.0) -> None:
        self.ridge_alpha = ridge_alpha
        self.snapshot_: HorseProfileSnapshot | None = None

    def fit(
        self,
        history: pd.DataFrame,
        as_of_datetime: str | pd.Timestamp,
    ) -> HorseProfileSnapshot:
        missing = REQUIRED_HISTORY_COLUMNS.difference(history.columns)
        if missing:
            raise ValueError(f"missing history columns: {sorted(missing)}")
        as_of = pd.Timestamp(as_of_datetime).normalize()
        cutoff = as_of - pd.Timedelta(seconds=1)
        runs = history.copy()
        runs["date"] = pd.to_datetime(runs["date"], errors="coerce")
        runs["horse_id"] = runs["horse_id"].astype(str)
        runs["time_sec"] = _finite_positive(runs["time_sec"])
        runs["last3f_sec"] = _finite_positive(runs["last3f_sec"])
        runs = runs.loc[
            runs["date"].notna()
            & (runs["date"] < as_of)
            & runs["time_sec"].notna()
        ].copy()
        if runs.empty:
            raise ValueError(f"no valid completed runs before as-of date {as_of.date()}")
        if runs.duplicated(["race_id", "horse_id"]).any():
            raise ValueError("history contains duplicate (race_id, horse_id) rows")

        runs["distance_m"] = pd.to_numeric(runs["distance_m"], errors="coerce")
        runs = runs.loc[runs["distance_m"].notna() & (runs["distance_m"] > 0)].copy()
        if runs.empty:
            raise ValueError("history contains no valid positive distances")
        for column in ("track", "track_cd", "going", "class_code", "age_class_code"):
            if column not in runs:
                runs[column] = "__missing__"
        if "field_size" not in runs:
            runs["field_size"] = np.nan

        runs = derive_sectional_features(runs)
        runs["early_position_fraction"] = _position_fraction(runs)

        time_normalizer = ConditionTimeNormalizer(ridge_alpha=self.ridge_alpha).fit(
            runs, runs["time_sec"]
        )
        runs["time_residual_sec"] = runs["time_sec"] - time_normalizer.predict(runs)

        closing_runs = runs["early_elapsed_sec"].notna() & runs["last3f_sec"].notna()
        closing_normalizer: ConditionTimeNormalizer | None = None
        runs["closing_residual_sec"] = np.nan
        if closing_runs.any():
            closing_normalizer = ConditionTimeNormalizer(
                extra_numeric=("early_elapsed_sec",),
                ridge_alpha=self.ridge_alpha,
            ).fit(runs.loc[closing_runs], runs.loc[closing_runs, "last3f_sec"])
            runs.loc[closing_runs, "closing_residual_sec"] = (
                runs.loc[closing_runs, "last3f_sec"]
                - closing_normalizer.predict(runs.loc[closing_runs])
            )

        prior_mean, within_var, prior_var = _variance_components(runs, "time_residual_sec")
        time_post = _posterior(runs, "time_residual_sec", prior_mean, within_var, prior_var)
        profiles = time_post.rename(
            columns={
                "mean": "time_ability_mean_sec",
                "sd": "time_ability_sd_sec",
                "support": "time_support",
            }
        )

        for source, mean_name, sd_name, support_name in (
            ("closing_residual_sec", "closing_ability_mean_sec", "closing_ability_sd_sec", "closing_support"),
            ("early_position_fraction", "early_position_mean", "early_position_sd", "early_position_support"),
        ):
            axis = runs[["horse_id", source]].dropna()
            if axis.empty:
                axis_post = pd.DataFrame(columns=["horse_id", mean_name, sd_name, support_name])
            else:
                axis_prior_mean, axis_within_var, axis_prior_var = _variance_components(runs, source)
                axis_post = _posterior(
                    runs, source, axis_prior_mean, axis_within_var, axis_prior_var
                ).rename(
                    columns={
                        "mean": mean_name,
                        "sd": sd_name,
                        "support": support_name,
                    }
                )
            profiles = profiles.merge(axis_post, on="horse_id", how="left")

        starts = runs.groupby("horse_id", sort=False).size().rename("total_starts")
        profiles = profiles.merge(starts, on="horse_id", how="left")
        profiles["effective_starts"] = profiles["time_support"]
        profiles["start_ability_mean"] = np.nan
        profiles["start_ability_sd"] = np.nan
        profiles["sustain_ability_mean"] = np.nan
        profiles["sustain_ability_sd"] = np.nan
        profiles["as_of_datetime"] = as_of
        profiles["train_cutoff_datetime"] = cutoff
        profiles["model_version"] = PROFILE_MODEL_VERSION
        profiles["coverage_flag"] = np.where(
            profiles["time_support"] > 0, "observed_with_population_shrinkage", "population_prior"
        )

        runs["distance_bucket_m"] = (
            (runs["distance_m"] / 200.0).round() * 200.0
        ).astype(int)
        runs["going"] = runs["going"].astype("string").fillna("__missing__").astype(str)
        responses = []
        time_prior_strength = within_var / prior_var
        for keys, group in runs.groupby(
            ["horse_id", *CONDITION_COLUMNS], sort=False, dropna=False
        ):
            horse_id, surface, distance_bucket, going = keys
            horse_profile = profiles.loc[profiles["horse_id"] == horse_id].iloc[0]
            n = len(group)
            delta_mean = float(group["time_residual_sec"].mean())
            delta_var = 1.0 / (n / within_var + 1.0 / prior_var)
            delta = delta_var * (
                n * delta_mean / within_var
                + float(horse_profile["time_ability_mean_sec"]) / prior_var
            )
            responses.append(
                {
                    "horse_id": horse_id,
                    "surface": str(surface),
                    "distance_bucket_m": int(distance_bucket),
                    "going": str(going),
                    "predicted_time_delta_sec": float(delta),
                    "uncertainty_sd_sec": float(np.sqrt(delta_var)),
                    "n_condition_starts": n,
                    "backed_by_prior_only": n == 0,
                }
            )
        condition_responses = pd.DataFrame(
            responses,
            columns=[
                "horse_id",
                "surface",
                "distance_bucket_m",
                "going",
                "predicted_time_delta_sec",
                "uncertainty_sd_sec",
                "n_condition_starts",
                "backed_by_prior_only",
            ],
        )
        residual_after_profile = runs["time_residual_sec"] - runs["horse_id"].map(
            profiles.set_index("horse_id")["time_ability_mean_sec"]
        )
        aleatoric_sd = float(np.sqrt(np.mean(np.square(residual_after_profile))))
        prior_sd = float(np.sqrt(prior_var))
        snapshot = HorseProfileSnapshot(
            as_of_datetime=as_of,
            train_cutoff_datetime=cutoff,
            profiles=profiles.reset_index(drop=True),
            condition_responses=condition_responses,
            time_normalizer=time_normalizer,
            closing_normalizer=closing_normalizer,
            time_aleatoric_sd_sec=max(aleatoric_sd, 1e-6),
            time_prior_sd_sec=max(prior_sd, 1e-6),
        )
        self.snapshot_ = snapshot
        return snapshot

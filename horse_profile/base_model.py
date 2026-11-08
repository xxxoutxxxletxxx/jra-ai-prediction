"""Horse-only BASE: condition-adjusted finish-time distributions and win probabilities."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from horse_profile.profile_estimator import CONDITION_COLUMNS, HorseProfileSnapshot

BASE_MODEL_VERSION: Final = "horse-only-base-v1"
ENTRY_COLUMNS: Final = {
    "race_id",
    "horse_id",
    "date",
    "surface",
    "distance_m",
}


class HorseOnlyBaseModel:
    """Simulate finish times without Ranker scores, odds, jockeys, or field formation."""

    def __init__(self, simulations: int = 20_000, seed: int = 20261108) -> None:
        if simulations < 1:
            raise ValueError("simulations must be positive")
        self.simulations = simulations
        self.seed = seed

    def predict(
        self,
        entries: pd.DataFrame,
        snapshot: HorseProfileSnapshot,
        calibration_temperature: float | None = None,
    ) -> pd.DataFrame:
        missing = ENTRY_COLUMNS.difference(entries.columns)
        if missing:
            raise ValueError(f"missing race-entry columns: {sorted(missing)}")
        if entries.empty:
            return pd.DataFrame(
                columns=[
                    "race_id",
                    "horse_id",
                    "as_of_datetime",
                    "expected_finish_time_sec",
                    "finish_time_sd_sec",
                    "win_probability_raw",
                    "win_probability_calibrated",
                    "predicted_rank",
                    "profile_coverage_flag",
                    "model_version",
                ]
            )
        if entries[["race_id", "horse_id"]].isna().any().any():
            raise ValueError("race_id and horse_id must not be missing")
        if entries.duplicated(["race_id", "horse_id"]).any():
            raise ValueError("entries contain duplicate (race_id, horse_id) rows")
        if calibration_temperature is not None and (
            not np.isfinite(calibration_temperature) or calibration_temperature <= 0
        ):
            raise ValueError("calibration_temperature must be a positive finite value")
        if "distance_m" not in entries or entries["distance_m"].isna().any():
            raise ValueError("distance_m must be present for every entry")

        frame = entries.copy()
        frame["horse_id"] = frame["horse_id"].astype(str)
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        if (frame["date"].dt.normalize() < snapshot.as_of_datetime).any():
            raise ValueError("prediction date precedes the profile as-of date")
        for column in ("track", "track_cd", "going", "class_code", "age_class_code"):
            if column not in frame:
                frame[column] = "__missing__"
        frame["distance_bucket_m"] = (
            (pd.to_numeric(frame["distance_m"], errors="coerce") / 200.0).round() * 200.0
        ).astype(int)
        frame["going"] = frame["going"].astype("string").fillna("__missing__").astype(str)

        profiles = snapshot.profiles.set_index("horse_id")
        responses = snapshot.condition_responses.set_index(
            ["horse_id", *CONDITION_COLUMNS]
        ) if not snapshot.condition_responses.empty else pd.DataFrame()
        predictions = []
        rng = np.random.default_rng(self.seed)

        for race_id, race in frame.groupby("race_id", sort=True):
            race = race.sort_values("horse_id", kind="stable").copy()
            baseline = snapshot.time_normalizer.predict(race)
            means = []
            profile_sds = []
            flags = []
            for row, baseline_time in zip(race.itertuples(index=False), baseline):
                horse_id = str(row.horse_id)
                profile = profiles.loc[horse_id] if horse_id in profiles.index else None
                mean = (
                    float(profile["time_ability_mean_sec"])
                    if profile is not None
                    else 0.0
                )
                profile_sd = (
                    float(profile["time_ability_sd_sec"])
                    if profile is not None and pd.notna(profile["time_ability_sd_sec"])
                    else snapshot.time_prior_sd_sec
                )
                condition_key = (
                    horse_id,
                    str(row.surface),
                    int(row.distance_bucket_m),
                    str(row.going),
                )
                condition_supported = False
                if not responses.empty and condition_key in responses.index:
                    response = responses.loc[condition_key]
                    mean = float(response["predicted_time_delta_sec"])
                    profile_sd = float(response["uncertainty_sd_sec"])
                    condition_supported = True
                means.append(float(baseline_time + mean))
                profile_sds.append(profile_sd)
                flags.append(
                    "condition_supported"
                    if condition_supported
                    else "global_profile"
                    if profile is not None
                    else "population_prior"
                )

            aleatoric_sd = snapshot.time_aleatoric_sd_sec
            total_sds = np.sqrt(np.square(profile_sds) + aleatoric_sd**2)
            sampled_times = rng.normal(
                loc=np.asarray(means, dtype=float),
                scale=np.asarray(total_sds, dtype=float),
                size=(self.simulations, len(race)),
            )
            winner_indices = np.argmin(sampled_times, axis=1)
            raw_probabilities = np.bincount(
                winner_indices, minlength=len(race)
            ).astype(float) / self.simulations
            if calibration_temperature is None:
                calibrated = np.full(len(race), np.nan, dtype=float)
            else:
                logits = np.log(np.maximum(raw_probabilities, np.finfo(float).tiny))
                logits /= calibration_temperature
                logits -= logits.max()
                calibrated = np.exp(logits)
                calibrated /= calibrated.sum()
            ranks = pd.Series(means).rank(method="first", ascending=True).astype(int).to_numpy()

            for index, row in enumerate(race.itertuples(index=False)):
                predictions.append(
                    {
                        "race_id": race_id,
                        "horse_id": str(row.horse_id),
                        "as_of_datetime": snapshot.as_of_datetime,
                        "expected_finish_time_sec": means[index],
                        "finish_time_sd_sec": total_sds[index],
                        "win_probability_raw": raw_probabilities[index],
                        "win_probability_calibrated": calibrated[index],
                        "predicted_rank": ranks[index],
                        "profile_coverage_flag": flags[index],
                        "calibration_status": (
                            "not_fitted"
                            if calibration_temperature is None
                            else "temperature"
                        ),
                        "model_version": BASE_MODEL_VERSION,
                    }
                )

        result = pd.DataFrame(predictions)
        if (
            not np.isfinite(result["win_probability_raw"]).all()
            or (result["win_probability_raw"] < 0).any()
        ):
            raise RuntimeError("base simulation produced invalid win probabilities")
        probability_sums = result.groupby("race_id")["win_probability_raw"].sum()
        if not np.allclose(probability_sums.to_numpy(), 1.0, atol=1e-12):
            raise RuntimeError("base simulation probabilities do not sum to one per race")
        return result.sort_values(["race_id", "predicted_rank"]).reset_index(drop=True)

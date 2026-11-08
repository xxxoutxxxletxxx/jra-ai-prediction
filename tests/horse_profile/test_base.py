import numpy as np
import pandas as pd
import pytest

from horse_profile.base_model import HorseOnlyBaseModel
from horse_profile.profile_estimator import HorseProfileEstimator
from horse_profile.sectional_features import derive_sectional_features


def _history() -> pd.DataFrame:
    rows = []
    for race_number, date in enumerate(pd.date_range("2023-01-01", periods=8, freq="7D")):
        for horse_number in range(4):
            rows.append(
                {
                    "race_id": f"old-{race_number}",
                    "date": date,
                    "horse_id": f"horse-{horse_number}",
                    "time_sec": 96.0 + horse_number * 0.3 + race_number * 0.02,
                    "last3f_sec": 34.0 + horse_number * 0.08,
                    "surface": "turf",
                    "distance_m": 1600,
                    "track": "05",
                    "track_cd": "16",
                    "going": "2",
                    "class_code": "C2",
                    "age_class_code": "13",
                    "field_size": 4,
                    "c1": horse_number + 1,
                    "c2": horse_number + 1,
                    "c3": horse_number + 1,
                    "c4": horse_number + 1,
                }
            )
    return pd.DataFrame(rows)


def test_sectional_identity_and_missingness() -> None:
    result = derive_sectional_features(
        pd.DataFrame(
            {
                "race_id": ["r1", "r1"],
                "time_sec": [95.3, 96.0],
                "last3f_sec": [34.8, np.nan],
            }
        )
    )

    assert result.loc[0, "early_elapsed_sec"] == pytest.approx(60.5)
    assert result.loc[0, "gap_to_leader_600_sec"] == pytest.approx(0.0)
    assert pd.isna(result.loc[1, "early_elapsed_sec"])
    assert pd.isna(result.loc[1, "gap_to_leader_600_sec"])
    assert not result["leader_observed_complete"].any()


def test_profile_ignores_runs_on_or_after_as_of_date() -> None:
    history = _history()
    estimator = HorseProfileEstimator()
    original = estimator.fit(history, "2023-02-20").profiles
    future = pd.DataFrame(
        [
            {
                **history.iloc[0].to_dict(),
                "race_id": "future",
                "date": pd.Timestamp("2023-02-20"),
                "time_sec": 400.0,
                "last3f_sec": 20.0,
            }
        ]
    )
    changed = estimator.fit(pd.concat([history, future], ignore_index=True), "2023-02-20").profiles

    pd.testing.assert_frame_equal(original, changed)


def test_horse_only_base_probabilities_sum_and_are_reproducible() -> None:
    history = _history()
    snapshot = HorseProfileEstimator().fit(history, "2023-02-20")
    entries = pd.DataFrame(
        [
            {
                "race_id": "target",
                "horse_id": f"horse-{horse_number}",
                "date": pd.Timestamp("2023-02-25"),
                "surface": "turf",
                "distance_m": 1600,
                "track": "05",
                "track_cd": "16",
                "going": "2",
                "class_code": "C2",
                "age_class_code": "13",
            }
            for horse_number in range(5)
        ]
    )
    model = HorseOnlyBaseModel(simulations=3000, seed=7)

    first = model.predict(entries, snapshot)
    second = model.predict(entries, snapshot)

    assert first["win_probability_raw"].sum() == pytest.approx(1.0)
    assert first["win_probability_raw"].between(0.0, 1.0).all()
    assert first["finish_time_sd_sec"].gt(0).all()
    assert first["win_probability_calibrated"].isna().all()
    pd.testing.assert_frame_equal(first, second)

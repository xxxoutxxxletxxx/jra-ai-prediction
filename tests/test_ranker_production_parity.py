from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import ranker_production_predict as production
from src import ranker_walk_forward_backtest as walk_forward
from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES, build_v1_features


class ForecastParityTest(unittest.TestCase):
    def test_course_wakuban_rates_use_prior_races_only(self) -> None:
        def race_row(day, race_number, umaban, wakuban, rank, horse, status="7"):
            return {
                "date": date(2026, 1, day), "idYear": 2026, "idMonthDay": f"01{day:02d}",
                "idJyoCD": "05", "idKaiji": "01", "idNichiji": "01", "idRaceNum": f"{race_number:02d}",
                "Umaban": umaban, "Wakuban": wakuban, "KettoNum": horse, "Bamei": horse,
                "KakuteiJyuni": rank, "headDataKubun": status, "race_Kyori": 1600,
                "race_TrackCD": "10", "race_Honsyokin0": 10000, "Odds": 20,
            }

        rows = [
            race_row(1, 1, 1, 1, 1, "A"),
            race_row(1, 1, 2, 1, 2, "B"),
            race_row(1, 1, 3, 2, 3, "C"),
            race_row(2, 2, 1, 1, 0, "D", "1"),
            race_row(2, 2, 2, 2, 0, "E", "1"),
        ]

        features = build_v1_features(rows, include_unfinished=True)
        first_day = [row for row in features if row["date"] == date(2026, 1, 1)]
        target = {row["horse_name"]: row for row in features if row["date"] == date(2026, 1, 2)}

        self.assertTrue(all(row["course_gate_sample_count"] == 0 for row in first_day))
        self.assertEqual(target["D"]["course_gate_sample_count"], 2)
        self.assertEqual(target["D"]["course_gate_win_rate"], 0.5)
        self.assertEqual(target["D"]["course_gate_place_rate"], 1.0)
        self.assertEqual(target["E"]["course_gate_sample_count"], 1)
        self.assertEqual(target["E"]["course_gate_win_rate"], 0.0)
        self.assertEqual(target["E"]["course_gate_place_rate"], 1.0)

    def test_production_feature_set_excludes_negative_roi_features(self) -> None:
        removed = {
            "last3_distance", "race_total_top5_prize", "race_second_prize",
            "mean_race_prize_last3", "race_third_prize", "last1_race_first_prize",
            "weighted_race_prize_last3", "hidden_strength_last2", "last2_distance",
            "last3_winner_strength_v2", "career_wins",
        }

        self.assertEqual(len(RANKER_MARGIN_CORRECTION_FEATURES), 86)
        self.assertTrue(removed.isdisjoint(RANKER_MARGIN_CORRECTION_FEATURES))
        self.assertIn("course_gate_win_rate", RANKER_MARGIN_CORRECTION_FEATURES)
        self.assertIn("course_gate_place_rate", RANKER_MARGIN_CORRECTION_FEATURES)

    def test_production_training_matches_backtest_eligibility(self) -> None:
        rows = [
            {
                "date": "2026-09-10", "idJyoCD": "09", "actual_rank": 1,
                "headDataKubun": "7", "race_first_prize": 9_000_000,
                "odds": 25.0, "Umaban": 1, "horse_name": "eligible", "surface": "芝",
            },
            {
                "date": "2026-09-10", "idJyoCD": "09", "actual_rank": 1,
                "headDataKubun": "7", "race_first_prize": 9_000_000,
                "odds": 0.0, "Umaban": 2, "horse_name": "no-odds", "surface": "芝",
            },
            {
                "date": "2026-09-12", "idJyoCD": "09", "actual_rank": 0,
                "headDataKubun": "1", "race_first_prize": 9_000_000,
                "odds": 0.0, "Umaban": 3, "horse_name": "upcoming", "surface": "芝",
            },
        ]
        with patch.object(production, "load_data", return_value=([], None, None)), patch.object(
            production, "build_v1_features", return_value=rows
        ):
            training, upcoming = production._prepare_frame(pd.Timestamp("2026-09-12"), 1)

        self.assertEqual(training["horse_name"].tolist(), ["eligible"])
        self.assertEqual(upcoming["horse_name"].tolist(), ["upcoming"])

    def test_forecast_uses_as_of_training_and_three_month_calibration(self) -> None:
        training = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-08-31", "2025-09-01", "2025-11-30"]),
                "race_id": ["old-1", "old-2", "cal-1", "cal-2"],
                "actual_rank": [1, 2, 1, 2],
                "odds": [20.0, 30.0, 40.0, 50.0],
                "feature": [1.0, 2.0, 3.0, 4.0],
            }
        )
        evaluation = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-12-01", "2025-12-01"]),
                "race_id": ["target", "target"],
                "actual_rank": [0, 0],
                "odds": [25.0, 60.0],
                "feature": [5.0, 6.0],
            }
        )

        with patch.object(
            walk_forward,
            "ranker_scores",
            side_effect=[np.array([0.2, -0.2]), np.array([1.0, 0.0])],
        ) as score_mock, patch.object(
            walk_forward, "select_temperature", return_value=(0.5, 0.1)
        ):
            result, metadata = walk_forward.forecast_ranker(
                training,
                evaluation,
                ["feature"],
                pd.Timestamp("2025-12-01"),
                calibration_months=3,
                mode="production_as_of",
            )

        calibration_train = score_mock.call_args_list[0].args[0]
        calibration = score_mock.call_args_list[0].args[1]
        final_train = score_mock.call_args_list[1].args[0]
        self.assertEqual(calibration_train["race_id"].tolist(), ["old-1", "old-2"])
        self.assertEqual(calibration["race_id"].tolist(), ["cal-1", "cal-2"])
        self.assertEqual(final_train["race_id"].tolist(), training["race_id"].tolist())
        self.assertEqual(metadata["temperature"], 0.5)
        self.assertEqual(result["model_train_end_date"].unique().tolist(), ["2025-11-30"])
        self.assertEqual(result["evaluation_mode"].unique().tolist(), ["production_as_of"])
        self.assertAlmostEqual(result["ranker_win_probability"].sum(), 1.0)
        self.assertEqual(result["prediction_rank"].tolist(), [1, 2])

    def test_production_output_uses_decimal_odds_and_backtest_bet_rule(self) -> None:
        predictions = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-09-12", "2026-09-12"]),
                "race_id": ["race", "race"],
                "idJyoCD": ["09", "09"],
                "racecourse": ["阪神", "阪神"],
                "idRaceNum": [1, 1],
                "Umaban": [6, 1],
                "horse_name": ["ガストン", "メイショウトム"],
                "KisyuCode": ["001", "002"],
                "predicted_win_probability": [0.45, 0.30],
                "ai_rank": [1, 2],
                "Odds": [25.0, 60.0],
                "popularity": [1, 2],
                "ranker_score": [1.2, 0.8],
                "model_train_end_date": ["2026-09-11", "2026-09-11"],
                "evaluation_mode": ["production_as_of", "production_as_of"],
                "calibration_temperature": [0.7, 0.7],
            }
        )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            production, "OUTPUT_DIR", Path(directory)
        ):
            production.write_output(predictions)
            with (Path(directory) / "predictions.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["Odds"], "2.5")
        self.assertEqual(rows[0]["bet_decision"], "BET")
        self.assertEqual(rows[0]["bet_reason_code"], "BET_LOW_ODDS_HIGH_PROB")
        self.assertEqual(rows[1]["Odds"], "6.0")
        self.assertEqual(rows[1]["bet_decision"], "")
        self.assertEqual(rows[0]["feature_count"], "86")


if __name__ == "__main__":
    unittest.main()

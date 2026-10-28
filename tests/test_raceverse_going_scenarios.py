import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from raceverse.cli import build_parser
from raceverse.pace_features import FEATURE_INDEX, race_constant_features
from raceverse.performance import PERF_FEATURES, perf_features
from raceverse.adapters.race_data import surface_from_track_code
from raceverse.winning_time_model import ability_stats
from raceverse_fixtures import make_ctx
from scripts.build_raceverse_site_data import build_payload
from src.backtest import surface


class GoingFeatureTest(unittest.TestCase):
    def test_missing_ranker_scores_are_neutral_for_performance_and_clock_features(self):
        values = ability_stats(np.array([1.0, np.nan, 0.0, np.nan]))
        self.assertTrue(np.isfinite(values).all())
        self.assertEqual(values[0], 1.0)

    def test_raceverse_turf_dirt_code_boundaries_are_unambiguous(self):
        codes = np.array([10, 22, 23, 29, 52])
        self.assertEqual(
            surface_from_track_code(pd.Series(codes)).tolist(),
            ["turf", "turf", "dirt", "dirt", "other"],
        )

    def test_shared_backtest_surface_parser_uses_complete_track_code(self):
        self.assertEqual(surface({"race_TrackCD": "11"}), "芝")
        self.assertEqual(surface({"race_TrackCD": "23"}), "ダート")
        self.assertEqual(surface({"race_TrackCD": "52"}), "障害")

    def test_prediction_cli_exposes_pre_event_scenario_mode(self):
        args = build_parser().parse_args([
            "predict", "--date", "2026-10-25", "--going-scenarios",
        ])
        self.assertTrue(args.going_scenarios)

    def test_going_updates_pace_and_learned_performance_inputs(self):
        ctx = make_ctx(n=10, seed=14)
        q = np.tile(np.linspace(0.0, 1.0, ctx.n), (3, 1))
        slots = np.zeros_like(q)
        pace = np.zeros(3)
        feature_vectors = []
        performance_vectors = []
        for going in range(1, 5):
            ctx.going = going
            feature_vectors.append(race_constant_features(ctx, 400.0))
            performance_vectors.append(perf_features(ctx, q, slots, pace))

        for going in range(1, 5):
            name = f"going_turf_{going}"
            self.assertEqual(feature_vectors[going - 1][FEATURE_INDEX[name]], 1.0)
        for going in range(2, 5):
            name = f"ability_c_x_going_{going}"
            col = PERF_FEATURES.index(name)
            self.assertGreater(np.abs(performance_vectors[going - 1][:, :, col]).sum(), 0.0)
            self.assertEqual(np.abs(performance_vectors[0][:, :, col]).sum(), 0.0)
        np.testing.assert_array_equal(performance_vectors[0][:, :, :5], performance_vectors[1][:, :, :5])


class SiteScenarioPayloadTest(unittest.TestCase):
    def _make_db(self, path: Path, race_status="2", turf_going="0", finish="0"):
        with sqlite3.connect(path) as connection:
            connection.execute("""
                CREATE TABLE NL_RA_RACE (
                    idYear TEXT, idMonthDay TEXT, idJyoCD TEXT, idKaiji TEXT, idNichiji TEXT, idRaceNum TEXT,
                    headDataKubun TEXT, headMakeDate TEXT, Kyori TEXT, TrackCD TEXT, RaceInfoRyakusyo10 TEXT,
                    TenkoBabaSibaBabaCD TEXT, TenkoBabaDirtBabaCD TEXT
                )
            """)
            connection.execute("""
                CREATE TABLE NL_SE_RACE_UMA (
                    idYear TEXT, idMonthDay TEXT, idJyoCD TEXT, idKaiji TEXT, idNichiji TEXT, idRaceNum TEXT,
                    KakuteiJyuni TEXT, Umaban TEXT
                )
            """)
            connection.execute(
                "INSERT INTO NL_RA_RACE VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026", "1025", "05", "04", "04", "01", race_status, "20261024100000", "1600", "11", "",
                 turf_going, "0"),
            )
            connection.execute(
                "INSERT INTO NL_SE_RACE_UMA VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026", "1025", "05", "04", "04", "01", finish, "1"),
            )

    def test_four_independent_scenarios_merge_and_no_going_is_guessed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reports = root / "reports"
            reports.mkdir()
            db_path = root / "race.db"
            self._make_db(db_path)
            race_id = "2026-1025-05-04-04-01"
            probabilities = {
                1: [0.7, 0.3],
                2: [0.6, 0.4],
                3: [0.4, 0.6],
                4: [0.3, 0.7],
            }
            for going, probs in probabilities.items():
                payload = {
                    "race": {
                        "engine": "RACEVERSE",
                        "version": "0.6",
                        "race_id": race_id,
                        "going": going,
                        "going_scenario": going,
                        "simulations": 1000,
                        "model_as_of": "2026-10-24",
                        "pace_display_probabilities": {},
                    },
                    "horses": [
                        {"umaban": number, "horse_name": f"Horse {number}", "win_probability_raw": p,
                         "win_probability_calibrated": p, "top3_probability": p}
                        for number, p in enumerate(probs, start=1)
                    ],
                }
                (reports / f"{race_id}_going-{going}.json").write_text(
                    json.dumps(payload), encoding="utf-8")

            result = build_payload(reports, db_path)
            race = result["dates"][0]["tracks"][0]["races"][0]
            self.assertEqual(set(race["going_scenarios"]), {"good", "yielding", "soft", "heavy"})
            self.assertTrue(race["scenario_favorite_changes"])
            self.assertIsNone(race["published_going"])
            self.assertEqual(race["horses"][0]["going_probabilities"]["good"], 0.7)
            self.assertEqual(race["horses"][1]["going_probabilities"]["heavy"], 0.7)

    def test_confirmed_race_keeps_only_actual_going_probability(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reports = root / "reports"
            reports.mkdir()
            db_path = root / "race.db"
            self._make_db(db_path, race_status="7", turf_going="3", finish="1")
            race_id = "2026-1025-05-04-04-01"
            payload = {
                "race": {
                    "engine": "RACEVERSE", "version": "0.6", "race_id": race_id, "going": 3,
                    "simulations": 1000, "model_as_of": "2026-10-25", "pace_display_probabilities": {},
                },
                "horses": [
                    {"umaban": number, "horse_name": f"Horse {number}", "win_probability_raw": probability,
                     "top3_probability": probability}
                    for number, probability in ((1, 0.6), (2, 0.4))
                ],
            }
            (reports / f"{race_id}.json").write_text(json.dumps(payload), encoding="utf-8")

            result = build_payload(reports, db_path)
            race = result["dates"][0]["tracks"][0]["races"][0]
            self.assertNotIn("going_scenarios", race)
            self.assertEqual(race["going_label"], "重")
            self.assertNotIn("going_probabilities", race["horses"][0])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from raceverse.baselines import walk_forward_baseline
from raceverse.history_features import build_run_history
from raceverse.jockey_profiles import JockeyProfiles, month_index

ROOT = Path(__file__).resolve().parents[1]


class HistoryAsOfTest(unittest.TestCase):
    def _runs(self):
        dates = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"])
        runs = pd.DataFrame({
            "horse_id": ["A", "A", "A", "B"], "date": dates, "q_early": [0.1, 0.2, 0.3, 0.9],
            "jockey_idx": [1, 2, 3, 4], "early_corner_idx": [1, 1, 1, 1], "closing_rel": [-0.5, -0.4, -0.3, 0.2],
        })
        return runs

    def test_history_contains_only_earlier_runs_of_same_horse(self):
        h = build_run_history(self._runs(), n_hist=3)
        self.assertTrue(np.isnan(h.q[0]).all())                       # 初出走は履歴なし
        self.assertAlmostEqual(h.q[1, 0], 0.1)
        np.testing.assert_allclose(h.q[2, :2], [0.2, 0.1], atol=1e-6)  # 1走前=0.2, 2走前=0.1
        self.assertTrue(np.isnan(h.q[3]).all())                       # 別馬の履歴は混ざらない
        self.assertEqual(h.jockey[2, 0], 2)

    def test_future_value_change_does_not_alter_past_rows(self):
        a = build_run_history(self._runs(), n_hist=3)
        runs = self._runs()
        runs.loc[2, "q_early"] = 0.99  # 未来の走の値を書き換える
        b = build_run_history(runs, n_hist=3)
        np.testing.assert_array_equal(a.q[:3], b.q[:3])               # 行2自身の履歴は不変(行2の値は行3以降の履歴にしか影響しない)

    def test_rest_days_and_n_prior(self):
        h = build_run_history(self._runs(), n_hist=3)
        self.assertEqual(h.n_prior.tolist(), [0, 1, 2, 0])
        self.assertAlmostEqual(h.rest_days[1], 31)


class JockeyProfileAsOfTest(unittest.TestCase):
    def test_snapshot_excludes_same_and_later_months(self):
        base = pd.Timestamp("2024-01-01")
        runs = pd.DataFrame({
            "race_id": ["r1", "r2", "r3"], "date": pd.to_datetime(["2024-01-10", "2024-02-10", "2024-03-10"]),
            "jockey_idx": [0, 0, 0], "q_early": [0.0, 0.5, 1.0], "early_rank": [1, 5, 10],
        })
        races = pd.DataFrame({"race_id": ["r1", "r2", "r3"], "early_split_sec": [34.0, 35.0, 36.0],
                              "early_ref": [35.0, 35.0, 35.0], "is_upcoming": [False] * 3})
        prof = JockeyProfiles.build(runs, races, 1, base, 3, frontness_k=1e-9, tempo_k=1e-9, lead_rank_cut=3)
        s0, s1, s2 = prof.snapshot(0), prof.snapshot(1), prof.snapshot(2)
        self.assertEqual(s0["n_q"][0], 0)                             # 1月のレースは自分の月の騎乗を見ない
        self.assertEqual(s1["n_q"][0], 1)
        self.assertAlmostEqual(s1["frontness"][0], 1.0, places=6)     # 1月のq=0 -> frontness=1
        self.assertAlmostEqual(s1["lead_tempo"][0], 1.0, places=6)    # 基準35 - 実測34 = +1(速く刻む)
        self.assertEqual(s2["n_q"][0], 2)
        self.assertAlmostEqual(s2["frontness"][0], 1 - 0.25, places=6)  # mean q=0.25 (1月と2月)
        self.assertEqual(s1["n_lead"][0], 1)
        self.assertEqual(s2["n_lead"][0], 1)                          # 2月は5着(先頭付近でない)

    def test_unknown_jockey_uses_prior_via_negative_index(self):
        base = pd.Timestamp("2024-01-01")
        runs = pd.DataFrame({"race_id": ["r1"], "date": pd.to_datetime(["2024-01-10"]), "jockey_idx": [0],
                             "q_early": [0.2], "early_rank": [1]})
        races = pd.DataFrame({"race_id": ["r1"], "early_split_sec": [35.0], "early_ref": [35.0], "is_upcoming": [False]})
        prof = JockeyProfiles.build(runs, races, 1, base, 2, 30.0, 20.0, 3)
        snap = prof.snapshot(1)
        self.assertEqual(snap["frontness"][-1], snap["frontness"][-1])
        self.assertAlmostEqual(snap["frontness"][-1], 0.8)            # 事前値 = 1 - 全体平均q


class BaselineWalkForwardTest(unittest.TestCase):
    def _races(self, seed=0):
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
        rows = []
        for d in dates:
            for r in range(3):
                rows.append({"date": d, "track": "05", "surface": "turf", "distance_m": 1600, "layout": "17A",
                             "class_group": "C1", "age_class": "3up", "going": 1, "is_upcoming": False,
                             "win_time_sec": 96 + rng.normal(0, 0.5)})
        return pd.DataFrame(rows)

    def test_prediction_for_a_month_ignores_that_month_and_later_targets(self):
        a = self._races()
        b = a.copy()
        future = b["date"] >= pd.Timestamp("2023-06-01")
        b.loc[future, "win_time_sec"] += 30.0  # 2023-06以降の実測値を大きく改変
        pa = walk_forward_baseline(a, "win_time_sec", pd.Timestamp("2023-01-01"))
        pb = walk_forward_baseline(b, "win_time_sec", pd.Timestamp("2023-01-01"))
        m = a["date"] < pd.Timestamp("2023-06-01")
        np.testing.assert_allclose(pa[m & pa.notna()], pb[m & pb.notna()])
        self.assertTrue(pa[a["date"] < pd.Timestamp("2023-01-01")].isna().all())


class AbilityOOFTest(unittest.TestCase):
    def test_existing_oof_cache_cutoff_precedes_score_date(self):
        path = ROOT / "data" / "cache" / "raceverse" / "ability_oof_pre_test.parquet"
        if not path.exists():
            self.skipTest("ability OOF cache not generated")
        table = pd.read_parquet(path)
        self.assertTrue((table["model_training_cutoff"] < table["score_available_at"]).all())


if __name__ == "__main__":
    unittest.main()

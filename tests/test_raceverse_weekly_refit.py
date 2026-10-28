import unittest

import numpy as np
import pandas as pd

from raceverse.baselines import walk_forward_baseline
from raceverse.jockey_profiles import JockeyProfiles
from raceverse.pace_regression import rolling_oof_predictions
from raceverse.periods import floor_timestamp, next_period, period_index, period_range, period_start


class PeriodHelpersTest(unittest.TestCase):
    def test_week_starts_on_monday_and_weekend_races_share_a_week(self):
        dates = pd.Series(pd.to_datetime(["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-24"]))  # 土, 日, 月, 土
        starts = period_start(dates, "week")
        self.assertEqual(list(starts.dt.strftime("%Y-%m-%d")), ["2026-10-12", "2026-10-12", "2026-10-19", "2026-10-19"])
        self.assertTrue((starts.dt.dayofweek == 0).all())

    def test_month_behaviour_is_unchanged(self):
        dates = pd.Series(pd.to_datetime(["2024-01-31", "2024-03-01"]))
        self.assertEqual(list(period_index(dates, pd.Timestamp("2024-01-01"), "month")), [0, 2])
        self.assertEqual(next_period(pd.Timestamp("2024-01-15"), "month"), pd.Timestamp("2024-02-01"))

    def test_week_index_and_range(self):
        base = pd.Timestamp("2024-01-01")  # 月曜
        dates = pd.Series(pd.to_datetime(["2024-01-06", "2024-01-07", "2024-01-08", "2024-01-20"]))
        self.assertEqual(list(period_index(dates, base, "week")), [0, 0, 1, 2])
        weeks = period_range(pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-22"), "week")
        self.assertEqual([w.strftime("%Y-%m-%d") for w in weeks], ["2024-01-01", "2024-01-08", "2024-01-15"])
        self.assertEqual(floor_timestamp(pd.Timestamp("2024-01-03"), "week"), pd.Timestamp("2024-01-01"))

    def test_invalid_unit_is_rejected(self):
        with self.assertRaises(ValueError):
            period_start(pd.Series(pd.to_datetime(["2024-01-01"])), "day")


class WeeklyAsOfTest(unittest.TestCase):
    def test_baseline_for_a_week_ignores_that_week_and_later_targets(self):
        rng = np.random.default_rng(0)
        rows = [{"date": d, "track": "05", "surface": "turf", "distance_m": 1600, "layout": "17A", "class_group": "C1",
                 "age_class": "3up", "going": 1, "is_upcoming": False, "win_time_sec": 96 + rng.normal(0, 0.5)}
                for d in pd.date_range("2022-01-01", "2023-12-31", freq="D") for _ in range(3)]
        a = pd.DataFrame(rows)
        b = a.copy()
        cutoff = pd.Timestamp("2023-06-12")  # 月曜
        b.loc[b["date"] >= cutoff, "win_time_sec"] += 30.0
        pa = walk_forward_baseline(a, "win_time_sec", pd.Timestamp("2023-01-02"), unit="week")
        pb = walk_forward_baseline(b, "win_time_sec", pd.Timestamp("2023-01-02"), unit="week")
        before = (a["date"] < cutoff) & pa.notna()
        self.assertTrue(before.any())
        np.testing.assert_allclose(pa[before], pb[before])
        # 先週(月曜より前)までの結果を改変すれば、その週の予測は変わる
        c = a.copy()
        c.loc[(c["date"] >= cutoff - pd.Timedelta(days=7)) & (c["date"] < cutoff), "win_time_sec"] += 30.0
        pc = walk_forward_baseline(c, "win_time_sec", pd.Timestamp("2023-01-02"), unit="week")
        week = (a["date"] >= cutoff) & (a["date"] < cutoff + pd.Timedelta(days=7))
        self.assertFalse(np.allclose(pa[week], pc[week]))

    def test_rolling_oof_uses_only_rows_before_the_week(self):
        rng = np.random.default_rng(1)
        n = 800
        dates = pd.Series(pd.date_range("2020-01-01", periods=n, freq="D"))
        x = rng.normal(size=(n, 2))
        y = rng.normal(size=n)
        y2 = y.copy()
        monday = pd.Timestamp("2021-01-04")
        y2[(dates >= monday).to_numpy()] += 50.0
        first = pd.Timestamp("2020-06-01")
        a = rolling_oof_predictions(x, y, np.ones(n), dates, 1.0, first, min_rows=50, unit="week")
        b = rolling_oof_predictions(x, y2, np.ones(n), dates, 1.0, first, min_rows=50, unit="week")
        before = (dates < monday).to_numpy()
        np.testing.assert_allclose(a[before & np.isfinite(a)], b[before & np.isfinite(b)])
        self.assertTrue(np.isnan(a[:50]).all())

    def test_jockey_snapshot_excludes_same_week_and_includes_previous_week(self):
        base = pd.Timestamp("2024-01-01")
        runs = pd.DataFrame({
            "race_id": ["r1", "r2", "r3"], "date": pd.to_datetime(["2024-01-06", "2024-01-13", "2024-01-14"]),
            "jockey_idx": [0, 0, 0], "q_early": [0.0, 0.5, 1.0], "early_rank": [1, 5, 10],
        })
        races = pd.DataFrame({"race_id": ["r1", "r2", "r3"], "early_split_sec": [34.0, 35.0, 36.0],
                              "early_ref": [35.0, 35.0, 35.0], "is_upcoming": [False] * 3})
        prof = JockeyProfiles.build(runs, races, 1, base, 3, 1e-9, 1e-9, 3, unit="week")
        w0, w1, w2 = prof.snapshot(0), prof.snapshot(1), prof.snapshot(2)
        self.assertEqual(w0["n_q"][0], 0)   # 第1週(1/1-1/7)のレースは第1週の騎乗を見ない
        self.assertEqual(w1["n_q"][0], 1)   # 第2週は先週(1/6)の騎乗だけ
        self.assertEqual(w2["n_q"][0], 3)   # 第3週は第1・第2週すべて
        self.assertAlmostEqual(w1["frontness"][0], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()

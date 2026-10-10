import unittest

import numpy as np
import pandas as pd

from raceverse.config import TrackSpeedConfig
from raceverse.meet_history import MeetIndex
from raceverse.track_speed import TrackSpeedBuilder


def _races(extra=None):
    """Nakayama(05)芝の週末開催(土日)を合成。meet A: 2024-01-06..2024-02-04(週末のみ)、meet B: 2024-03-02〜(開幕=土曜)。"""
    rows = []
    def add(date, meet, day, track="05", surface="turf", resid=0.0, going=1):
        for r in range(1, 4):
            rows.append({"race_id": f"{date}-{track}-{surface}-{r}", "date": pd.Timestamp(date), "track": track,
                         "surface": surface, "meet_id": meet, "meet_day": day, "track_resid": resid,
                         "is_upcoming": False, "going": going, "distance_m": 1600, "layout": "17A"})
    for i, d in enumerate(["2024-01-06", "2024-01-07", "2024-01-13", "2024-01-14", "2024-01-20", "2024-01-21"]):
        add(d, "2024-05-01", i + 1, resid=-0.5)
    for i, d in enumerate(["2024-03-02", "2024-03-03", "2024-03-09", "2024-03-10"]):
        add(d, "2024-05-02", i + 1, resid=0.3)
    add("2024-03-09", "2024-05-02", 3, track="06", resid=9.9)           # 別競馬場(混入禁止)
    add("2024-03-09", "2024-05-02", 3, surface="dirt", resid=9.9)       # 別芝ダ(混入禁止)
    for r in (extra or []):
        add(*r)
    df = pd.DataFrame(rows)
    df["is_upcoming"] = False
    return df.sort_values(["date", "race_id"]).reset_index(drop=True)


def _target(df, date, meet, day, going=1):
    row = {"race_id": "TARGET", "date": pd.Timestamp(date), "track": "05", "surface": "turf", "meet_id": meet,
           "meet_day": day, "track_resid": np.nan, "is_upcoming": True, "going": going, "distance_m": 1600, "layout": "17A"}
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def _day(d):
    return int(np.datetime64(pd.Timestamp(d), "D").astype(np.int64))


class MeetReferenceSelectionTest(unittest.TestCase):
    def setUp(self):
        self.cfg = TrackSpeedConfig()

    def _index(self, df):
        return MeetIndex(df, self.cfg.previous_week_window_days, self.cfg.previous_year_window_days, self.cfg.previous_meet_last_days)

    def test_candidates_are_strictly_before_target_and_same_track_surface(self):
        df = _races()
        idx = self._index(df)
        for target in ("2024-01-14", "2024-03-10", "2024-03-03"):
            cand = idx.candidates("05", "turf", _day(target), _day("2024-03-02") if target >= "2024-03" else _day("2024-01-06"))
            self.assertTrue((df.loc[cand.rows, "date"] < pd.Timestamp(target)).all())
            self.assertTrue((df.loc[cand.rows, "track"] == "05").all())
            self.assertTrue((df.loc[cand.rows, "surface"] == "turf").all())
            self.assertTrue((cand.gap_days >= 1).all())

    def test_previous_day_and_previous_week(self):
        df = _races()
        cand = self._index(df).candidates("05", "turf", _day("2024-01-14"), _day("2024-01-06"))
        sources = set(cand.source)
        self.assertIn("previous_day", sources)    # 土曜(1/13)
        self.assertIn("previous_week", sources)   # 前週末(1/6-7)
        self.assertTrue(all(df.loc[r, "date"] == pd.Timestamp("2024-01-13") for r, s in zip(cand.rows, cand.source) if s == "previous_day"))

    def test_opening_week_falls_back_to_previous_meet(self):
        df = _races()
        cand = self._index(df).candidates("05", "turf", _day("2024-03-02"), _day("2024-03-02"))
        self.assertNotIn("previous_day", cand.source)
        self.assertNotIn("previous_week", cand.source)
        self.assertIn("previous_meet", cand.source)
        dates = {df.loc[r, "date"] for r, s in zip(cand.rows, cand.source) if s == "previous_meet"}
        self.assertTrue(dates <= {pd.Timestamp("2024-01-20"), pd.Timestamp("2024-01-21")})  # 直前開催の最終週のみ

    def test_previous_year_same_season_and_no_duplicate_race_ids(self):
        df = _races([("2023-03-04", "2023-05-02", 1, "05", "turf", 0.1, 1), ("2023-03-05", "2023-05-02", 2, "05", "turf", 0.1, 1)])
        cand = self._index(df).candidates("05", "turf", _day("2024-03-02"), _day("2024-03-02"))
        self.assertIn("previous_year_same_season", cand.source)
        ids = df.loc[cand.rows, "race_id"].tolist()
        self.assertEqual(len(ids), len(set(ids)))

    def test_future_races_never_enter_even_if_added(self):
        base = _races()
        future = _races([("2024-03-16", "2024-05-02", 5, "05", "turf", -9.0, 1)])
        a = self._index(base).candidates("05", "turf", _day("2024-03-10"), _day("2024-03-02"))
        b = self._index(future).candidates("05", "turf", _day("2024-03-10"), _day("2024-03-02"))
        np.testing.assert_array_equal(base.loc[a.rows, "race_id"].to_numpy(), future.loc[b.rows, "race_id"].to_numpy())


class TrackSpeedBiasTest(unittest.TestCase):
    def test_bias_sign_shrinkage_and_future_independence(self):
        cfg = TrackSpeedConfig()
        df = _target(_races(), "2024-01-14", "2024-05-01", 4)
        pos = len(df) - 1
        bias = TrackSpeedBuilder(df, cfg).build_as_of(pos)
        self.assertLess(bias.track_bias_sec, 0)                       # 参照は基準より速い(-0.5)
        self.assertGreater(bias.track_bias_sec, -0.5)                 # 縮小で絶対値は原値より小さい
        self.assertEqual(bias.fallback_level, "previous_day")
        self.assertEqual(len(bias.reference_race_ids), len(set(bias.reference_race_ids)))

        poisoned = _races([("2024-02-10", "2024-05-01", 7, "05", "turf", 50.0, 1)])  # 未来の異常値
        poisoned = _target(poisoned, "2024-01-14", "2024-05-01", 4)
        bias2 = TrackSpeedBuilder(poisoned, cfg).build_as_of(len(poisoned) - 1)
        self.assertAlmostEqual(bias.track_bias_sec, bias2.track_bias_sec, places=9)

    def test_going_change_lowers_weight_and_is_flagged(self):
        cfg = TrackSpeedConfig()
        same = _target(_races(), "2024-01-14", "2024-05-01", 4, going=1)
        changed = _target(_races(), "2024-01-14", "2024-05-01", 4, going=3)
        a = TrackSpeedBuilder(same, cfg).build_as_of(len(same) - 1)
        b = TrackSpeedBuilder(changed, cfg).build_as_of(len(changed) - 1)
        self.assertFalse(a.going_changed)
        self.assertTrue(b.going_changed)
        self.assertLess(abs(b.track_bias_sec), abs(a.track_bias_sec))


if __name__ == "__main__":
    unittest.main()

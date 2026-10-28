import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from scripts.raceverse_market_analysis import (
    MODEL_NAMES, distance_band, load_analysis_data, market_comparison,
    odds_band_analysis, top1_rows, winner_logloss,
)


class MarketAnalysisTest(unittest.TestCase):
    def test_analysis_ignores_legacy_full_and_does_not_require_it(self):
        rows = [
            dict(race_id="r1", horse_id=str(horse), umaban=horse, level=level,
                 target=int(horse == 1), finish=horse, p_cal=0.5,
                 win_odds_reference=2.0, win_payout=200 if horse == 1 else 0)
            for level in ("base", "formation", "pace", "full")
            for horse in (1, 2)
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory)
            pd.DataFrame([dict(race_id="r1", surface="turf", distance_m=1400)]).to_csv(
                path / "race_level.csv", index=False)
            pd.DataFrame(rows).to_csv(path / "predictions.csv", index=False)
            with self.assertLogs("scripts.raceverse_market_analysis", level="WARNING"):
                legacy, _ = load_analysis_data(path)
            pd.DataFrame(rows[:-2]).to_csv(path / "predictions.csv", index=False)
            current, _ = load_analysis_data(path)
        pd.testing.assert_frame_equal(legacy, current)
        self.assertNotIn("full", MODEL_NAMES)
        self.assertNotIn("p_full", current)
        self.assertEqual(set(market_comparison(current)["model"]), set(MODEL_NAMES))
        self.assertEqual(len(odds_band_analysis(current)), 4 * 2 * 9)

    def test_distance_band_boundaries(self):
        actual = distance_band(pd.Series([1200, 1400, 1401, 1800, 1801, 2200, 2201])).astype(str).tolist()
        self.assertEqual(actual, ["D1", "D1", "D2", "D2", "D3", "D3", "D4"])

    def test_top1_rows_breaks_ties_by_lower_umaban(self):
        frame = pd.DataFrame(
            {
                "race_id": ["r1", "r1", "r2", "r2"],
                "horse_id": ["a", "b", "c", "d"],
                "umaban": [2, 1, 1, 2],
                "p": [0.5, 0.5, 0.4, 0.6],
            }
        )
        self.assertEqual(top1_rows(frame, "p")["horse_id"].tolist(), ["b", "d"])

    def test_winner_logloss_uses_one_winner_per_race(self):
        frame = pd.DataFrame(
            {
                "race_id": ["r1", "r1", "r2", "r2"],
                "target": [1, 0, 0, 1],
                "p": [0.5, 0.5, 0.75, 0.25],
            }
        )
        expected = -0.5 * (np.log(0.5) + np.log(0.25))
        self.assertAlmostEqual(winner_logloss(frame, "p"), expected)


if __name__ == "__main__":
    unittest.main()

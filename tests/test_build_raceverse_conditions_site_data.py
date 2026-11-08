import csv
import tempfile
import unittest
from pathlib import Path

from scripts.build_raceverse_conditions_site_data import build_payload


class BuildRaceverseConditionsSiteDataTest(unittest.TestCase):
    def test_includes_only_conditions_over_100_percent_with_minimum_sample(self):
        rows = [
            ["base", "Class A", "東京", "芝", "1600m", "良", 30, 100.0, 110.0, 120.0],
            ["pace", "Class B", "京都", "ダート", "1800m", "良", 30, 100.1, 105.0, 95.0],
            ["formation", "3勝クラス", "中山", "芝", "2000m", "良", 31, 150.0, 150.0, 150.0],
            ["base", "Class D", "阪神", "芝", "1400m", "稍重", 50, 130.0, "", 125.0],
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "conditions.csv"
            with input_path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(
                    [
                        "model",
                        "クラス",
                        "競馬場",
                        "芝ダート",
                        "距離",
                        "馬場",
                        "bets",
                        "win_roi_pct",
                        "win_roi_first_half_pct",
                        "win_roi_second_half_pct",
                    ]
                )
                writer.writerows(rows)

            payload = build_payload(input_path)

        self.assertEqual(len(payload["conditions"]), 1)
        self.assertEqual(payload["conditions"][0]["model"], "formation")
        self.assertEqual(payload["conditions"][0]["class"], "3勝クラス")
        self.assertEqual(payload["conditions"][0]["win_roi_pct"], 150.0)


if __name__ == "__main__":
    unittest.main()

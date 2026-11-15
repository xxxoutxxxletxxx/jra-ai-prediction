import csv
import tempfile
import unittest
from pathlib import Path

from scripts.build_raceverse_ai_stats_site_data import build_payload


class BuildRaceverseAiStatsSiteDataTest(unittest.TestCase):
    def test_builds_track_specific_roi_and_tenth_step_ev_bands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            condition_dir = input_dir / "condition_analysis"
            condition_dir.mkdir()
            with (input_dir / "race_level.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["race_id", "track", "date"])
                writer.writeheader()
                writer.writerows([
                    {"race_id": "r1", "track": "05", "date": "2025-01-01"},
                    {"race_id": "r2", "track": "08", "date": "2026-01-01"},
                    {"race_id": "r3", "track": "01", "date": "2025-01-01"},
                ])
            with (input_dir / "predictions.csv").open("w", newline="") as file:
                fields = ["race_id", "level", "umaban", "p_cal", "win_odds_reference", "win_payout"]
                fields.append("target")
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows([
                    {"race_id": "r1", "level": "formation", "umaban": "2",
                     "p_cal": "0.4", "win_odds_reference": "2", "win_payout": "0", "target": "0"},
                    {"race_id": "r1", "level": "formation", "umaban": "1",
                     "p_cal": "0.5", "win_odds_reference": "2", "win_payout": "200", "target": "1"},
                    {"race_id": "r2", "level": "formation", "umaban": "1",
                     "p_cal": "0.2", "win_odds_reference": "3", "win_payout": "", "target": "0"},
                    {"race_id": "r3", "level": "formation", "umaban": "1",
                     "p_cal": "1", "win_odds_reference": "2", "win_payout": "200", "target": "1"},
                ])
            with (condition_dir / "roi_by_combination.csv").open("w", newline="") as file:
                fields = [
                    "model", "クラス", "競馬場", "芝ダート", "距離", "馬場", "bets",
                    "win_hits", "win_hit_rate_pct", "win_roi_pct", "place_roi_pct",
                ]
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "model": "formation", "クラス": "1勝クラス", "競馬場": "東京",
                    "芝ダート": "芝", "距離": "1600m", "馬場": "良", "bets": "1",
                    "win_hits": "1", "win_hit_rate_pct": "100", "win_roi_pct": "200",
                    "place_roi_pct": "100",
                })

            payload = build_payload(input_dir)

        tokyo, kyoto, fukushima = payload["tracks"]
        self.assertEqual(tokyo["overall"], {"bets": 1, "hits": 1, "roi_pct": 200.0})
        self.assertEqual(tokyo["yearly"][0]["year"], 2025)
        ev_at_one = next(row for row in tokyo["ev_bands"] if row["label"] == "1.0以上1.1未満")
        self.assertEqual(ev_at_one["bets"], 1)
        self.assertEqual(len(tokyo["ev_bands"]), 20)
        self.assertEqual(tokyo["ev_bands"][0]["bets"], 0)
        self.assertIsNone(tokyo["ev_bands"][0]["roi_pct"])
        self.assertEqual(tokyo["conditions"][0]["class"], "1勝クラス")
        self.assertEqual(kyoto["overall"]["bets"], 1)
        self.assertEqual(fukushima["overall"]["bets"], 0)


if __name__ == "__main__":
    unittest.main()

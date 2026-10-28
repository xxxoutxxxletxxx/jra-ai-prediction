import unittest

import pandas as pd

from scripts.raceverse_roi_strategy_validation import (
    _threshold,
    make_top_candidates,
    max_drawdown,
    max_losing_streak,
)


class RoiStrategyValidationTest(unittest.TestCase):
    def test_losing_streak_and_drawdown_include_initial_stake_peak(self):
        self.assertEqual(max_losing_streak([False, False, True, False]), 2)
        self.assertEqual(max_drawdown([0, 300, 0]), 100)
        self.assertEqual(max_drawdown([]), 0)

    def test_threshold_is_selected_from_history_only_quantile(self):
        self.assertAlmostEqual(_threshold(pd.Series([0.1, 0.2, 0.3, 0.4]), 0.5), 0.25)
        self.assertTrue(pd.isna(_threshold(pd.Series([float("nan")]), 0.2)))

    def test_consensus_uses_majority_and_base_fallback_when_all_differ(self):
        rows = []
        probabilities = {
            "r1": {"base": {1: 0.6, 2: 0.4}, "formation": {1: 0.55, 2: 0.45}, "pace": {1: 0.45, 2: 0.55}},
            "r2": {"base": {1: 0.5, 2: 0.3, 3: 0.2}, "formation": {1: 0.2, 2: 0.5, 3: 0.3},
                   "pace": {1: 0.3, 2: 0.2, 3: 0.5}},
        }
        winners = {"r1": 1, "r2": 2}
        for race_id, by_model in probabilities.items():
            for model, by_horse in by_model.items():
                for horse, probability in by_horse.items():
                    rows.append(
                        {
                            "race_id": race_id,
                            "horse_id": str(horse),
                            "umaban": horse,
                            "level": model,
                            "p_cal": probability,
                            "target": int(horse == winners[race_id]),
                            "win_payout": 200.0 if horse == winners[race_id] else 0.0,
                            "win_odds_reference": 2.0 + horse,
                            "date": pd.Timestamp("2024-01-01"),
                            "year": 2024,
                            "racecourse": "東京",
                            "surface_name": "芝",
                            "distance_band": "1500〜1800m",
                            "going_name": "良",
                            "grade_group": "G3",
                            "grade_code_raw": "C",
                            "analysis_period": "2024-01-01/2024-01-01",
                        }
                    )
        candidates, _ = make_top_candidates(pd.DataFrame(rows))
        consensus = candidates.loc[candidates["model"].eq("consensus")].set_index("race_id")
        self.assertEqual(consensus.loc["r1", "selected_horse_id"], "1")
        self.assertEqual(consensus.loc["r1", "top1_agreement_votes"], 2)
        self.assertTrue(bool(consensus.loc["r1", "hit"]))
        self.assertEqual(consensus.loc["r2", "top1_agreement_votes"], 1)
        self.assertEqual(consensus.loc["r2", "selected_horse_id"], "1")
        self.assertFalse(bool(consensus.loc["r2", "hit"]))


if __name__ == "__main__":
    unittest.main()

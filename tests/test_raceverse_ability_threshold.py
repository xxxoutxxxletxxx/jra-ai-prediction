import unittest

import numpy as np
import pandas as pd

from raceverse.ability_threshold import AbilityThreshold, adjust_probabilities, select_top1


class AbilityThresholdTest(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "race_id": ["a", "a", "a", "b", "b"],
            "umaban": [1, 2, 3, 1, 2],
            "p": [0.50, 0.30, 0.20, 0.60, 0.40],
            "ability_z": [0.2, 1.0, -0.8, np.nan, np.nan],
            "required_ability_z": [0.5, 0.5, 0.5, 0.7, 0.7],
            "female_only": [False, False, False, True, True],
        })

    def test_none_preserves_probabilities_and_selects_model_top1(self):
        adjusted = adjust_probabilities(self.frame, "p", AbilityThreshold())
        np.testing.assert_allclose(adjusted["adjusted_probability"], self.frame["p"])
        top = select_top1(adjusted)
        self.assertEqual(top["umaban"].tolist(), [1, 1])

    def test_soft_penalty_is_normalized_and_never_assigns_zero_probability(self):
        adjusted = adjust_probabilities(
            self.frame, "p", AbilityThreshold(mode="soft", strength=2.0)
        )
        self.assertTrue((adjusted["adjusted_probability"] > 0).all())
        np.testing.assert_allclose(
            adjusted.groupby("race_id")["adjusted_probability"].sum().to_numpy(),
            np.ones(2),
        )
        self.assertLess(
            adjusted.loc[adjusted["umaban"] == 3, "adjusted_probability"].iloc[0],
            self.frame.loc[self.frame["umaban"] == 3, "p"].iloc[0],
        )

    def test_hard_exclusion_changes_purchase_candidate_not_probability(self):
        adjusted = adjust_probabilities(
            self.frame, "p", AbilityThreshold(mode="hard", strength=0.0)
        )
        self.assertGreater((adjusted["adjusted_probability"] > 0).sum(), 0)
        top = select_top1(adjusted)
        self.assertEqual(top["umaban"].tolist(), [2, 1])
        self.assertFalse(top["eligibility_fallback"].any())

    def test_zero_tilt_assigns_zero_below_cutoff_and_tilts_qualified_runners(self):
        source = self.frame.copy()
        source.loc[(source["race_id"] == "a") & (source["umaban"] == 1), "ability_z"] = 0.6
        adjusted = adjust_probabilities(
            source,
            "p",
            AbilityThreshold(mode="zero_tilt", strength=1.0),
        )
        race_a = adjusted[adjusted["race_id"] == "a"].set_index("umaban")
        self.assertEqual(race_a.loc[3, "adjusted_probability"], 0.0)
        self.assertGreater(race_a.loc[1, "adjusted_probability"], 0.0)
        expected_ratio = (0.3 * np.exp(0.5)) / (0.5 * np.exp(0.1))
        actual_ratio = (
            race_a.loc[2, "adjusted_probability"] / race_a.loc[1, "adjusted_probability"]
        )
        self.assertAlmostEqual(actual_ratio, expected_ratio)
        self.assertNotAlmostEqual(actual_ratio, 0.3 / 0.5)
        race_b = adjusted[adjusted["race_id"] == "b"].set_index("umaban")
        np.testing.assert_allclose(race_b["adjusted_probability"], [0.6, 0.4])
        np.testing.assert_allclose(
            adjusted.groupby("race_id")["adjusted_probability"].sum().to_numpy(),
            np.ones(2),
        )

    def test_zero_tilt_falls_back_when_no_known_runner_meets_cutoff(self):
        source = self.frame.copy()
        source.loc[source["race_id"] == "a", "ability_z"] = -10.0
        source.loc[source["race_id"] == "a", "required_ability_z"] = 10.0
        adjusted = adjust_probabilities(
            source,
            "p",
            AbilityThreshold(mode="zero_tilt", strength=1.0),
        )
        race_a = adjusted[adjusted["race_id"] == "a"]
        np.testing.assert_allclose(race_a["adjusted_probability"], [0.5, 0.3, 0.2])
        self.assertTrue(race_a["candidate_eligible"].all())
        self.assertTrue(race_a["threshold_fallback"].all())

    def test_all_excluded_and_unknown_ability_use_safe_fallback(self):
        source = self.frame.copy()
        source.loc[source["race_id"] == "a", "ability_z"] = -10.0
        source.loc[source["race_id"] == "a", "required_ability_z"] = 10.0
        adjusted = adjust_probabilities(source, "p", AbilityThreshold(mode="hard"))
        top = select_top1(adjusted)
        race_a = top[top["race_id"] == "a"].iloc[0]
        race_b = top[top["race_id"] == "b"].iloc[0]
        self.assertEqual(race_a["umaban"], 1)
        self.assertTrue(race_a["eligibility_fallback"])
        self.assertTrue(race_b["candidate_eligible"])
        self.assertFalse(race_b["eligibility_fallback"])

    def test_female_only_scope_does_not_adjust_mixed_races(self):
        adjusted = adjust_probabilities(
            self.frame,
            "p",
            AbilityThreshold(mode="soft", strength=1.0, scope="female_only"),
        )
        np.testing.assert_allclose(
            adjusted.loc[adjusted["race_id"] == "a", "adjusted_probability"],
            self.frame.loc[self.frame["race_id"] == "a", "p"],
        )
        self.assertTrue(np.isfinite(adjusted["adjusted_probability"]).all())

    def test_invalid_probabilities_are_rejected(self):
        invalid = self.frame.copy()
        invalid.loc[0, "p"] = np.nan
        with self.assertRaisesRegex(ValueError, "probabilities must be finite"):
            adjust_probabilities(invalid, "p", AbilityThreshold())


if __name__ == "__main__":
    unittest.main()

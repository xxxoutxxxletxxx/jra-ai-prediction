from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src import ranker_group_ablation as ab
from src import ranker_group_ablation_analysis as an
from src import ranker_walk_forward_backtest as wf


class GroupClassificationTest(unittest.TestCase):
    def test_groups_partition_the_production_86_features(self) -> None:
        report = ab.classification_report()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["classified_count"], 86)
        self.assertEqual(ab.mask_to_features(ab.ALL_ON_MASK), ab.PRODUCTION_FEATURES)

    def test_every_combination_is_unique_and_non_empty(self) -> None:
        masks = [ab.combo_index_to_mask(i) for i in range(1, ab.N_COMBOS + 1)]
        self.assertEqual(len(set(masks)), 4095)
        self.assertNotIn("0" * 12, masks)
        self.assertEqual(masks[-1], "1" * 12)
        self.assertEqual(ab.mask_to_groups("100000000001"), ["G1", "G12"])


class FastPathParityTest(unittest.TestCase):
    def test_vectorised_softmax_matches_production_softmax(self) -> None:
        rng = np.random.default_rng(1)
        race_ids = pd.Series(np.repeat([f"r{i}" for i in range(20)], rng.integers(5, 16, size=20)))
        scores = rng.normal(size=len(race_ids))
        starts = ab.segment_starts(race_ids.to_numpy())
        lengths = np.diff(np.append(starts, len(race_ids)))
        for temperature in wf.TEMPERATURES:
            fast = ab.softmax_segments(scores, starts, lengths, float(temperature))
            slow = wf.softmax_by_race(scores, race_ids, float(temperature))
            np.testing.assert_allclose(fast, slow, rtol=0, atol=1e-12)


class ContributionAnalysisTest(unittest.TestCase):
    def test_additive_value_has_exact_marginals_and_zero_interaction(self) -> None:
        weights = np.arange(1, 13) / 100.0
        values = np.full(an.N_COMBO_SLOTS, np.nan)
        for combo in range(1, an.N_COMBO_SLOTS):
            values[combo] = -sum(weights[i] for i in range(12) if combo >> i & 1)
        table = an.group_contribution_table(values)
        for _, row in table.iterrows():
            self.assertAlmostEqual(row["mean_delta"], -weights[ab.GROUP_KEYS.index(row["group"])])
            self.assertEqual(row["share_improved"], 1.0)
        self.assertAlmostEqual(an.interaction_effects(values, 2, 3)["interaction"].abs().max(), 0.0)

    def test_synergy_is_detected_with_negative_interaction(self) -> None:
        values = np.zeros(an.N_COMBO_SLOTS)
        for combo in range(an.N_COMBO_SLOTS):
            values[combo] = -0.1 if (combo & 0b11) == 0b11 else 0.0
        effect = an.interaction_effects(values, 0, 1)
        self.assertTrue((effect["interaction"] < 0).all())


if __name__ == "__main__":
    unittest.main()

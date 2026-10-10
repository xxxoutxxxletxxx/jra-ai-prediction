import unittest

import numpy as np

from raceverse.config import FormationConfig
from raceverse.formation_sampler import anchor_groups, arrange_formation, history_weights, sample_formation
from raceverse_fixtures import K, make_ctx, make_profiles_arrays

CFG = FormationConfig()


class RecencyWeightTest(unittest.TestCase):
    def test_default_weights_two_latest_equal_then_decrease_by_one(self):
        w = np.asarray(CFG.recency_weights)
        self.assertEqual(w[0], w[1])
        self.assertEqual(w[0], w.max())
        self.assertTrue(np.all(np.diff(w[1:]) == -1))
        self.assertEqual(list(w[2:]), [9, 8, 7, 6, 5, 4, 3, 2])

    def test_normalised_probability_for_ten_runs(self):
        hist = np.full((1, K), 0.5, dtype=np.float32)
        p = history_weights(hist, np.asarray(CFG.recency_weights))[0]
        self.assertAlmostEqual(p[0], 10 / 64)
        self.assertAlmostEqual(p[1], 10 / 64)
        self.assertAlmostEqual(p[:2].sum(), 0.3125)
        self.assertAlmostEqual(p.sum(), 1.0)

    def test_missing_runs_renormalise_and_cold_start_is_zero(self):
        hist = np.full((2, K), np.nan, dtype=np.float32)
        hist[0, :3] = [0.1, 0.2, 0.3]
        p = history_weights(hist, np.asarray(CFG.recency_weights))
        self.assertAlmostEqual(p[0].sum(), 1.0)
        self.assertAlmostEqual(p[0, 0], 10 / 29)
        self.assertEqual(p[1].sum(), 0.0)


class JockeyChangeTest(unittest.TestCase):
    def setUp(self):
        self.frontness, _ = make_profiles_arrays()

    def _ctx_single_run(self, past_jockey, current_jockey, q=0.5):
        ctx = make_ctx(n=6, seed=1)
        ctx.hist_q[:] = np.nan
        ctx.hist_q[:, 0] = q
        ctx.hist_j[:] = -1
        ctx.hist_j[:, 0] = past_jockey
        ctx.jockey_idx[:] = current_jockey
        return ctx

    def test_same_jockey_means_no_adjustment(self):
        ctx = self._ctx_single_run(2, 2)
        f = sample_formation(ctx, np.random.default_rng(0), 50, CFG, self.frontness)
        np.testing.assert_array_equal(f.q_adj, f.q_sampled)
        self.assertFalse(f.adjusted.any())

    def test_more_front_jockey_moves_forward_and_less_front_moves_back(self):
        ctx = self._ctx_single_run(2, 4)  # frontness(4) > frontness(2)
        f = sample_formation(ctx, np.random.default_rng(0), 10, CFG, self.frontness)
        expected = 0.5 - CFG.jockey_change_alpha * (self.frontness[4] - self.frontness[2])
        np.testing.assert_allclose(f.q_adj, expected)
        ctx = self._ctx_single_run(4, 0)
        f = sample_formation(ctx, np.random.default_rng(0), 10, CFG, self.frontness)
        self.assertTrue((f.q_adj > 0.5).all())

    def test_clipped_to_unit_interval(self):
        ctx = self._ctx_single_run(0, 4, q=0.02)
        f = sample_formation(ctx, np.random.default_rng(0), 10, CFG, self.frontness)
        self.assertTrue(((f.q_adj >= 0) & (f.q_adj <= 1)).all())

    def test_unknown_past_jockey_is_not_treated_as_change(self):
        ctx = self._ctx_single_run(-1, 3)
        f = sample_formation(ctx, np.random.default_rng(0), 10, CFG, self.frontness)
        np.testing.assert_array_equal(f.q_adj, f.q_sampled)
        self.assertGreater(f.unknown_jockey_runs, 0)


class EarlyFormationTest(unittest.TestCase):
    def test_anchor_grouping_does_not_chain(self):
        q = np.array([[0.00, 0.05, 0.10, 0.15, 0.30]])
        g = anchor_groups(q, 0.08)[0]
        self.assertEqual(list(g), [0, 0, 1, 1, 2])  # 0.10 は先頭(0.00)から0.08超なので新グループ

    def test_lateral_order_is_horse_number_ascending_within_group(self):
        # 馬番1,2,3,4 の q が同一グループ内で逆順 → 内外は馬番昇順
        q = np.array([[0.04, 0.03, 0.02, 0.01, 0.90]])
        group, slot, order, _ = arrange_formation(q, 0.08)
        self.assertTrue((group[0, :4] == 0).all())
        self.assertEqual(list(slot[0, :4]), [0, 1, 2, 3])
        self.assertEqual(list(order[0, :4]), [0, 1, 2, 3])
        self.assertEqual(slot[0, 4], 0)
        self.assertEqual(group[0, 4], 1)

    def test_same_seed_reproduces_and_different_field_sizes_work(self):
        frontness, _ = make_profiles_arrays()
        for n in (4, 9, 18):
            ctx = make_ctx(n=n, seed=n, cold_idx=(0,))
            a = sample_formation(ctx, np.random.default_rng(7), 200, CFG, frontness)
            b = sample_formation(ctx, np.random.default_rng(7), 200, CFG, frontness)
            np.testing.assert_array_equal(a.q_adj, b.q_adj)
            self.assertTrue(a.cold_start[0])
            self.assertEqual(a.group.shape, (200, n))
            self.assertTrue((np.sort(a.early_order, axis=1) == np.arange(n)).all())


if __name__ == "__main__":
    unittest.main()

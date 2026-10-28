import unittest

import numpy as np

from raceverse.config import RaceverseConfig
from raceverse.formation_sampler import arrange_formation
from raceverse.pace_features import pace_features
from raceverse.pace_impact import formation_from_actual_q
from raceverse.schemas import Formation
from raceverse.simulator import check_invariants, simulate_race
from raceverse_fixtures import make_bundle, make_ctx, make_snapshot


class SimulationInvariantsTest(unittest.TestCase):
    def setUp(self):
        self.cfg = RaceverseConfig()
        self.bundle = make_bundle()
        self.snap = make_snapshot()
        self.ctx = make_ctx(n=12, seed=4)

    def _run(self, level="pace", seed=11, n=2000, ctx=None):
        return simulate_race(ctx or self.ctx, self.bundle, self.snap, self.cfg, n_sims=n,
                             perf_level=level, seed=seed, keep_samples=True)

    def test_invariants_for_all_levels(self):
        for level in ("base", "formation", "pace"):
            result = self._run(level)
            checks = check_invariants(result)
            self.assertTrue(all(checks.values()), (level, checks))

    def test_retired_full_rejected_even_with_legacy_bundle_entry(self):
        self.bundle.perf_models["full"] = self.bundle.perf_models["formation"]
        with self.assertRaisesRegex(ValueError, "unsupported RACEVERSE performance level: full"):
            self._run(level="full")

    def test_same_seed_reproduces_and_different_seed_differs(self):
        a, b, c = self._run(seed=3), self._run(seed=3), self._run(seed=4)
        np.testing.assert_array_equal(a.horses["win_probability"], b.horses["win_probability"])
        self.assertFalse(np.array_equal(a.horses["win_probability"], c.horses["win_probability"]))

    def test_winner_has_zero_margin_and_times_are_monotone(self):
        r = self._run()
        ranks, margin, t = r.samples["ranks"], r.samples["margin"], r.samples["horse_time"]
        winner_margin = np.take_along_axis(margin, ranks.argmin(axis=1)[:, None], axis=1)
        self.assertTrue(np.allclose(winner_margin, 0))
        self.assertTrue((margin >= 0).all())
        order_by_time = np.argsort(t, axis=1, kind="stable")
        order_by_rank = np.argsort(ranks, axis=1)
        np.testing.assert_array_equal(order_by_time, order_by_rank)
        np.testing.assert_allclose(t.min(axis=1), r.samples["win_time"])

    def test_pace_is_continuous_and_bucket_applied_after_sampling(self):
        r = self._run()
        pace = r.samples["pace_delta"]
        self.assertGreater(len(np.unique(pace.round(6))), 1500)
        self.assertAlmostEqual(sum(r.race["pace_display_probabilities"].values()), 1.0)
        # 表示区分は連続値からの事後分類: 速い(小さい)ほど番号が小さい
        order = np.argsort(pace)
        self.assertTrue(np.all(np.diff(r.samples["bucket"][order]) >= 0))

    def test_pace_is_a_deterministic_function_of_the_sampled_formation(self):
        r = self._run(n=400)
        q = r.samples["q_adj"]
        threshold = self.cfg.formation.group_threshold
        same = np.repeat(q[:1], 5, axis=0)
        group, slot, early_order, order_q = arrange_formation(same, threshold)
        repeated = Formation(same, same, np.zeros_like(same, dtype=bool), group, slot, early_order, order_q,
                             np.zeros(self.ctx.n, dtype=bool), 0)
        pred = self.bundle.pace_model.predict(pace_features(self.ctx, repeated, self.snap))
        self.assertEqual(len(np.unique(pred)), 1)  # 同じ隊列・騎手・開催条件ならペースは同じ
        single = formation_from_actual_q(q[0], threshold)
        expected = self.bundle.pace_bounds.clip("turf_mile", self.bundle.pace_model.predict(
            pace_features(self.ctx, single, self.snap)))
        self.assertAlmostEqual(float(r.samples["pace_delta"][0]), float(expected[0]), places=9)  # 乱数の上乗せなし

    def test_conditional_win_probability_is_nan_when_bucket_never_occurs(self):
        r = self._run(n=50)
        counts = r.horses["pace_condition_sample_count"].iloc[0]
        for name, count in counts.items():
            if count == 0:
                self.assertTrue(r.horses[f"win_prob_{name}"].isna().all())

    def test_weighted_conditional_wins_equal_overall(self):
        r = self._run(n=4000)
        total = np.zeros(self.ctx.n)
        counts = r.horses["pace_condition_sample_count"].iloc[0]
        for name, count in counts.items():
            if count:
                total += (count / r.n_sims) * r.horses[f"win_prob_{name}"].to_numpy()
        np.testing.assert_allclose(total, r.horses["win_probability"].to_numpy(), atol=1e-9)

    def test_winning_time_unavailable_when_no_track_context(self):
        ctx = make_ctx(n=8, seed=5, with_track=False)
        r = self._run(ctx=ctx)
        self.assertEqual(r.race["winning_time_status"], "unavailable")
        self.assertNotIn("expected_winning_time_sec", r.race)
        self.assertAlmostEqual(r.horses["win_probability"].sum(), 1.0)

    def test_missing_pace_reference_disables_pace_terms_and_warns(self):
        ctx = make_ctx(n=8, seed=6)
        ctx.early_ref = float("nan")
        r = self._run(ctx=ctx)
        self.assertEqual(r.perf_level, "formation")
        self.assertTrue(any("pace reference unavailable" in w for w in r.warnings))

    def test_stronger_ability_gets_higher_win_probability_on_average(self):
        r = self._run(level="base", n=6000)
        corr = np.corrcoef(self.ctx.ability, r.horses["win_probability"])[0, 1]
        self.assertGreater(corr, 0.8)


if __name__ == "__main__":
    unittest.main()

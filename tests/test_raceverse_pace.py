import unittest

import numpy as np
import pandas as pd

from raceverse.config import FormationConfig
from raceverse.formation_sampler import sample_formation
from raceverse.pace_display import fit_display_thresholds, pace_display_bucket, pace_display_bucket_index
from raceverse.pace_features import FEATURE_NAMES, pace_features
from raceverse.pace_regression import fit_pace_regressor, rolling_oof_predictions
from raceverse.pace_residuals import PaceBounds, PaceResidualSampler
from raceverse_fixtures import make_ctx, make_snapshot


class PaceLinearRegressionTest(unittest.TestCase):
    def test_target_is_continuous_seconds_and_ridge_recovers_signal(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(5000, 3))
        y = 0.4 * x[:, 0] - 0.2 * x[:, 1] + rng.normal(0, 0.3, 5000)  # 連続値(秒)
        self.assertFalse(np.array_equal(y, y.astype(int)))
        model = fit_pace_regressor(x, y, np.full(5000, 1 / 16), 1.0)
        coef = model.named_steps["ridge"].coef_ / model.named_steps["scale"].scale_
        np.testing.assert_allclose(coef[:2], [0.4, -0.2], atol=0.03)
        self.assertEqual(model.predict(x[:3]).dtype, np.float64)

    def test_scaler_is_fit_on_training_only(self):
        rng = np.random.default_rng(1)
        x = np.vstack([rng.normal(0, 1, (500, 2)), rng.normal(50, 1, (500, 2))])
        y = rng.normal(size=1000)
        dates = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="D"))
        pred = rolling_oof_predictions(x, y, np.ones(1000), dates, 1.0, pd.Timestamp("2020-03-01"), min_rows=50)
        self.assertTrue(np.isnan(pred[:50]).all())  # 学習不足/初期月はNaN(未来で補完しない)
        self.assertTrue(np.isfinite(pred[200]))

    def test_features_only_depend_on_sampled_formation_and_prerace_info(self):
        ctx = make_ctx(n=12, seed=3)
        snap = make_snapshot()
        form = sample_formation(ctx, np.random.default_rng(0), 64, FormationConfig(), snap["frontness"])
        x = pace_features(ctx, form, snap)
        self.assertEqual(x.shape, (64, len(FEATURE_NAMES)))
        self.assertTrue(np.isfinite(x).all())
        for name in FEATURE_NAMES:
            for banned in ("actual", "result", "finish", "corner_pos", "payout"):
                self.assertNotIn(banned, name)


class PaceResidualAndDisplayTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(2)
        self.groups = np.array(["turf_mile"] * 1000)
        self.y = rng.normal(0, 0.8, 1000)
        self.sampler = PaceResidualSampler.fit(self.groups, rng.normal(0, 0.8, 1000), np.full(1000, 0.01), self.y,
                                               [0.001, 0.999], 100)

    def test_draw_is_reproducible_by_seed_and_bounded(self):
        mu = np.zeros(2000)
        a = self.sampler.draw(np.random.default_rng(5), "turf_mile", mu)
        b = self.sampler.draw(np.random.default_rng(5), "turf_mile", mu)
        np.testing.assert_array_equal(a, b)
        lo, hi = self.sampler.bounds_for("turf_mile")
        self.assertTrue((a >= lo).all() and (a <= hi).all())
        self.assertGreater(a.std(), 0.3)

    def test_unknown_group_falls_back_with_warning(self):
        self.sampler.draw_error(np.random.default_rng(0), "dirt_long", 10)
        self.assertTrue(self.sampler.warnings)

    def test_display_buckets_faster_pace_means_faster_label_and_order_enforced(self):
        th = fit_display_thresholds(self.groups, self.y, [0.1, 0.3, 0.7, 0.9])["__global__"]
        self.assertTrue(np.all(np.diff(th) > 0))
        self.assertEqual(pace_display_bucket(-5.0, th), "VERY_FAST")
        self.assertEqual(pace_display_bucket(5.0, th), "VERY_SLOW")
        idx = pace_display_bucket_index(np.linspace(-3, 3, 200), th)
        self.assertTrue(np.all(np.diff(idx) >= 0))
        with self.assertRaises(ValueError):
            pace_display_bucket_index(np.array([0.0]), np.array([0.3, 0.2, 0.5, 0.9]))

    def test_thresholds_are_not_reestimated_on_new_data(self):
        th = fit_display_thresholds(self.groups, self.y, [0.1, 0.3, 0.7, 0.9])["__global__"].copy()
        pace_display_bucket_index(np.random.default_rng(0).normal(5, 1, 100), th)
        np.testing.assert_array_equal(th, fit_display_thresholds(self.groups, self.y, [0.1, 0.3, 0.7, 0.9])["__global__"])


if __name__ == "__main__":
    unittest.main()

import dataclasses
import unittest

import numpy as np
import pandas as pd

from raceverse.config import CourseBiasConfig, RaceverseConfig
from raceverse.course_bias import (CourseBiasEngine, bias_feature_block, draw_group, pace_bucket, style_from_q,
                                   style_ids)
from raceverse.performance import GOING_ABILITY_FEATURES, PERF_FEATURES, PERF_LEVELS, level_indices, perf_features
from raceverse.simulator import check_invariants, simulate_race
from raceverse_fixtures import make_bias, make_bundle, make_ctx, make_snapshot


def synthetic_history(seed: int = 0, n_days: int = 40, races_per_day: int = 4, field: int = 12):
    """同じコースで開催日ごとにレースを並べた合成データ(逃げ有利・内枠有利を仕込む)。"""
    rng = np.random.default_rng(seed)
    races, runs = [], []
    for day in range(n_days):
        date = pd.Timestamp("2024-01-06") + pd.Timedelta(days=7 * day)
        for r in range(races_per_day):
            rid = f"R{day:03d}{r}"
            races.append({"race_id": rid, "date": date, "surface": "turf", "track": "05", "distance_m": 1600, "track_cd": "11",
                          "course_kubun": "A", "meet_id": f"2024-05-{day // 8 + 1:02d}", "meet_day": day % 8 + 1,
                          "going": 1, "pace_delta": float(rng.normal(0, 0.6)), "field_size": field, "is_upcoming": False})
            q = rng.permutation(field) / (field - 1)
            wk = np.clip(np.ceil(np.arange(1, field + 1) * 8.0 / field).astype(int), 1, 8)
            score = -2.0 * q - 0.15 * wk + rng.gumbel(size=field)  # 前・内ほど勝ちやすい
            finish = np.empty(field, dtype=int)
            finish[np.argsort(-score)] = np.arange(1, field + 1)
            rank = np.argsort(np.argsort(q)) + 1
            for i in range(field):
                runs.append({"race_id": rid, "wakuban": int(wk[i]), "finish": int(finish[i]), "q_early": float(q[i]),
                             "early_rank": int(rank[i])})
    races = pd.DataFrame(races)
    return races, pd.DataFrame(runs)


class StyleAssignmentTest(unittest.TestCase):
    def test_only_the_front_most_horse_is_lead_and_thresholds_apply(self):
        q = np.array([[0.05, 0.0, 0.3, 0.31, 0.7, 0.71, 1.0], [0.4, 0.2, 0.9, 0.0, 0.5, 0.6, 0.1]])
        sid = style_ids(q, 0.30, 0.70)
        self.assertEqual(sid[0].tolist(), [1, 0, 1, 2, 2, 3, 3])
        self.assertEqual((sid == 0).sum(axis=1).tolist(), [1, 1])

    def test_history_style_uses_actual_first_corner_rank(self):
        sid = style_from_q(np.array([0.0, 0.1, 0.5, 0.9]), np.array([True, False, False, False]), 0.30, 0.70)
        self.assertEqual(sid.tolist(), [0, 1, 2, 3])

    def test_draw_group_and_pace_bucket(self):
        self.assertEqual(draw_group(np.arange(1, 9)).tolist(), [0, 0, 0, 1, 1, 1, 2, 2])
        self.assertEqual(pace_bucket(np.array([-1.0, 0.0, 1.0]), [-0.35, 0.35]).tolist(), [0, 1, 2])


class AsOfEngineTest(unittest.TestCase):
    def setUp(self):
        self.races, self.runs = synthetic_history()
        self.cfg = CourseBiasConfig()
        self.target_pos = int(self.races.index[self.races["date"] == pd.Timestamp("2024-01-06") + pd.Timedelta(days=7 * 20)][1])

    def _bias(self, runs, races=None):
        engine = CourseBiasEngine(self.races if races is None else races, runs, self.cfg)
        return engine.get(self.target_pos)

    def _arrays(self, bias):
        return [getattr(bias, f.name) for f in dataclasses.fields(bias) if isinstance(getattr(bias, f.name), np.ndarray)]

    def test_no_history_gives_neutral_features(self):
        engine = CourseBiasEngine(self.races, self.runs, self.cfg)
        bias = engine.get(0)  # 最初の開催日: 参照できる過去が無い
        for arr in (bias.style_win, bias.style_place, bias.draw_win, bias.draw_place, bias.inter, bias.pstyle_win,
                    bias.pstyle_place, bias.pdraw):
            np.testing.assert_allclose(arr, 0.0, atol=1e-12)
        self.assertEqual(bias.style_n.sum(), 0)

    def test_results_on_or_after_the_race_date_are_never_used(self):
        date = self.races.at[self.target_pos, "date"]
        base = self._bias(self.runs)
        shuffled = self.runs.copy()
        late = self.races.loc[self.races["date"] >= date, "race_id"]  # 同日・未来の結果をまるごと入れ替える
        mask = shuffled["race_id"].isin(set(late))
        rng = np.random.default_rng(1)
        shuffled.loc[mask, "finish"] = shuffled.loc[mask].groupby("race_id")["finish"].transform(lambda s: rng.permutation(s.to_numpy()))
        shuffled.loc[mask, "q_early"] = 1.0 - shuffled.loc[mask, "q_early"]
        for a, b in zip(self._arrays(base), self._arrays(self._bias(shuffled))):
            np.testing.assert_array_equal(a, b)

    def test_past_results_do_change_the_statistics(self):
        date = self.races.at[self.target_pos, "date"]
        base = self._bias(self.runs)
        flipped = self.runs.copy()
        past = flipped["race_id"].isin(set(self.races.loc[self.races["date"] < date, "race_id"]))
        flipped.loc[past, "finish"] = flipped.loc[past].groupby("race_id")["finish"].transform(lambda s: s.max() + 1 - s)
        self.assertFalse(np.allclose(base.style_win, self._bias(flipped).style_win))

    def test_planted_front_and_inner_advantage_is_recovered_with_shrinkage(self):
        bias = self._bias(self.runs)
        self.assertGreater(bias.style_win[0], bias.style_win[3])        # 逃げ > 追込
        self.assertGreater(bias.draw_win[0], bias.draw_win[7])          # 内枠 > 外枠
        self.assertTrue(np.isfinite(bias.inter).all() and np.abs(bias.inter).max() < 0.6)
        thin = CourseBiasEngine(self.races[self.races["race_id"].isin(set(self.races["race_id"][:6]))],
                                self.runs, self.cfg)
        self.assertEqual(thin.H["race_id"].nunique(), 6)

    def test_few_samples_shrink_toward_the_parent(self):
        races, runs = self.races.copy(), self.runs.copy()
        first = races.index[:2]
        races.loc[first, "course_kubun"] = "B"                           # 2レースだけのコース条件
        engine_few = CourseBiasEngine(races, runs, self.cfg)
        pos = int(races.index[(races["date"] > races.loc[first, "date"].max())][0])
        thin = engine_few.get(pos)
        wide = CourseBiasEngine(self.races, self.runs, self.cfg).get(pos)
        self.assertLess(np.abs(thin.style_win - wide.style_win).max(), 0.5)

    def test_sample_counts_are_kept(self):
        bias = self._bias(self.runs)
        self.assertGreater(bias.style_n.sum(), 0)
        self.assertGreater(bias.draw_n.sum(), 0)


class BiasFeatureTest(unittest.TestCase):
    def test_supported_levels_exclude_full_and_bias_levels_use_new_columns(self):
        self.assertNotIn("full", PERF_LEVELS)
        self.assertEqual(len(level_indices("formation_bias")), 11)
        self.assertEqual(len(level_indices("pace_bias")), 16)
        self.assertEqual(PERF_LEVELS["formation_bias"][:3], ["ability_c", "q_c", "slot_c"])

    def test_features_are_centered_within_race_and_zero_without_bias(self):
        ctx = make_ctx(n=12, seed=3)
        rng = np.random.default_rng(0)
        q = rng.random((50, 12))
        pace = rng.normal(0, 0.6, 50)
        slot = np.zeros((50, 12))
        plain = perf_features(ctx, q, slot, pace)
        for name in PERF_FEATURES[5:]:
            self.assertTrue((plain[:, :, PERF_FEATURES.index(name)] == 0).all())
        ctx.bias = make_bias()
        f = perf_features(ctx, q, slot, pace)
        for name in PERF_FEATURES[5:]:
            if name in GOING_ABILITY_FEATURES:
                continue
            col = f[:, :, PERF_FEATURES.index(name)]
            np.testing.assert_allclose(col.mean(axis=1), 0.0, atol=1e-12)
            self.assertGreater(col.std(), 0.0, name)
        np.testing.assert_array_equal(f[:, :, :5], plain[:, :, :5])  # 既存特徴量は変わらない

    def test_style_feature_follows_the_sampled_early_position_and_pace_follows_the_sampled_pace(self):
        ctx = make_ctx(n=8, seed=2)
        bias = make_bias(seed=5)
        q = np.tile(np.linspace(0.0, 1.0, 8), (2, 1))
        fast = bias_feature_block(bias, ctx.wakuban, q, np.array([-1.0, 1.0]))
        sid = style_ids(q, bias.front_q, bias.stalk_q)
        np.testing.assert_allclose(fast["style_win_bias_c"], bias.style_win[sid])
        np.testing.assert_allclose(fast["pace_style_win_bias_c"][0], bias.pstyle_win[0, sid[0]])  # 速いペース=区分0
        np.testing.assert_allclose(fast["pace_style_win_bias_c"][1], bias.pstyle_win[2, sid[1]])  # 遅いペース=区分2

    def test_draw_features_do_not_depend_on_the_simulated_formation(self):
        ctx = make_ctx(n=8, seed=2)
        bias = make_bias(seed=5)
        a = bias_feature_block(bias, ctx.wakuban, np.random.default_rng(1).random((3, 8)), np.zeros(3))
        b = bias_feature_block(bias, ctx.wakuban, np.random.default_rng(2).random((3, 8)), np.zeros(3))
        np.testing.assert_array_equal(a["draw_win_bias_c"], b["draw_win_bias_c"])


class BiasSimulationTest(unittest.TestCase):
    def setUp(self):
        self.cfg = RaceverseConfig()
        self.bundle = make_bundle()
        self.snap = make_snapshot(n_horses=12)

    def _run(self, level, ctx, seed=7):
        return simulate_race(ctx, self.bundle, self.snap, self.cfg, n_sims=1500, perf_level=level, seed=seed, keep_samples=True)

    def test_invariants_and_same_random_stream_for_bias_levels(self):
        ctx = make_ctx(n=12, seed=4)
        ctx.bias = make_bias()
        for level in ("formation_bias", "pace_bias"):
            r = self._run(level, ctx)
            self.assertTrue(all(check_invariants(r).values()), level)
            self.assertIn("mean_rel_time_sec", r.horses)
        a, b = self._run("formation", ctx), self._run("formation_bias", ctx)
        np.testing.assert_array_equal(a.samples["q_adj"], b.samples["q_adj"])      # 同じ隊列抽選
        np.testing.assert_array_equal(a.samples["pace_delta"], b.samples["pace_delta"])

    def test_bias_coefficients_change_win_probability_through_the_performance_model_only(self):
        ctx = make_ctx(n=12, seed=4)
        ctx.bias = make_bias(seed=9)
        ctx.bias.style_win = np.array([2.0, 0.5, -0.5, -2.0])  # 逃げ・先行が非常に有利なコース
        model = self.bundle.perf_models["formation_bias"]
        base_coef = model.coef.copy()
        with_bias = base_coef.copy()
        with_bias[3] = -0.8  # style_win_bias_c の係数: 大きいほど走破時計が速い
        before = self._run("formation_bias", ctx).horses["win_probability"].to_numpy()
        model.coef = with_bias
        try:
            after = self._run("formation_bias", ctx)
        finally:
            model.coef = base_coef
        self.assertAlmostEqual(after.horses["win_probability"].sum(), 1.0)
        front_mean_q = after.samples["q_adj"].mean(axis=0)
        front = np.argsort(front_mean_q)[:3]
        rear = np.argsort(front_mean_q)[-3:]
        self.assertGreater(after.horses["win_probability"].to_numpy()[front].sum() - before[front].sum(),
                           after.horses["win_probability"].to_numpy()[rear].sum() - before[rear].sum())

    def test_pace_fallback_keeps_bias_level_when_reference_is_missing(self):
        ctx = make_ctx(n=8, seed=6)
        ctx.bias = make_bias()
        ctx.early_ref = float("nan")
        r = self._run("pace_bias", ctx)
        self.assertEqual(r.perf_level, "formation_bias")


if __name__ == "__main__":
    unittest.main()

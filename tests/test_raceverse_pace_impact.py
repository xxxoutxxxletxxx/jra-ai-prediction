import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd

from raceverse.config import PaceImpactConfig
from raceverse.formation_sampler import arrange_formation
from raceverse.pace_correlation import correlation_table
from raceverse.pace_features import FEATURE_INDEX, FEATURE_NAMES, pace_features
from raceverse.pace_impact import PaceImpactProfiles, RoleEvents, backfit_impacts, build_events, formation_from_actual_q
from raceverse.pace_regression import fit_pace_regressor
from raceverse.schemas import Formation
from raceverse_fixtures import make_ctx, make_snapshot


def _events(horse, jockey, eps, month=None):
    horse = np.asarray(horse, dtype=int)
    month = np.zeros(len(horse), dtype=int) if month is None else np.asarray(month, dtype=int)
    return RoleEvents(month, horse, np.asarray(jockey, dtype=int), np.asarray(eps, dtype=float))


class ShrinkageTest(unittest.TestCase):
    def test_impact_equals_n_over_n_plus_lambda_times_mean_residual(self):
        ev = _events([0, 0, 0, 0, 1], [-1] * 5, [-1.0, -1.0, -1.0, -1.0, -1.0])
        a, _, cnt, _ = backfit_impacts(ev, 2, 1, lam_horse=6.0, lam_jockey=10.0, iters=3)
        self.assertAlmostEqual(a[0], 4 / (4 + 6) * -1.0)
        self.assertAlmostEqual(a[1], 1 / (1 + 6) * -1.0)
        self.assertEqual(cnt.tolist(), [4.0, 1.0])

    def test_few_samples_do_not_produce_extreme_values(self):
        thin = _events([0], [-1], [3.0])
        thick = _events([0] * 60, [-1] * 60, [3.0] * 60)
        a_thin = backfit_impacts(thin, 1, 1, 8.0, 10.0, 2)[0][0]
        a_thick = backfit_impacts(thick, 1, 1, 8.0, 10.0, 2)[0][0]
        self.assertLess(a_thin, 0.5)
        self.assertGreater(a_thick, 2.5)

    def test_unseen_horse_has_zero_impact(self):
        a, _, _, _ = backfit_impacts(_events([0], [-1], [1.0]), 3, 1, 8.0, 10.0, 2)
        self.assertEqual(a[2], 0.0)


class HorseJockeySeparationTest(unittest.TestCase):
    def test_jockey_effect_is_not_double_counted_on_the_horse(self):
        rng = np.random.default_rng(0)
        horse, jockey, eps = [], [], []
        for h in range(4):
            for j in range(2):
                for _ in range(40):
                    horse.append(h)
                    jockey.append(j)
                    eps.append((-0.4 if j == 0 else 0.0) + rng.normal(0, 0.3))
        for _ in range(60):  # 常にj=0が騎乗する馬(馬と騎手が交絡)
            horse.append(4)
            jockey.append(0)
            eps.append(-0.4 + rng.normal(0, 0.3))
        ev = _events(horse, jockey, eps)
        a_sep, b_sep, _, _ = backfit_impacts(ev, 5, 2, 8.0, 1.0, 40, separate_jockey=True)
        a_naive, _, _, _ = backfit_impacts(ev, 5, 2, 8.0, 1.0, 40, separate_jockey=False)
        self.assertLess(b_sep[0], -0.25)                       # 騎手の効果は騎手に帰属
        self.assertLess(abs(a_sep[:4]).max(), 0.5 * abs(a_naive[:4]).min())  # 複数騎手で走った馬には残りにくい
        self.assertLess(abs(a_sep[4]), abs(a_naive[4]))        # 交絡した馬の値は単純集計より小さい


class AsOfAndRoleTest(unittest.TestCase):
    def _profiles(self, eps_future):
        lead = _events([0, 0, 0, 0], [0, 0, 0, 0], [-0.5, -0.5, eps_future, eps_future], month=[0, 1, 2, 3])
        roles = {"lead": lead, "chase": _events([], [], []), "front": _events([], [], [])}
        presence = _events([], [], [])
        return PaceImpactProfiles(PaceImpactConfig(), 1, 1, roles, presence, np.array([0, 1, 2, 3]), np.zeros(4, dtype=int),
                                  np.ones(4, dtype=bool), pd.DataFrame())

    def test_snapshot_ignores_same_month_and_future_events(self):
        a, b = self._profiles(5.0), self._profiles(-5.0)  # 月2以降の実績を正反対に書き換える
        for month in (0, 1, 2):
            sa, sb = a.snapshot(month), b.snapshot(month)
            np.testing.assert_array_equal(sa["h_lead"], sb["h_lead"])
        self.assertEqual(a.snapshot(0)["h_lead"][0], 0.0)      # 月0は自分の月を見ない
        self.assertLess(a.snapshot(1)["h_lead"][0], 0.0)       # 月1は月0の速い実績を見る
        self.assertEqual(a.snapshot(2)["h_n_lead"][0], 2.0)    # 逃げ経験数も月2より前の2走だけ

    def test_roles_follow_actual_early_rank_with_field_size_scaling(self):
        n = 16
        runs = pd.DataFrame({
            "race_id": ["r"] * n + ["bad"] * 4, "date": pd.Timestamp("2024-02-10"),
            "horse_idx": list(range(n)) + [20, 21, 22, 23], "jockey_idx": [0] * (n + 4),
            "early_rank": list(range(1, n + 1)) + [0, 0, 0, 0], "field_size": [n] * n + [4] * 4,
        })
        eps = pd.DataFrame({"race_id": ["r", "bad"], "eps": [-0.5, np.nan]})
        ds = SimpleNamespace(runs=runs, base_month=pd.Timestamp("2024-01-01"))
        roles, presence = build_events(ds, eps, PaceImpactConfig())
        self.assertEqual(roles["lead"].horse.tolist(), [0])
        self.assertEqual(sorted(roles["chase"].horse.tolist()), [1, 2])
        self.assertEqual(sorted(roles["front"].horse.tolist()), [0, 1, 2, 3])  # 16頭の25%=4頭
        self.assertEqual(len(presence.horse), 12)                                # 先行集団以外は出走のみ評価
        self.assertTrue(all(len(e.eps) == len(set(e.horse)) for e in roles.values()))  # 残差NaNのレースは除外


class CorrelationTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        n_races = 600
        dates = pd.Timestamp("2022-01-01") + pd.to_timedelta(np.arange(n_races) * 1.2, unit="D")
        lead_races = set(rng.choice(np.arange(20, 560), 25, replace=False))
        thin_races = {100, 200, 300}
        eps = rng.normal(0, 0.5, n_races)
        for r in lead_races:
            eps[r] -= 0.8
        self.race_eps = pd.DataFrame({"race_id": [f"r{i}" for i in range(n_races)], "date": dates,
                                      "group": "turf_mile", "eps": eps})
        rows = []
        for i in range(n_races):
            rows.append((f"r{i}", dates[i], 99, 9, 8, 16))                      # 他の馬(母集団を作るだけ)
        for r in sorted(lead_races):
            rows.append((f"r{r}", dates[r], 0, 0, 1, 16))                        # 馬0: 逃げ
        for r in (5, 30, 590, 400, 410, 420, 430, 440, 450, 460, 470, 480):
            rows.append((f"r{r}", dates[r], 0, 0, 9, 16))                        # 馬0: 後方で出走(フラグ0)
        for r in thin_races:
            rows.append((f"r{r}", dates[r], 1, 1, 1, 16))                        # 馬1: 逃げ3回だけ
        rows.append(("r10", dates[10], 1, 1, 9, 16))
        self.runs = pd.DataFrame(rows, columns=["race_id", "date", "horse_idx", "jockey_idx", "early_rank", "field_size"])
        self.table = correlation_table(self.runs, self.race_eps, pd.Timestamp("2025-01-01"), "horse_idx", PaceImpactConfig())

    def _row(self, horse, flag):
        return self.table[(self.table["horse_idx"] == horse) & (self.table["flag"] == flag)].iloc[0]

    def test_speeding_horse_has_negative_significant_correlation(self):
        row = self._row(0, "lead")
        self.assertEqual(row["status"], "estimated")
        self.assertLess(row["pace_corr"], -0.1)
        self.assertLess(row["t_stat"], -3)

    def test_population_contains_unflagged_races(self):
        row = self._row(0, "lead")
        self.assertGreater(row["n_population"], 10 * row["n_events"])   # 常に存在フラグ1にならない
        presence = self._row(0, "presence")
        self.assertGreater(presence["n_population"], presence["n_events"])

    def test_small_samples_are_not_given_a_correlation(self):
        row = self._row(1, "lead")
        self.assertEqual(row["status"], "insufficient_sample")
        self.assertTrue(np.isnan(row["pace_corr"]))

    def test_future_races_are_not_used(self):
        early = correlation_table(self.runs, self.race_eps, pd.Timestamp("2022-03-01"), "horse_idx", PaceImpactConfig())
        self.assertLessEqual(early["n_population"].max(), 50)


def _random_formation(q: np.ndarray, threshold: float = 0.08) -> Formation:
    group, slot, early_order, order_q = arrange_formation(q, threshold)
    return Formation(q, q, np.zeros_like(q, dtype=bool), group, slot, early_order, order_q,
                     np.zeros(q.shape[1], dtype=bool), 0)


class PaceSensitivityTest(unittest.TestCase):
    """特定の馬・騎手の位置取りを変えたとき、全頭隊列から予測ペースがどう変わるか。"""

    @classmethod
    def setUpClass(cls):
        n, cls.n = 14, 14
        cls.ctx = make_ctx(n=n, seed=11)
        cls.ctx.jockey_idx = np.arange(n) % 5
        cls.ctx.jockey_idx[5] = 5          # 馬5の騎手は他の馬と共有しない
        cls.snap = make_snapshot(n_horses=n, n_jockeys=6, seed=2)
        for role in ("lead", "chase", "front"):
            cls.snap[f"h_{role}"][:] = 0.0
            cls.snap[f"j_{role}"][:] = 0.0
        cls.snap["h_lead"][3] = -0.6        # 馬3: 逃げると速い
        cls.snap["h_front"][3] = -0.5
        cls.snap["h_front"][6] = -0.5       # 馬6: 先行集団にいるだけでペースを引き上げる
        cls.snap["j_lead"][cls.ctx.jockey_idx[5]] = -0.4   # 馬5の騎手: 逃げると速い
        rng = np.random.default_rng(0)
        q = rng.random((8000, n))
        x = pace_features(cls.ctx, _random_formation(q), cls.snap)
        idx = FEATURE_INDEX
        truth = (x[:, idx["leader_horse_lead_impact"]] + x[:, idx["leader_jockey_lead_impact"]]
                 + 0.6 * x[:, idx["front_impact_neg_sum"]])
        cls.model = fit_pace_regressor(x, truth + rng.normal(0, 0.1, len(truth)), np.ones(len(truth)), 1.0)

    def _predict(self, q_row: np.ndarray) -> float:
        x = pace_features(self.ctx, _random_formation(q_row[None, :]), self.snap)
        return float(self.model.predict(x)[0])

    def _base_q(self) -> np.ndarray:
        q = np.linspace(0.3, 0.95, self.n)
        q[3], q[6] = 0.93, 0.96  # 影響の大きい馬は基準では後方に置く
        return q

    def test_known_fast_horse_leading_makes_predicted_pace_faster(self):
        led, hidden = self._base_q(), self._base_q()
        led[3], hidden[3] = 0.0, 0.97
        self.assertLess(self._predict(led), self._predict(hidden) - 0.3)

    def test_known_fast_jockey_leading_makes_predicted_pace_faster(self):
        led, hidden = self._base_q(), self._base_q()
        led[5], hidden[5] = 0.0, 0.97
        self.assertLess(self._predict(led), self._predict(hidden) - 0.2)

    def test_pace_raising_horse_far_behind_does_not_change_prediction(self):
        a, b = self._base_q(), self._base_q()
        a[3], b[3] = 0.9, 1.0
        self.assertLess(abs(self._predict(a) - self._predict(b)), 0.1)

    def test_second_pace_raising_horse_in_front_group_is_not_diluted_by_averaging(self):
        one, two = self._base_q(), self._base_q()
        one[3], one[6] = 0.0, 0.97
        two[3], two[6] = 0.0, 0.02
        self.assertLess(self._predict(two), self._predict(one) - 0.2)

    def test_same_formation_gives_same_prediction(self):
        q = self._base_q()
        q[3] = 0.0
        self.assertEqual(self._predict(q), self._predict(q))


class ImpactFeatureShapeTest(unittest.TestCase):
    def test_features_are_finite_and_normalized_by_field_size(self):
        for n in (6, 12, 18):
            ctx = make_ctx(n=n, seed=n)
            snap = make_snapshot(n_horses=n)
            q = np.random.default_rng(n).random((50, n))
            x = pace_features(ctx, _random_formation(q), snap)
            self.assertEqual(x.shape, (50, len(FEATURE_NAMES)))
            self.assertTrue(np.isfinite(x).all())
            for name in ("front_group_ratio", "second_group_ratio", "n_groups_ratio", "lead_candidates_ratio",
                         "n_q_le25_ratio", "n_q_le50_ratio", "outside_front_ratio", "fast_pressure_outside_share"):
                column = x[:, FEATURE_INDEX[name]]
                self.assertTrue((column >= 0).all() and (column <= 1).all(), name)
            self.assertTrue((np.diff(x[:, [FEATURE_INDEX[f"q_p{p}"] for p in (10, 25, 50, 75)]], axis=1) >= -1e-12).all())

    def test_impact_features_vanish_without_snapshot_impacts(self):
        ctx = make_ctx(n=10, seed=1)
        ctx.horse_idx = None
        q = np.random.default_rng(1).random((20, 10))
        x = pace_features(ctx, _random_formation(q), make_snapshot(with_impacts=False))
        for name in ("leader_horse_lead_impact", "front_impact_min", "inout_pressure_diff", "field_presence_impact_sum"):
            self.assertTrue((x[:, FEATURE_INDEX[name]] == 0).all(), name)

    def test_actual_formation_helper_matches_manual_ranking(self):
        form = formation_from_actual_q(np.array([0.5, 0.0, 1.0, 0.25]), 0.08)
        self.assertEqual(form.q_rank_order[0].tolist(), [1, 3, 0, 2])


if __name__ == "__main__":
    unittest.main()

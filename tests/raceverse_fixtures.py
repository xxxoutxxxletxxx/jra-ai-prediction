"""テスト専用の合成データ。実データ・実モデルの結果とは無関係(RACEVERSEの出力に混ぜない)。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from raceverse.pace_display import fit_display_thresholds
from raceverse.pace_features import FEATURE_NAMES
from raceverse.pace_regression import fit_pace_regressor
from raceverse.pace_residuals import PaceBounds, PaceResidualSampler
from raceverse.performance import PerfModel
from raceverse.schemas import RaceBias, RaceContext, TrackContext
from raceverse.training import ModelBundle
from raceverse.winning_time_model import TIME_FEATURES, TIME_LEVELS, TimeModel

K = 10


def make_ctx(n: int = 10, seed: int = 0, with_track: bool = True, cold_idx=()) -> RaceContext:
    rng = np.random.default_rng(seed)
    hist_q = rng.random((n, K)).astype(np.float32)
    hist_j = rng.integers(0, 5, size=(n, K)).astype(np.int32)
    for i in cold_idx:
        hist_q[i, :] = np.nan
    track = TrackContext(0.2, 5.0, "previous_day", {"previous_day": 3, "previous_week": 0, "previous_meet": 0,
                                                    "previous_year_same_season": 2}, ["a", "b"], "2025-01-01", False) if with_track else None
    return RaceContext(
        race_id=f"TEST-{seed}", date=pd.Timestamp("2025-06-01"), track="05", surface="turf", distance_m=1600,
        layout="17A", going=1, class_group="C2", age_class="3up", meet_id="2025-05-02", meet_day=3, course_week=2,
        month=6, first_turn_distance_m=400.0, first_turn_missing=False, early_ref=35.0, early_section_m=600.0,
        win_time_base=96.0, month_idx=0, horse_ids=[f"H{i}" for i in range(n)], umaban=np.arange(1, n + 1),
        jockey_idx=rng.integers(0, 5, size=n).astype(np.int32), hist_q=hist_q, hist_j=hist_j,
        closing_skill=rng.normal(0, 0.5, n).astype(np.float32), rest_days=rng.integers(7, 120, n).astype(np.float32),
        age=rng.integers(3, 7, n).astype(float), weight_carried=rng.normal(56, 1.5, n), ability=rng.normal(0, 1, n),
        odds=rng.uniform(2, 50, n), track_context=track, horse_idx=np.arange(n),
        wakuban=np.clip(np.ceil(np.arange(1, n + 1) * 8.0 / n).astype(int), 1, 8),
    )


def make_bias(seed: int = 0, front_q: float = 0.30, stalk_q: float = 0.70) -> RaceBias:
    rng = np.random.default_rng(seed)
    return RaceBias(
        style_win=rng.normal(0, 0.3, 4), style_place=rng.normal(0, 0.2, 4), style_n=np.full(4, 200.0),
        style_n_meet=np.full(4, 10.0), draw_win=rng.normal(0, 0.15, 8), draw_place=rng.normal(0, 0.1, 8),
        draw_n=np.full(8, 300.0), draw_n_meet=np.full(8, 12.0), inter=rng.normal(0, 0.1, (4, 3)),
        pstyle_win=rng.normal(0, 0.2, (3, 4)), pstyle_place=rng.normal(0, 0.1, (3, 4)), pdraw=rng.normal(0, 0.05, (3, 3)),
        front_q=front_q, stalk_q=stalk_q, pace_edges=np.array([-0.35, 0.35]),
    )


def make_bundle(seed: int = 0) -> ModelBundle:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(600, len(FEATURE_NAMES)))
    y = 0.1 * x[:, 0] + rng.normal(0, 0.7, 600)
    pace_model = fit_pace_regressor(x, y, np.ones(600), 1.0)
    groups = np.array(["turf_mile"] * 600)
    bounds = PaceBounds.fit(groups, y, [0.001, 0.999], 100)
    thresholds = fit_display_thresholds(groups, y, [0.1, 0.3, 0.7, 0.9])
    xt = rng.normal(size=(400, len(TIME_FEATURES)))
    yt = 0.3 * xt[:, 0] + rng.normal(0, 0.8, 400)
    time_models = {lv: TimeModel(lv, 10.0).fit(xt, yt) for lv in TIME_LEVELS}
    time_sampler = PaceResidualSampler.fit(np.array(["turf_mile"] * 400), rng.normal(0, 0.8, 400), np.full(400, 0.01),
                                           yt, [0.002, 0.998], 100)
    perf = {}
    n_cols = {"base": 1, "formation": 3, "pace": 5, "full": 9, "formation_bias": 8, "pace_bias": 13}
    for lv, c in n_cols.items():
        coef = np.zeros(c)
        coef[0] = -0.45
        perf[lv] = PerfModel(lv, coef, 0.0, 0.5, 0.2, rng.normal(size=2000), 0.0 if lv == "base" else 0.3, 0.1,
                             np.array([-3.0, 6.0]), 1000)
    return ModelBundle(pd.Timestamp("2025-06-01"), pace_model, bounds, thresholds, time_models, time_sampler, perf, {})


def make_profiles_arrays(n_jockeys: int = 5):
    frontness = np.append(np.linspace(0.2, 0.8, n_jockeys), 0.5)
    tempo = np.append(np.linspace(-0.2, 0.2, n_jockeys), 0.0)
    return frontness, tempo


def make_snapshot(n_horses: int = 12, n_jockeys: int = 5, seed: int = 0, with_impacts: bool = True):
    """Dataset.snapshot と同じキーの辞書(末尾=未知の馬・騎手)。"""
    frontness, tempo = make_profiles_arrays(n_jockeys)
    snap = {"frontness": frontness, "lead_tempo": tempo}
    if with_impacts:
        rng = np.random.default_rng(seed)
        for role in ("lead", "chase", "front"):
            snap[f"h_{role}"] = np.append(rng.normal(0, 0.2, n_horses), 0.0)
            snap[f"j_{role}"] = np.append(rng.normal(0, 0.1, n_jockeys), 0.0)
        snap["h_presence"] = np.append(rng.normal(0, 0.05, n_horses), 0.0)
        snap["h_n_runs"] = np.append(rng.integers(3, 30, n_horses).astype(float), 0.0)
        snap["h_n_lead"] = np.append(rng.integers(0, 5, n_horses).astype(float), 0.0)
    return snap

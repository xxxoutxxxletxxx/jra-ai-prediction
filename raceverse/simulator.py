"""10,000回レースシミュレーター(仕様9章)。

1試行の順序:
  近走抽選 → 騎手変更補正 → 序盤隊列 → 全頭隊列・Pace Impactからペース回帰(乱択なし) → 決着時計 → 各馬の相対走破性能 → 着順・着差・各馬時計
全馬が同じ試行のペース・共通ショックを共有し、勝者は1頭だけ。時計は T_i = T_win + margin_i (勝者のmargin=0)。
ペースは確定した隊列から回帰で決まる値で、同じ隊列・騎手・開催条件なら同じ値になる。分布は隊列の抽選だけから生まれる。
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from raceverse.config import PACE_BUCKETS, RaceverseConfig
from raceverse.formation_sampler import sample_formation
from raceverse.pace_display import pace_display_bucket_index, thresholds_for
from raceverse.pace_features import FEATURE_INDEX, pace_features
from raceverse.pace_residuals import group_key
from raceverse.performance import PACELESS_FALLBACK, PERF_FEATURES, PERF_LEVELS, perf_features
from raceverse.schemas import RaceContext
from raceverse.training import ModelBundle
from raceverse.winning_time_model import FORMATION_COLUMNS, time_features


def race_rng(seed: int, race_id: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(race_id.encode("utf-8"))])


@dataclass
class SimulationResult:
    race_id: str
    n_sims: int
    seed: int
    perf_level: str
    horses: pd.DataFrame
    race: Dict[str, object]
    warnings: List[str] = field(default_factory=list)
    samples: Optional[Dict[str, np.ndarray]] = None


def simulate_race(
    ctx: RaceContext,
    bundle: ModelBundle,
    snap: Dict[str, np.ndarray],
    cfg: RaceverseConfig,
    n_sims: Optional[int] = None,
    perf_level: str = "formation",
    seed: Optional[int] = None,
    first_turn_default: float = 400.0,
    keep_samples: bool = False,
) -> SimulationResult:
    if perf_level not in PERF_LEVELS:
        raise ValueError(f"unsupported RACEVERSE performance level: {perf_level}")
    s = int(n_sims or cfg.n_simulations)
    seed = cfg.random_seed if seed is None else seed
    rng = race_rng(seed, ctx.race_id)
    n = ctx.n
    warnings = list(ctx.warnings)
    key = group_key(ctx.surface, ctx.distance_m)

    # 1-3. 隊列
    form = sample_formation(ctx, rng, s, cfg.formation, snap["frontness"])
    if form.unknown_jockey_runs:
        warnings.append(f"sampled past-run jockey unknown in {form.unknown_jockey_runs} draws (no jockey-change adjustment)")

    # 4. 連続値ペース: 確定した全頭隊列と馬・騎手のPace Impactから回帰で決める(乱択なし)
    pace_ok = bool(np.isfinite(ctx.early_ref))
    x_pace = pace_features(ctx, form, snap, first_turn_default)
    if pace_ok:
        mu_delta = bundle.pace_model.predict(x_pace)
        pace_delta = bundle.pace_bounds.clip(key, mu_delta)
        early_split = ctx.early_ref + pace_delta
        thresholds = thresholds_for(bundle.display_thresholds, ctx.surface, ctx.distance_m)
        bucket = pace_display_bucket_index(pace_delta, thresholds)
    else:
        warnings.append("pace reference unavailable (no lap baseline); pace-dependent terms disabled")
        mu_delta = np.zeros(s)
        pace_delta = np.zeros(s)
        early_split = np.full(s, np.nan)
        bucket = np.full(s, 2, dtype=int)
        perf_level = PACELESS_FALLBACK.get(perf_level, perf_level)

    # 5. 決着時計
    win_time = None
    time_status = "unavailable"
    track = ctx.track_context
    if (bundle.time_models and bundle.time_sampler is not None and track is not None
            and np.isfinite(ctx.win_time_base) and pace_ok):
        form_x = x_pace[:, [FEATURE_INDEX[c] for c in FORMATION_COLUMNS]]
        xt = time_features(ctx, track, pace_delta, form_x)
        mean_y = bundle.time_models["full"].predict(xt)
        y_sim = bundle.time_sampler.draw(rng, key, mean_y)
        win_time = ctx.win_time_base + y_sim
        time_status = "estimated"
    else:
        warnings.append("winning_time_status=unavailable")

    # 6. 走破性能・着順・着差
    if perf_level not in bundle.perf_models:
        raise ValueError(f"performance model '{perf_level}' is not available in the bundle")
    pm = bundle.perf_models[perf_level]
    feats = perf_features(ctx, form.q_adj, form.lateral_slot, pace_delta)
    mu = pm.mean_dev(feats)
    q_c = feats[:, :, PERF_FEATURES.index("q_c")]
    slot_c = feats[:, :, PERF_FEATURES.index("slot_c")]
    shared = rng.normal(0.0, pm.tau_q, size=(s, 1)) * q_c + rng.normal(0.0, pm.tau_slot, size=(s, 1)) * slot_c
    dev = mu + shared + pm.draw_noise(rng, mu)
    order = np.argsort(dev, axis=1, kind="stable")
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.broadcast_to(np.arange(n), (s, n)), axis=1)  # 0=1着
    margin = dev - dev.min(axis=1, keepdims=True)
    horse_time = win_time[:, None] + margin if win_time is not None else None

    result = _summarize(ctx, form, ranks, horse_time, win_time, pace_delta, mu_delta, early_split, bucket,
                        s, seed, perf_level, time_status, warnings, bundle)
    rel_dev = dev - dev.mean(axis=1, keepdims=True)  # 出走馬平均基準の相対走破時計(秒, 正=遅い)
    result.horses["mean_rel_time_sec"] = rel_dev.mean(axis=0)
    result.horses["wakuban"] = ctx.wakuban if ctx.wakuban is not None else np.nan
    if ctx.bias is not None:
        result.race["course_bias_sample_counts"] = {
            "style_runs_at_course": ctx.bias.style_n.astype(int).tolist(),
            "style_runs_in_meet": ctx.bias.style_n_meet.astype(int).tolist(),
            "draw_runs_at_course": ctx.bias.draw_n.astype(int).tolist(),
            "draw_runs_in_meet": ctx.bias.draw_n_meet.astype(int).tolist(),
        }
    if keep_samples:
        result.samples = {"ranks": ranks, "margin": margin, "horse_time": horse_time, "win_time": win_time,
                          "pace_delta": pace_delta, "mu_delta": mu_delta, "bucket": bucket, "q_adj": form.q_adj,
                          "early_split": early_split}
    return result


def _summarize(ctx, form, ranks, horse_time, win_time, pace_delta, mu_delta, early_split, bucket,
               s, seed, perf_level, time_status, warnings, bundle) -> SimulationResult:
    n = ctx.n
    win = ranks == 0
    finish_dist = np.stack([(ranks == k).mean(axis=0) for k in range(n)], axis=1)  # [N, N]
    horses = pd.DataFrame({
        "race_id": ctx.race_id, "horse_id": ctx.horse_ids, "umaban": ctx.umaban,
        "ability_score": ctx.ability, "win_probability": win.mean(axis=0),
        "top2_probability": (ranks <= 1).mean(axis=0), "top3_probability": (ranks <= 2).mean(axis=0),
        "mean_finish_position": (ranks + 1).mean(axis=0),
        "mean_early_position": form.q_adj.mean(axis=0), "mean_lateral_slot": form.lateral_slot.mean(axis=0),
        "lead_probability": np.bincount(form.q_rank_order[:, 0], minlength=n) / s,
        "cold_start": form.cold_start,
        "jockey_change_adjusted_fraction": form.adjusted.mean(axis=0),
        "jockey_change_mean_shift": (form.q_adj - form.q_sampled).mean(axis=0),
        "win_odds_reference": ctx.odds,
    })
    horses["finish_position_distribution"] = [finish_dist[i].round(6).tolist() for i in range(n)]
    counts = np.array([(bucket == b).sum() for b in range(5)])
    for b, name in enumerate(PACE_BUCKETS):
        horses[f"win_prob_{name}"] = win[bucket == b].mean(axis=0) if counts[b] > 0 else np.full(n, np.nan)
    horses["pace_condition_sample_count"] = [{PACE_BUCKETS[b]: int(counts[b]) for b in range(5)}] * n
    if horse_time is not None:
        horses["mean_horse_time_sec"] = horse_time.mean(axis=0)
        horses["horse_time_p10_sec"] = np.percentile(horse_time, 10, axis=0)
        horses["horse_time_p90_sec"] = np.percentile(horse_time, 90, axis=0)

    track = ctx.track_context
    has_split = bool(np.isfinite(early_split).any())
    race: Dict[str, object] = {
        "engine": "RACEVERSE", "version": "0.6", "race_id": ctx.race_id, "simulations": s, "seed": seed,
        "perf_level": perf_level, "going": int(ctx.going), "model_as_of": str(bundle.as_of.date()),
        "data_cutoff": track.reference_cutoff if track else str((ctx.date - pd.Timedelta(days=1)).date()),
        "reference_early_split_sec": None if not np.isfinite(ctx.early_ref) else ctx.early_ref,
        "early_section_m": None if not np.isfinite(ctx.early_section_m) else ctx.early_section_m,
        "pace_delta_mean_sec": float(pace_delta.mean()), "pace_delta_regression_mean_sec": float(mu_delta.mean()),
        "pace_delta_p10_p90_sec": [float(np.percentile(pace_delta, 10)), float(np.percentile(pace_delta, 90))],
        "predicted_early_split_mean_sec": float(early_split.mean()) if has_split else None,
        "predicted_early_split_p10_p90_sec": ([float(np.percentile(early_split, 10)), float(np.percentile(early_split, 90))]
                                              if has_split else None),
        "pace_display_probabilities": {PACE_BUCKETS[b]: float(counts[b] / s) for b in range(5)},
        "winning_time_status": time_status,
        "formation_summary": {
            "mean_front_group_size": float((form.group == 0).sum(axis=1).mean()),
            "top_lead_candidates": [ctx.horse_ids[i] for i in np.argsort(-horses["lead_probability"].to_numpy())[:3]],
        },
        "warnings": warnings,
    }
    if win_time is not None:
        race["expected_winning_time_sec"] = float(win_time.mean())
        race["winning_time_p10_p90_sec"] = [float(np.percentile(win_time, 10)), float(np.percentile(win_time, 90))]
    if track is not None:
        race["track_speed_adjustment_sec"] = track.track_bias_sec
        race["track_reference_sources"] = {
            "counts": track.source_counts, "effective_sample_size": track.effective_sample_size,
            "fallback_level": track.fallback_level, "going_changed": track.going_changed,
            "reference_race_ids": track.reference_race_ids,
        }
    return SimulationResult(ctx.race_id, s, seed, perf_level, horses, race, warnings)


def check_invariants(result: SimulationResult, atol: float = 1e-9) -> Dict[str, bool]:
    """仕様15章の整合条件(勝者1頭・確率合計1・時計順=着順)。keep_samples=True の結果で検証する。"""
    out = {
        "win_prob_sum_is_1": bool(abs(result.horses["win_probability"].sum() - 1.0) < 1e-9),
        "pace_prob_sum_is_1": bool(abs(sum(result.race["pace_display_probabilities"].values()) - 1.0) < 1e-9),
    }
    sm = result.samples
    if sm is not None:
        ranks, margin = sm["ranks"], sm["margin"]
        out["one_winner_per_sim"] = bool(((ranks == 0).sum(axis=1) == 1).all())
        out["ranks_are_permutations"] = bool((np.sort(ranks, axis=1) == np.arange(ranks.shape[1])).all())
        out["winner_margin_zero_others_nonneg"] = bool(
            (margin >= -atol).all() and np.allclose(np.where(ranks == 0, margin, 0), 0))
        if sm["horse_time"] is not None:
            t = sm["horse_time"]
            out["time_order_matches_rank"] = bool((np.argsort(t, axis=1, kind="stable") == np.argsort(ranks, axis=1)).all())
    return out

"""独立Walk-Forwardバックテスト(仕様11章)。既存Rankerのコード・出力は変更せず、同一レース・同一馬・同一評価期間で比較する。

月ごとに「その月より前のデータだけ」でモデル一式を再学習し、その月の各レースを 1万回シミュレーションする。
予測を書き出した後に初めて実際の結果と照合する。確率の温度校正(p^gamma)の gamma は、直前 window_months の
バックテスト予測(=すべて過去)だけから決める。評価期間の前に burn_in_months 分の助走期間を回して校正の初期値を作る。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from raceverse import bias_eval
from raceverse import evaluation as ev
from raceverse.config import PACE_BUCKETS, REPORT_DIR
from raceverse.pace_display import pace_display_bucket_index, thresholds_for
from raceverse.pipeline import Prepared
from raceverse.simulator import simulate_race
from raceverse.winning_time_model import time_features

LOGGER = logging.getLogger(__name__)
LEVELS = ["base", "formation", "pace", "full"]
BIAS_LEVELS = ["formation_bias", "pace_bias"]
ALL_LEVELS = LEVELS + BIAS_LEVELS
BIAS_PAIRS = [("formation", "formation_bias"), ("pace", "pace_bias")]
EXISTING_WF_CSV = Path(__file__).resolve().parents[1] / "reports" / "ranker_walk_forward_86_features" / "walk_forward_predictions.csv"


def reference_level(levels: List[str]) -> str:
    """レース単位のペース・時計評価に使うレベル(時計・ペースはどのレベルでも同じ値)。"""
    return "full" if "full" in levels else levels[-1]


def _month_list(start: pd.Timestamp, end: pd.Timestamp) -> List[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end - pd.offsets.MonthBegin(1), freq="MS"))


def simulate_period(P: Prepared, start: pd.Timestamp, end: pd.Timestamp, n_sims: int, levels: List[str],
                    max_races_per_month: Optional[int] = None):
    """[start, end) を月次で処理し、(馬単位DF, レース単位DF) を返す。"""
    cfg, ds, store = P.cfg, P.ds, P.store
    horse_frames, race_rows = [], []
    positions_all = np.array(sorted(store.ability_ctx))
    dates_all = ds.races.loc[positions_all, "date"].to_numpy()
    ref_level = reference_level(levels)
    for month in _month_list(start, end):
        t0 = time.time()
        bundle = P.bundle(month)
        nxt = month + pd.offsets.MonthBegin(1)
        sel = positions_all[(dates_all >= np.datetime64(month)) & (dates_all < np.datetime64(nxt))]
        if max_races_per_month:
            sel = sel[:max_races_per_month]
        for pos in sel:
            ctx = store.ability_ctx[int(pos)]
            outcome = store.outcomes[int(pos)]
            snap = ds.snapshot(ctx.month_idx)
            full_result = None
            for level in levels:
                if level not in bundle.perf_models:
                    continue
                result = simulate_race(ctx, bundle, snap, cfg, n_sims=n_sims,
                                       perf_level=level, first_turn_default=ds.first_turn_default)
                h = result.horses[["race_id", "horse_id", "umaban", "wakuban", "win_probability", "top2_probability",
                                   "top3_probability", "mean_early_position", "lead_probability",
                                   "mean_rel_time_sec", "win_odds_reference"]].copy()
                h["level"] = level
                h["date"] = ctx.date
                h["finish"] = outcome["finish"].to_numpy()
                h["time_sec"] = outcome["time_sec"].to_numpy()
                h["q_early_actual"] = outcome["q_early"].to_numpy()
                h["early_rank_actual"] = outcome["early_rank"].to_numpy()
                if level == ref_level:
                    full_result = result
                horse_frames.append(h)
            if full_result is not None:
                race_rows.append(_race_record(ctx, full_result, bundle, ds, int(pos)))
        LOGGER.info("backtest month %s: %d races, bundle %s (%.0fs)", month.strftime("%Y-%m"), len(sel),
                    bundle.warnings or "ok", time.time() - t0)
    horses = pd.concat(horse_frames, ignore_index=True)
    horses["target"] = (horses["finish"] == 1).astype(int)
    return horses, pd.DataFrame(race_rows)


def _race_record(ctx, result, bundle, ds, pos) -> dict:
    race = result.race
    row = ds.races.loc[pos]
    track = ctx.track_context
    thresholds = thresholds_for(bundle.display_thresholds, ctx.surface, ctx.distance_m)
    split_ci = race["predicted_early_split_p10_p90_sec"] or [np.nan, np.nan]
    time_ci = race.get("winning_time_p10_p90_sec") or [np.nan, np.nan]
    rec = {
        "race_id": ctx.race_id, "date": ctx.date, "track": ctx.track, "surface": ctx.surface,
        "distance_m": ctx.distance_m, "going": ctx.going, "field_size": ctx.n, "meet_day": ctx.meet_day,
        "early_ref": ctx.early_ref, "early_actual": row["early_split_sec"], "pace_delta_actual": row["pace_delta"],
        "early_pred_mean": race["predicted_early_split_mean_sec"],
        "early_pred_p10": split_ci[0], "early_pred_p90": split_ci[1],
        "pace_delta_pred_mean": race["pace_delta_mean_sec"],
        "pace_delta_regression_mean": race["pace_delta_regression_mean_sec"],
        "win_time_actual": row["win_time_sec"], "win_time_base": ctx.win_time_base,
        "win_time_full_mean": race.get("expected_winning_time_sec", np.nan),
        "win_time_full_p10": time_ci[0], "win_time_full_p90": time_ci[1],
        "track_bias_sec": track.track_bias_sec, "bias_n_eff": track.effective_sample_size,
        "fallback_level": track.fallback_level, "going_changed": track.going_changed,
        "n_previous_day": track.source_counts["previous_day"], "n_previous_week": track.source_counts["previous_week"],
        "n_previous_meet": track.source_counts["previous_meet"],
        "n_previous_year": track.source_counts["previous_year_same_season"],
        "opening_week": bool(ctx.meet_day <= 2),
        "actual_pace_bucket": int(pace_display_bucket_index(np.array([row["pace_delta"]]), thresholds)[0])
        if np.isfinite(row["pace_delta"]) else -1,
    }
    for name in PACE_BUCKETS:
        rec[f"pace_prob_{name}"] = race["pace_display_probabilities"][name]
    # 時計アブレーション(解析的な点予測。ペースを使うのは full のみ)
    if bundle.time_models and np.isfinite(ctx.win_time_base):
        xt = time_features(ctx, track, np.array([race["pace_delta_mean_sec"]]), np.zeros((1, 4)))
        for level in ("baseline", "track_bias", "field_ability"):
            rec[f"win_time_{level}"] = float(ctx.win_time_base + bundle.time_models[level].predict(xt)[0])
    return rec


def attach_existing_ranker(horses: pd.DataFrame, csv_path: Path = EXISTING_WF_CSV) -> pd.DataFrame:
    """既存Rankerの同一(race, horse)の確率と単勝払戻を結合(読み取り専用)。"""
    if not csv_path.exists():
        horses["ranker_win_probability"] = np.nan
        horses["win_payout"] = np.nan
        return horses
    ranker = pd.read_csv(csv_path, dtype={"race_id": str, "horse_id": str},
                         usecols=["race_id", "horse_id", "ranker_win_probability", "win_payout"])
    return horses.merge(ranker, on=["race_id", "horse_id"], how="left")


def calibrate_walk_forward(horses: pd.DataFrame, window_months: int, grid: List[float]):
    """月ごとに、直前window_monthsの予測だけでgammaを決めて確率を校正する(月mの校正に月m以降は使わない)。"""
    horses = horses.copy()
    horses["p_cal"] = np.nan
    gammas = []
    months = horses["date"].dt.to_period("M").dt.to_timestamp()
    for level in horses["level"].unique():
        lv = horses["level"] == level
        for month in sorted(months[lv].unique()):
            hist = horses[lv & (horses["date"] >= month - pd.DateOffset(months=window_months)) & (horses["date"] < month)]
            if hist["race_id"].nunique() < 100:
                continue
            gamma = ev.fit_gamma(hist, "win_probability", grid)
            rows = lv & (months == month)
            horses.loc[rows, "p_cal"] = ev.power_normalize(horses[rows], "win_probability", gamma)
            gammas.append({"level": level, "month": pd.Timestamp(month).strftime("%Y-%m"), "gamma": gamma,
                           "calibration_races": int(hist["race_id"].nunique())})
    return horses, pd.DataFrame(gammas)


def evaluate_all(horses: pd.DataFrame, races: pd.DataFrame, test_start: pd.Timestamp, out_dir: Path) -> Dict:
    test = horses[horses["date"] >= test_start]
    present = [lv for lv in ALL_LEVELS if lv in set(test["level"])]
    ref_level = reference_level(present)
    # 既存Rankerと同一の(レース, 馬)集合だけに揃える
    full = test[test["level"] == ref_level]
    have = full.dropna(subset=["ranker_win_probability", "p_cal"])
    sizes = have.groupby("race_id").size()
    base_sizes = full.groupby("race_id").size()
    common_races = sizes[sizes == base_sizes.reindex(sizes.index)].index
    summary: Dict = {"common_races": int(len(common_races))}
    rows, calib_tables, roi_rows = [], [], []
    ranker = have[have["race_id"].isin(common_races)].copy()
    ranker["win_odds"] = ranker["win_odds_reference"]
    ranker["p"] = ranker["ranker_win_probability"]
    rows.append({"model": "existing_ranker", "calibrated": True, **ev.prob_metrics(ranker, "p")})
    calib_tables.append(ev.calibration_table(ranker, "p").assign(model="existing_ranker"))
    buy_rules = lambda col: (("top1", lambda f: pd.Series(True, index=f.index)), ("rule", ev.rule_selector(col)),
                             ("ev>=1.0", ev.ev_selector(col, 1.0)), ("ev>=1.2", ev.ev_selector(col, 1.2)))
    for label, selector in buy_rules("p"):
        roi_rows.append({"model": "existing_ranker", "buy_rule": label, **ev.roi_summary(ranker, "p", selector)})
    payouts = ranker[["race_id", "horse_id", "win_payout"]]
    subs: Dict[str, pd.DataFrame] = {}
    for level in present:
        sub = test[(test["level"] == level) & test["race_id"].isin(common_races)].dropna(subset=["p_cal"]).copy()
        if sub.empty:
            continue
        sub = sub.drop(columns=["win_payout"]).merge(payouts, on=["race_id", "horse_id"], how="left")
        sub["win_odds"] = sub["win_odds_reference"]
        subs[level] = sub
    rt_rows = []
    for level, sub in subs.items():
        for name, col in (("raw", "win_probability"), ("calibrated", "p_cal")):
            rows.append({"model": f"raceverse_{level}", "calibrated": name == "calibrated", **ev.prob_metrics(sub, col)})
            calib_tables.append(ev.calibration_table(sub, col).assign(model=f"raceverse_{level}_{name}"))
        for label, selector in buy_rules("p_cal"):
            roi_rows.append({"model": f"raceverse_{level}_calibrated", "buy_rule": label,
                             **ev.roi_summary(sub, "p_cal", selector)})
        rt_rows.append({"model": f"raceverse_{level}", **bias_eval.relative_time_metrics(sub)})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out_dir / "probability_metrics.csv", index=False)
    pd.concat(calib_tables).to_csv(out_dir / "calibration_tables.csv", index=False)
    pd.DataFrame(roi_rows).to_csv(out_dir / "roi_reference.csv", index=False)
    pd.DataFrame(rt_rows).to_csv(out_dir / "relative_time_metrics.csv", index=False)
    summary["probability_metrics"] = metrics.to_dict("records")
    summary["roi_reference"] = roi_rows
    summary["relative_time"] = rt_rows
    summary.update(bias_eval.course_bias_comparison(subs, races, BIAS_PAIRS, out_dir))
    summary.update(_evaluate_races(races, test_start, out_dir))
    summary.update(_evaluate_formation(test, out_dir, ref_level))
    return summary


def _evaluate_formation(test: pd.DataFrame, out_dir: Path, ref_level: str = "full") -> Dict:
    full = test[(test["level"] == ref_level)].dropna(subset=["q_early_actual"])
    if full.empty:
        return {}
    mae_q = float((full["mean_early_position"] - full["q_early_actual"]).abs().mean())
    naive = float((full["q_early_actual"] - full["q_early_actual"].mean()).abs().mean())
    hits = []
    for _, g in full.groupby("race_id"):
        leader = g[g["early_rank_actual"] == 1]
        if leader.empty:
            continue
        top3 = g.nlargest(3, "lead_probability")["horse_id"]
        hits.append(float(leader["horse_id"].iloc[0] in set(top3)))
    result = {"formation": {"early_position_mae_relative": mae_q, "naive_constant_mae": naive,
                            "leader_in_top3_lead_prob_rate": float(np.mean(hits)) if hits else None,
                            "n_runners": int(len(full))}}
    (out_dir / "formation_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _err(a: pd.Series, b: pd.Series) -> Dict[str, float]:
    d = (a - b).dropna()
    if d.empty:
        return {"n": 0, "mae": float("nan"), "rmse": float("nan"), "bias": float("nan")}
    return {"n": int(len(d)), "mae": float(d.abs().mean()), "rmse": float(np.sqrt((d ** 2).mean())), "bias": float(d.mean())}


def _evaluate_races(races: pd.DataFrame, test_start: pd.Timestamp, out_dir: Path) -> Dict:
    r = races[races["date"] >= test_start].copy()
    out: Dict = {"races_evaluated": int(len(r))}
    pace = {
        "early_split": {
            "model_sim_mean": _err(r["early_pred_mean"], r["early_actual"]),
            "reference_baseline_only": _err(r["early_ref"], r["early_actual"]),
            "regression_mean_only": _err(r["early_ref"] + r["pace_delta_regression_mean"], r["early_actual"]),
        },
        "p10_p90_coverage": float(((r["early_actual"] >= r["early_pred_p10"]) & (r["early_actual"] <= r["early_pred_p90"])).mean()),
    }
    observed = r[r["actual_pace_bucket"] >= 0]
    table = pd.DataFrame({
        "bucket": PACE_BUCKETS,
        "predicted_rate": [observed[f"pace_prob_{b}"].mean() for b in PACE_BUCKETS],
        "actual_rate": [(observed["actual_pace_bucket"] == i).mean() for i in range(5)],
    })
    table.to_csv(out_dir / "pace_display_calibration.csv", index=False)
    pace["display_bucket_calibration"] = table.to_dict("records")
    out["pace"] = pace

    t = r.dropna(subset=["win_time_actual", "win_time_full_mean"]).copy()
    timing: Dict = {"winning_time": {}}
    for level in ("baseline", "track_bias", "field_ability"):
        if f"win_time_{level}" in t:
            timing["winning_time"][level] = _err(t[f"win_time_{level}"], t["win_time_actual"])
    timing["winning_time"]["full"] = _err(t["win_time_full_mean"], t["win_time_actual"])
    timing["p10_p90_coverage"] = float(((t["win_time_actual"] >= t["win_time_full_p10"]) &
                                        (t["win_time_actual"] <= t["win_time_full_p90"])).mean())
    t["distance_band"] = pd.cut(t["distance_m"], [0, 1300, 1600, 2000, 9999],
                                labels=["~1300", "1400-1600", "1700-2000", "2100+"]).astype(str)
    segments = []
    for column in ("fallback_level", "opening_week", "going_changed", "surface", "distance_band"):
        for key, g in t.groupby(column):
            seg_base = _err(g["win_time_baseline"], g["win_time_actual"]) if "win_time_baseline" in g else {}
            segments.append({"segment": column, "value": str(key), **_err(g["win_time_full_mean"], g["win_time_actual"]),
                             "baseline_mae": seg_base.get("mae")})
    pd.DataFrame(segments).to_csv(out_dir / "time_error_by_segment.csv", index=False)
    out["timing"] = timing
    r.to_csv(out_dir / "race_level.csv", index=False)
    return out


def run_backtest(P: Prepared, out_dir: Optional[Path] = None, n_sims: Optional[int] = None,
                 levels: Optional[List[str]] = None, max_races_per_month: Optional[int] = None,
                 test_start: Optional[str] = None, test_end: Optional[str] = None) -> Dict:
    cfg = P.cfg
    n_sims = n_sims or cfg.backtest.n_simulations
    levels = levels or LEVELS
    test_start_ts = pd.Timestamp(test_start or cfg.backtest.test_start)
    test_end_ts = pd.Timestamp(test_end or cfg.backtest.test_end)
    burn_start = test_start_ts - pd.DateOffset(months=cfg.calibration.burn_in_months)
    out_dir = Path(out_dir or REPORT_DIR / f"backtest_{test_start_ts:%Y%m}_{test_end_ts:%Y%m}")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    horses, races = simulate_period(P, burn_start, test_end_ts, n_sims, levels, max_races_per_month)
    LOGGER.info("simulation done: %d horse rows, %d races (%.0fs)", len(horses), len(races), time.time() - t0)
    horses = attach_existing_ranker(horses)
    horses, gammas = calibrate_walk_forward(horses, cfg.calibration.window_months, cfg.calibration.gamma_grid)
    gammas.to_csv(out_dir / "calibration_gammas.csv", index=False)
    horses[horses["date"] >= test_start_ts].to_csv(out_dir / "predictions.csv", index=False)
    summary = evaluate_all(horses, races, test_start_ts, out_dir)
    summary["config"] = {"n_simulations": n_sims, "seed": cfg.random_seed, "levels": levels,
                         "test_start": str(test_start_ts.date()), "test_end": str(test_end_ts.date()),
                         "burn_in_start": str(burn_start.date()),
                         "odds_note": "DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only"}
    summary["runtime_sec"] = time.time() - t0
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    from raceverse.reports import write_backtest_markdown
    write_backtest_markdown(summary, out_dir)
    return summary

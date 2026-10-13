#!/usr/bin/env python3
"""All-combination (2^12 - 1) feature-group ablation of the production Ranker.

This is an independent validation harness. It never touches the production
Ranker configuration; it re-uses the production feature list, LightGBM
hyper-parameters, relevance definition, preprocessing and monthly
Walk-Forward / temperature-calibration procedure from
``src.ranker_walk_forward_backtest``.

Computation sharing (numerically identical to the baseline procedure):
  * Feature standardisation is column-wise, so the 86-column matrices are built
    once per training window and sliced per combination.
  * The "preliminary" calibration Ranker of month m (trained on dates < m-3M)
    is exactly the final Ranker of month m-3M. One fit per (combination, month k)
    therefore scores month k (final prediction) and the window [k, k+3M)
    (calibration for month k+3M).

Sub-commands: validate | prepare | bench | run | assemble | verify
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES
except ModuleNotFoundError:  # direct execution
    import ranker_walk_forward_backtest as wf
    from backtest import RANKER_MARGIN_CORRECTION_FEATURES

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache" / "ranker_group_ablation"
OUT_DIR = ROOT / "reports" / "ranker_group_ablation"
SEED = wf.SEED
CALIBRATION_MONTHS = wf.CALIBRATION_MONTHS
CHUNK = 16

GROUP_NAMES = {
    "G1": "出走履歴・実績",
    "G2": "距離・出走条件",
    "G3": "過去走の勝ち馬の能力",
    "G4": "過去走の出走メンバーの強さ",
    "G5": "過去走の勝ち馬のクラス・賞金実績",
    "G6": "序盤位置・展開",
    "G7": "補正後パフォーマンス",
    "G8": "隠れた能力・補正量",
    "G9": "レース賞金・クラス変化",
    "G10": "過去の勝ち着差",
    "G11": "クラス適合パフォーマンス",
    "G12": "コース・枠順バイアス",
}


def _winner_class_prize() -> list[str]:
    series = [
        "winner_max_race_class_before_target",
        "winner_best_win_class_before_target",
        "winner_max_prize_before_target",
        "winner_mean_prize_before_target",
    ]
    return [f"last{n}_{name}" for name in series for n in (1, 2, 3)]


GROUPS: dict[str, list[str]] = {
    "G1": ["career_places", "recent5_win_rate", "races_last_180d", "races_last_365d"],
    "G2": ["last1_distance", "current_distance", "field_size"],
    "G3": [
        "last1_winner_strength", "last2_winner_strength", "last3_winner_strength",
        "last1_winner_strength_v2", "last2_winner_strength_v2",
        "max_winner_strength_last3", "mean_winner_strength_last3",
        "weighted_winner_strength_last3", "best_strong_opponent_performance_last3",
    ],
    "G4": [
        "last1_field_strength", "last2_field_strength", "last3_field_strength",
        "last1_field_strength_v2", "last2_field_strength_v2", "last3_field_strength_v2",
        "last1_field_max_strength_v2", "last2_field_max_strength_v2", "last3_field_max_strength_v2",
        "last1_field_top3_mean_strength_v2", "last2_field_top3_mean_strength_v2",
        "last3_field_top3_mean_strength_v2", "opponent_history_missing_last3",
    ],
    "G5": _winner_class_prize(),
    "G6": ["last1_position_advantage", "last2_position_advantage", "last3_position_advantage", "setup_improvement"],
    "G7": [
        "last1_adjusted_performance", "last2_adjusted_performance", "last3_adjusted_performance",
        "best_adjusted_performance_last3", "mean_adjusted_performance_last3",
        "weighted_adjusted_performance_last3",
    ],
    "G8": [
        "hidden_strength_last1", "hidden_strength_last3", "max_hidden_strength_last3",
        "max_strong_against_bias_last3", "strong_against_bias_last1",
        "strong_against_bias_last2", "strong_against_bias_last3", "hidden_strength_x_race_strength",
    ],
    "G9": [
        "race_first_prize", "race_first_prize_log", "race_total_top5_prize_log",
        "last2_race_first_prize", "last3_race_first_prize", "last1_race_first_prize_log",
        "last2_race_first_prize_log", "last3_race_first_prize_log", "max_race_prize_last3",
        "prize_change_from_last1", "prize_change_from_last3_mean",
        "prize_ratio_vs_last1", "prize_ratio_vs_last3_mean",
    ],
    "G10": [
        "last1_winning_margin", "last2_winning_margin", "last3_winning_margin",
        "last4_winning_margin", "last5_winning_margin",
        "mean_winning_margin_last5", "max_winning_margin_last5",
    ],
    "G11": [
        "last1_class_matched_adjusted_performance", "last2_class_matched_adjusted_performance",
        "last3_class_matched_adjusted_performance", "mean_class_matched_adjusted_performance_last3",
        "class_matched_sample_count",
    ],
    "G12": ["course_gate_win_rate", "course_gate_place_rate"],
}
EXPECTED_SIZES = {"G1": 4, "G2": 3, "G3": 9, "G4": 13, "G5": 12, "G6": 4, "G7": 6, "G8": 8,
                  "G9": 13, "G10": 7, "G11": 5, "G12": 2}
GROUP_KEYS = list(GROUPS)
N_GROUPS = len(GROUP_KEYS)
N_COMBOS = 2 ** N_GROUPS - 1
PRODUCTION_FEATURES = list(RANKER_MARGIN_CORRECTION_FEATURES)
# Column order of the ablation matrices = production order; a combination keeps that order.
COLUMN_INDEX = {name: i for i, name in enumerate(PRODUCTION_FEATURES)}


def combo_index_to_mask(index: int) -> str:
    """Combination index 1..4095 -> 12-char bitmask, G1 leftmost ('1' = group ON)."""
    return "".join("1" if (index >> position) & 1 else "0" for position in range(N_GROUPS))


def mask_to_groups(mask: str) -> list[str]:
    return [key for key, bit in zip(GROUP_KEYS, mask) if bit == "1"]


def mask_to_features(mask: str) -> list[str]:
    selected = {name for key in mask_to_groups(mask) for name in GROUPS[key]}
    return [name for name in PRODUCTION_FEATURES if name in selected]


def mask_to_columns(mask: str) -> np.ndarray:
    return np.array([COLUMN_INDEX[name] for name in mask_to_features(mask)], dtype=np.int64)


ALL_ON_MASK = "1" * N_GROUPS
ALL_ON_INDEX = N_COMBOS


def classification_report() -> dict:
    flat = [name for key in GROUP_KEYS for name in GROUPS[key]]
    production = PRODUCTION_FEATURES
    duplicates = sorted({name for name in flat if flat.count(name) > 1})
    unclassified = [name for name in production if name not in set(flat)]
    unknown = [name for name in flat if name not in set(production)]
    size_mismatch = {key: (len(GROUPS[key]), EXPECTED_SIZES[key]) for key in GROUP_KEYS
                     if len(GROUPS[key]) != EXPECTED_SIZES[key]}
    all_on = mask_to_features(ALL_ON_MASK)
    return {
        "production_feature_count": len(production),
        "production_unique": len(set(production)),
        "classified_count": len(flat),
        "duplicates": duplicates,
        "unclassified_in_production": unclassified,
        "unknown_not_in_production": unknown,
        "group_size_mismatch(actual,expected)": size_mismatch,
        "all_on_equals_production_set": set(all_on) == set(production),
        "all_on_equals_production_order": all_on == production,
        "ok": not (duplicates or unclassified or unknown or size_mismatch)
        and set(all_on) == set(production) and len(flat) == len(production) == 86,
    }


# ---------------------------------------------------------------- data preparation

def test_months(start: str, end: str) -> list[pd.Timestamp]:
    return wf.month_starts(pd.Timestamp(start), pd.Timestamp(end))


def fit_months(months: list[pd.Timestamp]) -> list[pd.Timestamp]:
    first = months[0] - pd.DateOffset(months=CALIBRATION_MONTHS)
    return list(pd.date_range(first, months[-1], freq="MS"))


def load_base_frame(end: pd.Timestamp) -> pd.DataFrame:
    """Evaluation universe: same filters as the production backtest (cached to parquet)."""
    path = CACHE_DIR / "frame.parquet"
    if path.exists():
        return pd.read_parquet(path)
    wf.TEST_END = max(wf.TEST_END, end)
    frame, _ = wf.load_frame(PRODUCTION_FEATURES)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    return frame


def window_paths(k: pd.Timestamp) -> dict[str, Path]:
    tag = k.strftime("%Y-%m")
    base = CACHE_DIR / "matrices"
    return {name: base / f"{tag}_{name}.npy" for name in ("xtr", "ytr", "gtr", "xte")} | {"meta": base / f"{tag}_meta.json"}


def prepare_window(frame: pd.DataFrame, k: pd.Timestamp) -> None:
    """Standardised 86-column matrices for the Ranker of month k (train < k, score [k, k+3M))."""
    paths = window_paths(k)
    if paths["meta"].exists():
        return
    paths["xtr"].parent.mkdir(parents=True, exist_ok=True)
    train = frame[frame["date"] < k]
    test = frame[(frame["date"] >= k) & (frame["date"] < k + pd.DateOffset(months=CALIBRATION_MONTHS))]
    # Identical row ordering/encoding to wf.ranker_scores.
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)
    x_train, x_test = wf.encode_train_test(ordered, test, PRODUCTION_FEATURES)
    relevance = ordered.groupby("race_id")["actual_rank"].transform("max") - ordered["actual_rank"] + 1
    group_sizes = ordered.groupby("race_id", sort=False).size().to_numpy()
    np.save(paths["xtr"], x_train)
    np.save(paths["ytr"], relevance.to_numpy())
    np.save(paths["gtr"], group_sizes)
    np.save(paths["xte"], x_test)
    month_rows = int((test["date"] < k + pd.DateOffset(months=1)).sum())
    meta = {"k": k.strftime("%Y-%m"), "train_rows": len(ordered), "train_races": int(len(group_sizes)),
            "test_rows": len(test), "month_rows": month_rows}
    paths["meta"].write_text(json.dumps(meta), encoding="utf-8")


def cmd_prepare(args: argparse.Namespace) -> None:
    months = test_months(args.test_start, args.test_end)
    frame = load_base_frame(pd.Timestamp(args.test_end))
    frame = frame[frame["date"] < pd.Timestamp(args.test_end)].reset_index(drop=True)
    for k in fit_months(months):
        started = time.time()
        prepare_window(frame, k)
        print(f"prepared {k:%Y-%m} in {time.time() - started:.1f}s", flush=True)


# ---------------------------------------------------------------- fitting

def segment_starts(race_ids: np.ndarray) -> np.ndarray:
    change = np.flatnonzero(race_ids[1:] != race_ids[:-1]) + 1
    return np.concatenate([[0], change])


def softmax_segments(scores: np.ndarray, starts: np.ndarray, lengths: np.ndarray, temperature: float) -> np.ndarray:
    """Race-wise softmax; same arithmetic as wf.softmax_by_race (rows of a race are contiguous)."""
    values = scores / temperature
    values = values - np.repeat(np.maximum.reduceat(values, starts), lengths)
    weights = np.exp(np.clip(values, -50, 50))
    return weights / np.repeat(np.add.reduceat(weights, starts), lengths)


def choose_temperature(scores: np.ndarray, target: np.ndarray, starts: np.ndarray, lengths: np.ndarray) -> tuple[float, float]:
    best_temperature, best_brier = 1.0, float("inf")
    for temperature in wf.TEMPERATURES:
        probability = softmax_segments(scores, starts, lengths, float(temperature))
        brier = float(np.average((target - probability) ** 2))
        if brier < best_brier:
            best_temperature, best_brier = float(temperature), brier
    return best_temperature, best_brier


def make_ranker(n_jobs: int):
    from lightgbm import LGBMRanker
    return LGBMRanker(objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3], n_estimators=180,
                      learning_rate=0.04, num_leaves=15, max_depth=5, min_child_samples=80,
                      reg_lambda=2.0, random_state=SEED, verbosity=-1, n_jobs=n_jobs)


def window_arrays(k: pd.Timestamp, frame_keys: pd.DataFrame):
    paths = window_paths(k)
    meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    return (np.load(paths["xtr"], mmap_mode="r"), np.load(paths["ytr"]), np.load(paths["gtr"]),
            np.load(paths["xte"], mmap_mode="r"), meta)


def result_path(out_dir: Path, k: str, chunk: int) -> Path:
    return out_dir / "scores" / f"k={k}" / f"chunk_{chunk:04d}.npz"


def existing_result_files(path: Path) -> list[Path]:
    return sorted(p for p in path.parent.glob(f"{path.stem}*.npz") if ".tmp." not in p.name) if path.parent.exists() else []


def fit_chunk(task: tuple) -> dict:
    """Fit all combinations of one chunk for month k; returns a status dict (never raises)."""
    k_text, chunk, out_dir_text, test_end_text, n_jobs, limit_combos = task
    out_dir = Path(out_dir_text)
    started = time.time()
    path = result_path(out_dir, k_text, chunk)
    k = pd.Timestamp(k_text + "-01")
    indexes = [i for i in range(chunk * CHUNK + 1, (chunk + 1) * CHUNK + 1) if i <= N_COMBOS]
    if limit_combos:
        indexes = [i for i in indexes if i in set(limit_combos)]
    saved = existing_result_files(path)
    done_before = {int(value) for old in saved for value in np.load(old)["combo"]}
    indexes = [i for i in indexes if i not in done_before]
    if not indexes:
        return {"k": k_text, "chunk": chunk, "status": "skipped", "seconds": 0.0}
    if saved:
        path = path.with_name(f"{path.stem}_{len(saved)}.npz")
    failures: list[dict] = []
    try:
        frame = pd.read_parquet(CACHE_DIR / "frame.parquet", columns=["date", "race_id", "target"])
        frame = frame[frame["date"] < pd.Timestamp(test_end_text)].reset_index(drop=True)
        test_frame = frame[(frame["date"] >= k) & (frame["date"] < k + pd.DateOffset(months=CALIBRATION_MONTHS))]
        x_train, relevance, group_sizes, x_test, meta = window_arrays(k, test_frame)
        # Matrices may have been prepared with a later evaluation end; rows are date-ordered prefixes.
        x_test = x_test[:len(test_frame)]
        month_rows = meta["month_rows"]
        race_ids = test_frame["race_id"].to_numpy().astype(str)
        starts = segment_starts(race_ids)
        lengths = np.diff(np.append(starts, len(race_ids)))
        target = test_frame["target"].to_numpy(dtype=float)
        k_plus = k + pd.DateOffset(months=CALIBRATION_MONTHS)
    except Exception:  # data problems fail the whole chunk, recorded below
        return {"k": k_text, "chunk": chunk, "status": "failed", "seconds": time.time() - started,
                "failures": [{"combo": None, "error": traceback.format_exc()}]}
    done_indexes, month_scores, temperatures, calib_brier, fit_seconds = [], [], [], [], []
    for index in indexes:
        mask = combo_index_to_mask(index)
        try:
            columns = mask_to_columns(mask)
            t0 = time.time()
            model = make_ranker(n_jobs)
            model.fit(np.ascontiguousarray(x_train[:, columns]), relevance, group=group_sizes)
            scores = model.predict(np.ascontiguousarray(x_test[:, columns]), raw_score=True)
            fit_seconds.append(time.time() - t0)
            temperature, brier = choose_temperature(scores, target, starts, lengths)
            done_indexes.append(index)
            month_scores.append(scores[:month_rows])
            temperatures.append(temperature)
            calib_brier.append(brier)
        except Exception:
            failures.append({"combo": index, "mask": mask, "error": traceback.format_exc()})
    if done_indexes:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npz")
        np.savez(tmp, combo=np.array(done_indexes), month_scores=np.vstack(month_scores),
                 temperature_for_k_plus=np.array(temperatures), calibration_brier=np.array(calib_brier),
                 fit_seconds=np.array(fit_seconds), k_plus=k_plus.strftime("%Y-%m"))
        os.replace(tmp, path)
    return {"k": k_text, "chunk": chunk, "status": "failed" if failures else "ok",
            "seconds": time.time() - started, "failures": failures, "fits": len(done_indexes)}


def append_log(out_dir: Path, record: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "run_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def cmd_run(args: argparse.Namespace) -> None:
    months = test_months(args.test_start, args.test_end)
    out_dir = Path(args.out)
    ks = [k.strftime("%Y-%m") for k in fit_months(months)]
    n_chunks = (N_COMBOS + CHUNK - 1) // CHUNK
    chunks = range(n_chunks) if args.chunks is None else range(args.chunks)
    limit = None
    if args.combos_file:
        limit = sorted(json.loads(Path(args.combos_file).read_text(encoding="utf-8")))
        chunks = sorted({(i - 1) // CHUNK for i in limit})
    tasks = [(k, c, str(out_dir), args.test_end, 1, limit) for c in chunks for k in ks]
    # fit_chunk itself skips finished combinations, so this only drops fully completed chunks cheaply.
    if limit is None:
        tasks = [t for t in tasks if not result_path(out_dir, t[0], t[1]).exists()]
    print(f"{len(tasks)} chunk tasks remaining; workers={args.workers}", flush=True)
    started = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for record in pool.map(fit_chunk, tasks, chunksize=1):
            done += 1
            append_log(out_dir, {key: value for key, value in record.items()})
            if record["status"] == "failed":
                print(f"FAILED {record['k']} chunk {record['chunk']}: see run_log.jsonl", flush=True)
            if done % 10 == 0 or done == len(tasks):
                elapsed = time.time() - started
                print(f"{done}/{len(tasks)} chunks, {elapsed / 60:.1f} min elapsed, "
                      f"eta {(elapsed / done) * (len(tasks) - done) / 60:.1f} min", flush=True)


# ---------------------------------------------------------------- assembly

def assemble(out_dir: Path, test_start: str, test_end: str) -> dict:
    """Collect chunk results into score/temperature matrices for the evaluation months."""
    months = test_months(test_start, test_end)
    frame = pd.read_parquet(CACHE_DIR / "frame.parquet")
    frame = frame[(frame["date"] >= pd.Timestamp(test_start)) & (frame["date"] < pd.Timestamp(test_end))].reset_index(drop=True)
    month_of = frame["date"].dt.strftime("%Y-%m").to_numpy()
    scores = np.full((N_COMBOS, len(frame)), np.nan)
    temperature = np.full((N_COMBOS, len(months)), np.nan)
    calibration_brier = np.full((N_COMBOS, len(months)), np.nan)
    month_position = {m.strftime("%Y-%m"): i for i, m in enumerate(months)}
    for k_dir in sorted((out_dir / "scores").glob("k=*")):
        k = k_dir.name[2:]
        for path in sorted(p for p in k_dir.glob("chunk_*.npz") if ".tmp." not in p.name):
            data = np.load(path)
            combo = data["combo"] - 1
            if k in month_position:
                rows = np.flatnonzero(month_of == k)
                scores[np.ix_(combo, rows)] = data["month_scores"]
            k_plus = str(data["k_plus"])
            if k_plus in month_position:
                temperature[combo, month_position[k_plus]] = data["temperature_for_k_plus"]
                calibration_brier[combo, month_position[k_plus]] = data["calibration_brier"]
    complete = ~np.isnan(scores).any(axis=1) & ~np.isnan(temperature).any(axis=1)
    return {"frame": frame, "scores": scores, "temperature": temperature,
            "calibration_brier": calibration_brier, "complete": complete, "months": months}


def combo_probabilities(frame: pd.DataFrame, scores: np.ndarray, temperatures: np.ndarray,
                        months: list[pd.Timestamp]) -> np.ndarray:
    """Race-wise softmax of one combination over the whole evaluation period (month-specific T)."""
    race_ids = frame["race_id"].to_numpy().astype(str)
    starts = segment_starts(race_ids)
    lengths = np.diff(np.append(starts, len(race_ids)))
    row_month = frame["date"].dt.strftime("%Y-%m").to_numpy()
    probability = np.zeros(len(frame))
    for position, month in enumerate(months):
        rows = np.flatnonzero(row_month == month.strftime("%Y-%m"))
        if len(rows) == 0:
            continue
        month_race = race_ids[rows]
        month_starts = segment_starts(month_race)
        month_lengths = np.diff(np.append(month_starts, len(month_race)))
        probability[rows] = softmax_segments(scores[rows], month_starts, month_lengths, float(temperatures[position]))
    return probability


def cmd_verify(args: argparse.Namespace) -> None:
    """Re-run selected combinations with the production code path and compare with the fast path."""
    months = test_months(args.test_start, args.test_end)
    out_dir = Path(args.out) / "verify"
    indexes = sorted({ALL_ON_INDEX, *args.verify_combos})
    ks = [k.strftime("%Y-%m") for k in fit_months(months)]
    for k in ks:
        for chunk in sorted({(i - 1) // CHUNK for i in indexes}):
            record = fit_chunk((k, chunk, str(out_dir), args.test_end, 1, indexes))
            if record["status"] == "failed":
                raise SystemExit(f"verify fit failed: {record}")
    # fit_chunk covers whole chunks only when limit_combos is None; limited here to the requested ones.
    result = assemble(out_dir, args.test_start, args.test_end)
    frame = result["frame"]
    full_frame, _ = wf.load_frame(PRODUCTION_FEATURES)
    report = []
    for index in indexes:
        mask = combo_index_to_mask(index)
        features = mask_to_features(mask)
        baseline, _ = wf.monthly_walk_forward(full_frame, features, months, CALIBRATION_MONTHS)
        fast = combo_probabilities(frame, result["scores"][index - 1], result["temperature"][index - 1], months)
        assert (baseline["race_id"].to_numpy() == frame["race_id"].to_numpy()).all()
        assert (baseline["horse_id"].to_numpy() == frame["horse_id"].to_numpy()).all()
        difference = np.abs(baseline["ranker_win_probability"].to_numpy() - fast)
        fast_rank = pd.Series(fast).groupby(frame["race_id"].to_numpy()).rank(method="first", ascending=False).astype(int)
        report.append({"combo": index, "mask": mask, "features": len(features),
                       "max_abs_probability_difference": float(difference.max()),
                       "mean_abs_probability_difference": float(difference.mean()),
                       "top1_selection_mismatches": int((fast_rank.to_numpy() != baseline["prediction_rank"].to_numpy()).sum()),
                       "rows": len(frame)})
        print(report[-1], flush=True)
    (Path(args.out) / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def cmd_assemble(args: argparse.Namespace) -> None:
    result = assemble(Path(args.out), args.test_start, args.test_end)
    print(f"complete combinations: {int(result['complete'].sum())}/{N_COMBOS}")


# ---------------------------------------------------------------- validate / bench

def cmd_validate(args: argparse.Namespace) -> None:
    report = classification_report()
    available = set(pd.read_parquet(wf.CACHE, columns=None).columns) if args.check_cache else None
    if available is not None:
        report["missing_in_feature_cache"] = [name for name in PRODUCTION_FEATURES if name not in available]
        report["ok"] = report["ok"] and not report["missing_in_feature_cache"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        sys.exit("特徴量分類が本番86特徴量と一致しません。実験を開始しません。")


def cmd_bench(args: argparse.Namespace) -> None:
    months = test_months(args.test_start, args.test_end)
    ks = fit_months(months)
    k = ks[args.bench_month_index]
    frame = pd.read_parquet(CACHE_DIR / "frame.parquet", columns=["date", "race_id", "target"])
    frame = frame[frame["date"] < pd.Timestamp(args.test_end)].reset_index(drop=True)
    test_frame = frame[(frame["date"] >= k) & (frame["date"] < k + pd.DateOffset(months=CALIBRATION_MONTHS))]
    x_train, relevance, group_sizes, x_test, meta = window_arrays(k, test_frame)
    print(f"k={k:%Y-%m} train_rows={meta['train_rows']} test_rows={meta['test_rows']}")
    rng = np.random.default_rng(0)
    for label, mask in [("all_on(86)", ALL_ON_MASK)] + [
        (f"random({mask_})", mask_) for mask_ in (combo_index_to_mask(int(i)) for i in rng.integers(1, N_COMBOS, 3))
    ]:
        columns = mask_to_columns(mask)
        for n_jobs in args.bench_jobs:
            t0 = time.time()
            model = make_ranker(n_jobs)
            model.fit(np.ascontiguousarray(x_train[:, columns]), relevance, group=group_sizes)
            model.predict(np.ascontiguousarray(x_test[:, columns]), raw_score=True)
            print(f"{label} features={len(columns)} n_jobs={n_jobs}: {time.time() - t0:.1f}s", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["validate", "prepare", "bench", "run", "assemble", "verify"])
    parser.add_argument("--test-start", default="2025-09-01")
    parser.add_argument("--test-end", default="2026-09-01", help="exclusive")
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--chunks", type=int, default=None, help="limit to the first N chunks (smoke test)")
    parser.add_argument("--check-cache", action="store_true")
    parser.add_argument("--bench-month-index", type=int, default=-1)
    parser.add_argument("--combos-file", default=None, help="JSON list of combination indexes to run")
    parser.add_argument("--verify-combos", type=int, nargs="*", default=[])
    parser.add_argument("--bench-jobs", type=int, nargs="+", default=[1])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    {"validate": cmd_validate, "prepare": cmd_prepare, "bench": cmd_bench,
     "run": cmd_run, "assemble": cmd_assemble, "verify": cmd_verify}[args.command](args)


if __name__ == "__main__":
    main()

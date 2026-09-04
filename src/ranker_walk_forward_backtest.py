#!/usr/bin/env python3
"""Leakage-safe monthly Ranker walk-forward backtest for the 8M prize universe.

Feature rows retain low-prize historical races when they were built. This module
only filters low-prize races from Ranker fitting and evaluation targets.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

try:
    from src.backtest import (
        CLEANUP_B_FEATURES,
        RANKER_MARGIN_CORRECTION_FEATURES,
    )
    from src.betting_rules import decide_bet
except ModuleNotFoundError:  # Supports direct script execution.
    from backtest import CLEANUP_B_FEATURES, RANKER_MARGIN_CORRECTION_FEATURES
    from betting_rules import decide_bet

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "phase5_f_features.parquet"
RACE_DB = ROOT / "data" / "raw" / "race.db"
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_walk_forward_12m"
TEST_START = pd.Timestamp("2025-09-01")
TEST_END = pd.Timestamp("2026-09-01")
CALIBRATION_MONTHS = 3
SEED = 42
TEMPERATURES = np.array([0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0])


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end - pd.offsets.MonthBegin(1), freq="MS"))


def payout_map() -> dict[tuple[str, int], float]:
    key_columns = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    pay_columns = [f"PayTansyo{index}{suffix}" for index in range(3) for suffix in ("Umaban", "Pay")]
    query = f"SELECT {', '.join(key_columns + pay_columns)} FROM NL_HR_PAY WHERE idYear >= '2012'"
    values: dict[tuple[str, int], float] = {}
    with sqlite3.connect(RACE_DB) as connection:
        for record in connection.execute(query):
            row = dict(zip(key_columns + pay_columns, record))
            race_id = "-".join(str(row[column]).strip() for column in key_columns)
            for index in range(3):
                try:
                    umaban = int(float(row[f"PayTansyo{index}Umaban"] or 0))
                    payout = float(row[f"PayTansyo{index}Pay"] or 0)
                except (TypeError, ValueError):
                    continue
                if umaban:
                    values[(race_id, umaban)] = payout
    return values


def load_frame(feature_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    identifiers = ["race_id", "date", "horse_id", "horse_name", "actual_rank", "target", "odds", "popularity", "umaban", "race_first_prize"]
    available = set(pd.read_parquet(CACHE).columns)
    selected_features = feature_columns if feature_columns is not None else CLEANUP_B_FEATURES
    if feature_columns is not None:
        missing = [feature for feature in selected_features if feature not in available]
        if missing:
            raise SystemExit(
                f"Feature cache is missing required Ranker features: {missing}. "
                "Rebuild it with `python -m src.build_feature_cache --model F`."
            )
    requested = list(dict.fromkeys(identifiers + selected_features))
    frame = pd.read_parquet(CACHE, columns=[column for column in requested if column in available])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[(frame["race_first_prize"] > 8_000_000) & (frame["actual_rank"] > 0) & (frame["odds"] > 0) & (frame["date"] < TEST_END)].copy()
    values = payout_map()
    frame["win_payout"] = [values.get((race_id, int(umaban)), 0.0) for race_id, umaban in zip(frame["race_id"], frame["umaban"])]
    frame.sort_values(["date", "race_id", "horse_id"], inplace=True)
    return frame.reset_index(drop=True), [column for column in selected_features if column in frame]


def encode_train_test(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray]:
    train_raw, test_raw = train[features].copy(), test[features].copy()
    categories = [column for column in features if train_raw[column].dtype.name in {"object", "category"}]
    numerics = [column for column in features if column not in categories]
    for column in numerics:
        train_raw[column] = pd.to_numeric(train_raw[column], errors="coerce")
        median = train_raw[column].median()
        train_raw[column] = train_raw[column].fillna(median).fillna(0.0)
        test_raw[column] = pd.to_numeric(test_raw[column], errors="coerce").fillna(median).fillna(0.0)
    for column in categories:
        train_raw[column] = train_raw[column].fillna("UNKNOWN").astype(str)
        test_raw[column] = test_raw[column].fillna("UNKNOWN").astype(str)
    train_x = pd.get_dummies(train_raw, columns=categories, dummy_na=True, dtype=float)
    test_x = pd.get_dummies(test_raw, columns=categories, dummy_na=True, dtype=float).reindex(columns=train_x.columns, fill_value=0.0)
    center, scale = train_x.mean(), train_x.std().replace(0.0, 1.0)
    return ((train_x - center) / scale).to_numpy(dtype=np.float32), ((test_x - center) / scale).to_numpy(dtype=np.float32)


def ranker_scores(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
    train_x, test_x = encode_train_test(train, test, features)
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)
    # Keep feature rows in exactly the same order as group sizes and relevance labels.
    ordered_x, test_x = encode_train_test(ordered, test, features)
    group_sizes = ordered.groupby("race_id", sort=False).size().tolist()
    relevance = ordered.groupby("race_id")["actual_rank"].transform("max") - ordered["actual_rank"] + 1
    model = LGBMRanker(objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3], n_estimators=180,
                       learning_rate=0.04, num_leaves=15, max_depth=5, min_child_samples=80,
                       reg_lambda=2.0, random_state=SEED, verbosity=-1)
    model.fit(ordered_x, relevance.to_numpy(), group=group_sizes)
    return model.predict(test_x, raw_score=True)


def softmax_by_race(scores: np.ndarray, race_ids: pd.Series, temperature: float) -> np.ndarray:
    result = np.zeros(len(scores), dtype=float)
    positions: dict[str, list[int]] = defaultdict(list)
    for index, race_id in enumerate(race_ids.astype(str)):
        positions[race_id].append(index)
    for indexes in positions.values():
        values = scores[indexes] / temperature
        values -= values.max()
        weights = np.exp(np.clip(values, -50, 50))
        result[indexes] = weights / weights.sum()
    return result


def select_temperature(calibration: pd.DataFrame, scores: np.ndarray) -> tuple[float, float]:
    best_temperature, best_brier = 1.0, float("inf")
    for temperature in TEMPERATURES:
        probability = softmax_by_race(scores, calibration["race_id"], float(temperature))
        brier = brier_score_loss(calibration["target"], probability)
        if brier < best_brier:
            best_temperature, best_brier = float(temperature), brier
    return best_temperature, best_brier


def add_probabilities(rows: pd.DataFrame, scores: np.ndarray, temperature: float, train_end: pd.Timestamp, mode: str) -> pd.DataFrame:
    result = rows.copy()
    result["ranker_score"] = scores
    result["ranker_win_probability"] = softmax_by_race(scores, result["race_id"], temperature)
    result["prediction_rank"] = result.groupby("race_id")["ranker_win_probability"].rank(method="first", ascending=False).astype(int)
    result["model_train_end_date"] = train_end.strftime("%Y-%m-%d")
    result["evaluation_mode"] = mode
    result["win_odds"] = result["odds"] / 10.0
    return result


def metrics(rows: pd.DataFrame) -> dict:
    probability = rows["ranker_win_probability"].to_numpy()
    target = rows["target"].to_numpy()
    top1 = rows[rows["prediction_rank"] == 1]
    top3 = rows[rows["prediction_rank"] <= 3]
    investment = len(top1) * 100
    rule_selected = top1[[decide_bet(odds, prob)[0] for odds, prob in zip(top1["win_odds"], top1["ranker_win_probability"])]]
    rule_investment = len(rule_selected) * 100
    return {"races": rows["race_id"].nunique(), "horses": len(rows), "brier": brier_score_loss(target, probability),
            "logloss": log_loss(target, np.clip(probability, 1e-6, 1 - 1e-6)), "auc": roc_auc_score(target, probability),
            "top1_hit_rate": top1["target"].mean(),
            "top3_hit_rate": sum(group["target"].any() for _, group in top3.groupby("race_id")) / rows["race_id"].nunique(),
            "top1_win_roi": top1["win_payout"].sum() / investment * 100 if investment else None,
            "top1_profit": top1["win_payout"].sum() - investment,
            "rule_bets": len(rule_selected),
            "rule_win_roi": rule_selected["win_payout"].sum() / rule_investment * 100 if rule_investment else None,
            "rule_profit": rule_selected["win_payout"].sum() - rule_investment}


def calibration_partition(frame: pd.DataFrame, prediction_month: pd.Timestamp, months: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    calibration_start = prediction_month - pd.DateOffset(months=months)
    calibration = frame[(frame["date"] >= calibration_start) & (frame["date"] < prediction_month)]
    preliminary_train = frame[frame["date"] < calibration_start]
    return preliminary_train, calibration


def monthly_walk_forward(frame: pd.DataFrame, features: list[str], months: list[pd.Timestamp], calibration_months: int) -> tuple[pd.DataFrame, list[dict]]:
    predictions, logs = [], []
    for prediction_month in months:
        prediction_end = prediction_month + pd.DateOffset(months=1)
        final_train = frame[frame["date"] < prediction_month]
        calibration_train, calibration = calibration_partition(frame, prediction_month, calibration_months)
        evaluation = frame[(frame["date"] >= prediction_month) & (frame["date"] < prediction_end)]
        calibration_scores = ranker_scores(calibration_train, calibration, features)
        temperature, calibration_brier = select_temperature(calibration, calibration_scores)
        scores = ranker_scores(final_train, evaluation, features)
        month_rows = add_probabilities(evaluation, scores, temperature, prediction_month - pd.Timedelta(days=1), "monthly_walk_forward")
        predictions.append(month_rows)
        logs.append({"prediction_month": prediction_month.strftime("%Y-%m"), "train_start": final_train["date"].min().strftime("%Y-%m-%d"),
                     "train_end": (prediction_month - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), "train_races": final_train["race_id"].nunique(),
                     "train_horses": len(final_train), "calibration_start": calibration["date"].min().strftime("%Y-%m-%d"),
                     "calibration_end": calibration["date"].max().strftime("%Y-%m-%d"), "calibration_races": calibration["race_id"].nunique(),
                     "temperature": temperature, "calibration_brier": calibration_brier, "evaluation_races": evaluation["race_id"].nunique(),
                     "evaluation_horses": len(evaluation)})
    return pd.concat(predictions, ignore_index=True), logs


def fixed_backtest(frame: pd.DataFrame, features: list[str], months: list[pd.Timestamp], calibration_months: int) -> pd.DataFrame:
    calibration_train, calibration = calibration_partition(frame, TEST_START, calibration_months)
    calibration_scores = ranker_scores(calibration_train, calibration, features)
    temperature, _ = select_temperature(calibration, calibration_scores)
    train = frame[frame["date"] < TEST_START]
    evaluation = frame[(frame["date"] >= TEST_START) & (frame["date"] < TEST_END)]
    scores = ranker_scores(train, evaluation, features)
    return add_probabilities(evaluation, scores, temperature, TEST_START - pd.Timedelta(days=1), "fixed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 12-month monthly Ranker walk-forward backtest")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retrain-months", type=int, default=1, help="Retraining cadence in months; monthly is the validated default.")
    parser.add_argument("--calibration-months", type=int, default=CALIBRATION_MONTHS)
    args = parser.parse_args()
    if args.retrain_months != 1:
        raise SystemExit("Only monthly retraining is implemented in this experiment. The setting is explicit for future cadence comparisons.")
    frame, features = load_frame(RANKER_MARGIN_CORRECTION_FEATURES)
    months = month_starts(TEST_START, TEST_END)
    walk_rows, training_log = monthly_walk_forward(frame, features, months, args.calibration_months)
    fixed_rows = fixed_backtest(frame, features, months, args.calibration_months)
    monthly_rows = []
    for mode, rows in (("monthly_walk_forward", walk_rows), ("fixed", fixed_rows)):
        for month, subset in rows.groupby(rows["date"].dt.strftime("%Y-%m")):
            monthly_rows.append({"mode": mode, "month": month, **metrics(subset)})
    comparison = [{"mode": "monthly_walk_forward", **metrics(walk_rows)}, {"mode": "fixed", **metrics(fixed_rows)}]
    args.out.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds", "popularity", "ranker_score", "ranker_win_probability", "prediction_rank", "win_payout", "model_train_end_date", "evaluation_mode"]
    write_csv(args.out / "walk_forward_predictions.csv", walk_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(args.out / "fixed_predictions.csv", fixed_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(args.out / "monthly_training_log.csv", training_log)
    write_csv(args.out / "monthly_results.csv", monthly_rows)
    write_csv(args.out / "fixed_vs_walk_forward_comparison.csv", comparison)
    metadata = {"test_start": TEST_START.strftime("%Y-%m-%d"), "test_end_exclusive": TEST_END.strftime("%Y-%m-%d"),
                "retrain_months": args.retrain_months, "calibration_months": args.calibration_months,
                "all_targets_above_8000000": bool((walk_rows["race_first_prize"] > 8_000_000).all()),
                "prediction_months": [month.strftime("%Y-%m") for month in months], "features": len(features)}
    (args.out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    walk, fixed = comparison
    lines = ["# Monthly Ranker Walk-Forward Backtest", "", "## Design", "- Final out-of-sample period: 2025-09-01 to 2026-08-31.",
             "- Monthly expanding-window retraining. Each forecast month uses only target races dated before that month.",
             "- Temperature: a preliminary Ranker trains before the preceding three calibration months; its out-of-time calibration scores select T. The final Ranker then retrains through the month immediately before prediction.",
             "- Low-prize races remain in precomputed historical features but are excluded from Ranker train/evaluation targets.", "", "## Annual Comparison",
             f"- Monthly Walk-Forward: Brier {walk['brier']:.6f}, LogLoss {walk['logloss']:.6f}, AUC {walk['auc']:.6f}, Top1 {walk['top1_hit_rate']:.2%}, Top3 {walk['top3_hit_rate']:.2%}, Top1 ROI {walk['top1_win_roi']:.2f}%.",
             f"- Fixed: Brier {fixed['brier']:.6f}, LogLoss {fixed['logloss']:.6f}, AUC {fixed['auc']:.6f}, Top1 {fixed['top1_hit_rate']:.2%}, Top3 {fixed['top3_hit_rate']:.2%}, Top1 ROI {fixed['top1_win_roi']:.2f}%.",
             "- Result: monthly retraining gives a small probability/ranking improvement, but does not improve Top1 win ROI in this final year. It is retained as the leakage-safe operational baseline, not as evidence of a profitable purchase rule.",
             "", "## Rule-Based Betting (src/betting_rules.py)",
             "- Rule: odds < 3.0 requires predicted probability >= 0.40; 5.0 <= odds < 20.0 is always bought; everything else is skipped.",
             f"- Monthly Walk-Forward: {walk['rule_bets']} bets, ROI {walk['rule_win_roi']:.2f}%, profit {walk['rule_profit']:.0f} yen (all Top1: ROI {walk['top1_win_roi']:.2f}%).",
             f"- Fixed: {fixed['rule_bets']} bets, ROI {fixed['rule_win_roi']:.2f}%, profit {fixed['rule_profit']:.0f} yen (all Top1: ROI {fixed['top1_win_roi']:.2f}%).",
             "", "## Outputs", "- `walk_forward_predictions.csv` is the standard input for the later purchase-condition search.",
             "- `monthly_training_log.csv` records each month’s train end, sample sizes, calibration window, and fixed temperature.",
             "- `monthly_results.csv` reports fixed and walk-forward metrics by month."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), **metadata, "walk_forward": walk, "fixed": fixed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

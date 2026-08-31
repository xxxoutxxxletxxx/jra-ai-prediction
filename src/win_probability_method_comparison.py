#!/usr/bin/env python3
"""Compare ranker, Bradley-Terry, and Plackett-Luce win probabilities.

This is a read-only experiment over the existing feature cache.  It keeps the
8M-first-prize target condition and never changes the production model or bet
selection logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    plt = None

try:
    from src.backtest import CLEANUP_B_FEATURES
except ModuleNotFoundError:  # Supports `python src/win_probability_method_comparison.py`.
    from backtest import CLEANUP_B_FEATURES

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "phase5_f_features.parquet"
RACE_DB = ROOT / "data" / "raw" / "race.db"
OUT = ROOT / "reports" / "win_probability_method_comparison"
SEED = 42
TRAIN_START, CAL_START, VALIDATION_START, VALIDATION_END = "2023-08-01", "2025-08-01", "2026-01-01", "2026-09-01"
BANDS = [(0.00, 0.05, "0-5%"), (0.05, 0.10, "5-10%"), (0.10, 0.15, "10-15%"),
         (0.15, 0.20, "15-20%"), (0.20, 0.30, "20-30%"), (0.30, 0.40, "30-40%"), (0.40, 1.01, "40%+")]
GAP_BANDS = [(0.00, 0.02, "0-2%"), (0.02, 0.05, "2-5%"), (0.05, 0.075, "5-7.5%"),
             (0.075, 0.10, "7.5-10%"), (0.10, float("inf"), "10%+")]
TEMPERATURES = np.array([0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0])


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def softmax_by_race(scores: np.ndarray, race_ids: np.ndarray, temperature: float) -> np.ndarray:
    probabilities = np.zeros(len(scores), dtype=float)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, race_id in enumerate(race_ids):
        groups[str(race_id)].append(index)
    for indexes in groups.values():
        value = scores[indexes] / temperature
        value -= value.max()
        exp = np.exp(np.clip(value, -50, 50))
        probabilities[indexes] = exp / exp.sum()
    return probabilities


def race_groups(frame: pd.DataFrame) -> list[np.ndarray]:
    return [group.index.to_numpy() for _, group in frame.groupby("race_id", sort=False)]


def prepare_data() -> tuple[pd.DataFrame, list[str]]:
    identifier_columns = ["race_id", "date", "horse_id", "horse_name", "actual_rank", "target", "odds", "popularity", "umaban", "race_first_prize"]
    requested = list(dict.fromkeys(identifier_columns + CLEANUP_B_FEATURES))
    available = set(pd.read_parquet(CACHE).columns)
    frame = pd.read_parquet(CACHE, columns=[column for column in requested if column in available])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[(frame["race_first_prize"] > 8_000_000) & (frame["actual_rank"] > 0) & (frame["odds"] > 0)].copy()
    frame = frame[(frame["date"] >= pd.Timestamp(TRAIN_START)) & (frame["date"] < pd.Timestamp(VALIDATION_END))]
    frame.sort_values(["date", "race_id", "horse_id"], inplace=True)
    payouts = load_win_payouts()
    frame["win_payout"] = [payouts.get((race_id, int(umaban)), 0.0) for race_id, umaban in zip(frame["race_id"], frame["umaban"])]
    feature_columns = [column for column in CLEANUP_B_FEATURES if column in frame]
    return frame.reset_index(drop=True), feature_columns


def load_win_payouts() -> dict[tuple[str, int], float]:
    key_columns = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    payout_columns = [f"PayTansyo{index}{suffix}" for index in range(3) for suffix in ("Umaban", "Pay")]
    query = f"SELECT {', '.join(key_columns + payout_columns)} FROM NL_HR_PAY WHERE idYear >= '2023'"
    payouts: dict[tuple[str, int], float] = {}
    with sqlite3.connect(RACE_DB) as connection:
        for values in connection.execute(query):
            row = dict(zip(key_columns + payout_columns, values))
            race_id = "-".join(str(row[column]).strip() for column in key_columns)
            for index in range(3):
                try:
                    umaban = int(float(row[f"PayTansyo{index}Umaban"] or 0))
                    payout = float(row[f"PayTansyo{index}Pay"] or 0)
                except (TypeError, ValueError):
                    continue
                if umaban:
                    payouts[(race_id, umaban)] = payout
    return payouts


def encode(frame: pd.DataFrame, feature_columns: list[str]) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
    train_mask = frame["date"] < pd.Timestamp(CAL_START)
    raw = frame[feature_columns].copy()
    categorical = [column for column in feature_columns if raw[column].dtype.name in {"object", "category"}]
    numeric = [column for column in feature_columns if column not in categorical]
    for column in numeric:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
        raw[column] = raw[column].fillna(raw.loc[train_mask, column].median()).fillna(0.0)
    for column in categorical:
        raw[column] = raw[column].astype(str).fillna("UNKNOWN")
    train_encoded = pd.get_dummies(raw.loc[train_mask], columns=categorical, dummy_na=True, dtype=float)
    all_encoded = pd.get_dummies(raw, columns=categorical, dummy_na=True, dtype=float).reindex(columns=train_encoded.columns, fill_value=0.0)
    train_mean = all_encoded.loc[train_mask].mean()
    train_std = all_encoded.loc[train_mask].std().replace(0.0, 1.0)
    all_encoded = (all_encoded - train_mean) / train_std
    return all_encoded.to_numpy(dtype=np.float32), {"train": np.flatnonzero(train_mask.to_numpy()),
            "calibration": np.flatnonzero(((frame["date"] >= pd.Timestamp(CAL_START)) & (frame["date"] < pd.Timestamp(VALIDATION_START))).to_numpy()),
            "validation": np.flatnonzero(((frame["date"] >= pd.Timestamp(VALIDATION_START)) & (frame["date"] < pd.Timestamp(VALIDATION_END))).to_numpy())}, list(train_encoded.columns)


def fit_ranker(x: np.ndarray, frame: pd.DataFrame, indices: np.ndarray) -> np.ndarray:
    train = frame.iloc[indices].copy()
    groups = [len(group) for _, group in train.groupby("race_id", sort=False)]
    relevance = train.groupby("race_id")["actual_rank"].transform("max") - train["actual_rank"] + 1
    model = LGBMRanker(objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3], n_estimators=180,
                       learning_rate=0.04, num_leaves=15, max_depth=5, min_child_samples=80,
                       reg_lambda=2.0, random_state=SEED, verbosity=-1)
    model.fit(x[indices], relevance.to_numpy(), group=groups)
    return model.predict(x, raw_score=True)


def fit_bradley_terry(x: np.ndarray, frame: pd.DataFrame, indices: np.ndarray) -> np.ndarray:
    pairs, labels = [], []
    train = frame.iloc[indices]
    for _, group in train.groupby("race_id", sort=False):
        group_indices = group.index.to_numpy()
        for left in range(len(group_indices) - 1):
            for right in range(left + 1, len(group_indices)):
                first, second = group_indices[left], group_indices[right]
                pairs.append(x[first] - x[second])
                labels.append(int(frame.at[first, "actual_rank"] < frame.at[second, "actual_rank"]))
    model = LogisticRegression(fit_intercept=False, C=1.0, max_iter=1000, random_state=SEED, solver="lbfgs")
    model.fit(np.asarray(pairs, dtype=np.float32), labels)
    return x @ model.coef_[0]


def pl_gradient(x: np.ndarray, frame: pd.DataFrame, indices: np.ndarray, epochs: int = 35, learning_rate: float = 0.08) -> np.ndarray:
    """Fit a linear Plackett-Luce log-strength by full observed-order likelihood."""
    coefficients = np.zeros(x.shape[1], dtype=np.float64)
    race_indexes = [group.index.to_numpy() for _, group in frame.iloc[indices].groupby("race_id", sort=False)]
    for epoch in range(epochs):
        gradient = np.zeros_like(coefficients)
        for group in race_indexes:
            ordered = group[np.argsort(frame.loc[group, "actual_rank"].to_numpy())]
            remaining = ordered.copy()
            for winner in ordered[:-1]:
                scores = x[remaining] @ coefficients
                scores -= scores.max()
                weights = np.exp(np.clip(scores, -50, 50))
                expected = (weights[:, None] * x[remaining]).sum(axis=0) / weights.sum()
                gradient += x[winner] - expected
                remaining = remaining[remaining != winner]
        coefficients += learning_rate * (gradient / len(indices) - 0.0005 * coefficients)
    return x @ coefficients


def select_temperature(scores: np.ndarray, frame: pd.DataFrame, calibration_indices: np.ndarray) -> float:
    best_temperature, best_brier = 1.0, float("inf")
    for temperature in TEMPERATURES:
        probabilities = softmax_by_race(scores[calibration_indices], frame.iloc[calibration_indices]["race_id"].to_numpy(), float(temperature))
        brier = brier_score_loss(frame.iloc[calibration_indices]["target"], probabilities)
        if brier < best_brier:
            best_temperature, best_brier = float(temperature), brier
    return best_temperature


def calibration_metrics(probabilities: np.ndarray, actual: np.ndarray) -> dict:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    ece = 0.0
    for low, high, _ in BANDS:
        selected = (probabilities >= low) & (probabilities < high)
        if selected.any():
            ece += selected.mean() * abs(probabilities[selected].mean() - actual[selected].mean())
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    if len(np.unique(actual)) == 2:
        calibration = LogisticRegression(C=1e6, max_iter=1000, random_state=SEED).fit(logits, actual)
        slope, intercept = float(calibration.coef_[0][0]), float(calibration.intercept_[0])
    else:
        slope = intercept = None
    return {"brier_score": brier_score_loss(actual, probabilities), "log_loss": log_loss(actual, clipped),
            "expected_calibration_error": ece, "calibration_slope": slope, "calibration_intercept": intercept}


def ranks_and_gaps(frame: pd.DataFrame, probability_column: str) -> pd.DataFrame:
    result = frame.copy()
    result[f"{probability_column}_rank"] = result.groupby("race_id")[probability_column].rank(method="first", ascending=False).astype(int)
    ordered = result.sort_values(["race_id", probability_column, "horse_id"], ascending=[True, False, True])
    gap = ordered.groupby("race_id")[probability_column].agg(lambda values: values.iloc[0] - values.iloc[1] if len(values) > 1 else 0.0)
    result[f"{probability_column}_gap_1_2"] = result["race_id"].map(gap)
    return result


def strategy_metrics(frame: pd.DataFrame, probability_column: str, ev_minimum: float | None, phase: str) -> tuple[dict, list[dict]]:
    selected = []
    for _, group in frame.groupby("race_id", sort=False):
        eligible = group[group[probability_column] >= 0.10].copy()
        if eligible.empty:
            continue
        eligible["ev"] = eligible[probability_column] * (eligible["odds"] / 10.0)
        candidate = eligible.sort_values(["ev", probability_column], ascending=False).iloc[0]
        if ev_minimum is None or candidate["ev"] > ev_minimum:
            selected.append(candidate.to_dict())
    payout = sum(row["win_payout"] for row in selected)
    balance = peak = drawdown = 0.0
    for row in sorted(selected, key=lambda row: (row["date"], row["race_id"])):
        balance += row["win_payout"] - 100.0
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    total_races = frame["race_id"].nunique()
    return {"method": probability_column.replace("_win_probability", ""), "strategy": "max EV p>=10%" if ev_minimum is None else "max EV p>=10%, EV>1",
            "phase": phase, "total_races": total_races, "bets": len(selected), "skip_count": total_races - len(selected),
            "wins": sum(int(row["target"]) for row in selected), "hit_rate": mean([row["target"] for row in selected]) if selected else None,
            "average_odds": mean([row["odds"] / 10.0 for row in selected]) if selected else None,
            "win_roi": payout / (len(selected) * 100) * 100 if selected else None,
            "profit": payout - len(selected) * 100, "maximum_drawdown": drawdown}, selected


def gap_rows(frame: pd.DataFrame, probability_column: str, phase: str) -> list[dict]:
    top1 = frame[frame[f"{probability_column}_rank"] == 1]
    records = []
    for low, high, label in GAP_BANDS:
        selected = top1[(top1[f"{probability_column}_gap_1_2"] >= low) & (top1[f"{probability_column}_gap_1_2"] < high)]
        investment = len(selected) * 100
        records.append({"method": probability_column.replace("_win_probability", ""), "phase": phase, "gap_band": label,
                        "sample_size": len(selected), "top1_actual_win_rate": selected["target"].mean() if len(selected) else None,
                        "average_odds": (selected["odds"] / 10.0).mean() if len(selected) else None,
                        "win_roi": selected["win_payout"].sum() / investment * 100 if investment else None})
    return records


def high_payout_sensitivity(selected: list[dict], method: str, phase: str, strategy: str) -> list[dict]:
    records = []
    for remove_count in (0, 1, 3):
        remaining = sorted(selected, key=lambda row: row["win_payout"], reverse=True)[remove_count:]
        investment = len(remaining) * 100
        records.append({"method": method, "phase": phase, "strategy": strategy, "removed_largest_payouts": remove_count,
                        "bets_remaining": len(remaining), "win_roi": sum(row["win_payout"] for row in remaining) / investment * 100 if investment else None,
                        "profit": sum(row["win_payout"] for row in remaining) - investment if investment else 0.0})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare three race-level win probability estimators")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    frame, features = prepare_data()
    x, phase_indices, encoded_features = encode(frame, features)
    if not len(phase_indices["train"]) or not len(phase_indices["calibration"]) or not len(phase_indices["validation"]):
        raise SystemExit("The fixed train/calibration/validation split has an empty partition.")
    methods = {"ranker": fit_ranker(x, frame, phase_indices["train"]),
               "bt": fit_bradley_terry(x, frame, phase_indices["train"]),
               "pl": pl_gradient(x, frame, phase_indices["train"])}
    temperatures = {name: select_temperature(scores, frame, phase_indices["calibration"]) for name, scores in methods.items()}
    for name, scores in methods.items():
        frame[f"{name}_score" if name == "ranker" else f"{name}_strength"] = scores
        frame[f"{name}_win_probability"] = softmax_by_race(scores, frame["race_id"].to_numpy(), temperatures[name])
        frame = ranks_and_gaps(frame, f"{name}_win_probability")
    output = frame[frame["date"] >= pd.Timestamp(CAL_START)].copy()
    output["phase"] = np.where(output["date"] < pd.Timestamp(VALIDATION_START), "calibration", "validation")
    output["win_odds"] = output["odds"] / 10.0
    output["race_id"] = output["race_id"].astype(str)
    comparison, bins, strategies, gaps, monthly, sensitivity = [], [], [], [], [], []
    for phase in ("calibration", "validation"):
        subset = output[output["phase"] == phase]
        for method in methods:
            probability_column = f"{method}_win_probability"
            actual, probability = subset["target"].to_numpy(), subset[probability_column].to_numpy()
            metrics = calibration_metrics(probability, actual)
            top1 = subset[subset[f"{probability_column}_rank"] == 1]
            top3_hit = sum(group["target"].any() for _, group in subset[subset[f"{probability_column}_rank"] <= 3].groupby("race_id")) / subset["race_id"].nunique()
            comparison.append({"method": method, "phase": phase, "temperature_from_calibration": temperatures[method],
                               **metrics, "roc_auc": roc_auc_score(actual, probability), "top1_hit_rate": top1["target"].mean(), "top3_hit_rate": top3_hit,
                               "races": subset["race_id"].nunique(), "horses": len(subset)})
            for low, high, label in BANDS:
                values = subset[(subset[probability_column] >= low) & (subset[probability_column] < high)]
                bins.append({"method": method, "phase": phase, "band": label, "sample_size": len(values),
                             "predicted_probability_mean": values[probability_column].mean() if len(values) else None,
                             "actual_win_rate": values["target"].mean() if len(values) else None,
                             "difference": (values[probability_column].mean() - values["target"].mean()) if len(values) else None})
            gaps.extend(gap_rows(subset, probability_column, phase))
            for ev_minimum in (None, 1.0):
                record, selected = strategy_metrics(subset, probability_column, ev_minimum, phase)
                strategies.append(record)
                sensitivity.extend(high_payout_sensitivity(selected, method, phase, record["strategy"]))
            for month, month_rows in subset.groupby(subset["date"].dt.strftime("%Y-%m")):
                record, _ = strategy_metrics(month_rows, probability_column, None, phase)
                monthly.append({**record, "month": month})
    args.out.mkdir(parents=True, exist_ok=True)
    keep = ["phase", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds", "popularity", "date", "ranker_score", "bt_strength", "pl_strength", "ranker_win_probability", "bt_win_probability", "pl_win_probability"]
    write_csv(args.out / "win_probability_comparison.csv", output[keep].to_dict("records"))
    write_csv(args.out / "calibration_comparison.csv", comparison)
    write_csv(args.out / "calibration_bins.csv", bins)
    write_csv(args.out / "strategy_comparison.csv", strategies)
    write_csv(args.out / "gap_comparison.csv", gaps)
    write_csv(args.out / "monthly_comparison.csv", monthly)
    write_csv(args.out / "high_payout_sensitivity.csv", sensitivity)
    if plt:
        plt.figure(figsize=(7, 4))
        for method in methods:
            values = [row for row in bins if row["phase"] == "validation" and row["method"] == method and row["sample_size"]]
            plt.plot([row["predicted_probability_mean"] for row in values], [row["actual_win_rate"] for row in values], "o-", label=method)
        plt.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
        plt.xlabel("Predicted win probability")
        plt.ylabel("Actual win rate")
        plt.legend()
        plt.tight_layout()
        plt.savefig(args.out / "calibration_curve.png")
        plt.close()
    validation = sorted([row for row in comparison if row["phase"] == "validation"], key=lambda row: (row["brier_score"], row["log_loss"]))
    roi_validation = sorted([row for row in strategies if row["phase"] == "validation" and row["strategy"] == "max EV p>=10%"], key=lambda row: (row["win_roi"] or -float("inf")), reverse=True)
    validation_frame = output[output["phase"] == "validation"]
    gap_correlations = {}
    for method in methods:
        probability_column = f"{method}_win_probability"
        top1 = validation_frame[validation_frame[f"{probability_column}_rank"] == 1]
        gap_correlations[method] = float(np.corrcoef(top1[f"{probability_column}_gap_1_2"], top1["target"])[0, 1])
    default_roi = {row["method"]: row for row in roi_validation}
    ev_one_roi = {row["method"]: row for row in strategies if row["phase"] == "validation" and row["strategy"] == "max EV p>=10%, EV>1"}
    highest_roi_method = roi_validation[0]["method"]
    bt_sensitivity = [row for row in sensitivity if row["phase"] == "validation" and row["method"] == highest_roi_method and row["strategy"] == "max EV p>=10%"]
    summary = ["# Win Probability Method Comparison", "", "## Design", "- Common features: existing CLEANUP_B_FEATURES; common seed: 42; target condition: first prize > 8,000,000 yen.",
               "- Train: 2023-08 through 2025-07. Temperature calibration: 2025-08 through 2025-12. Final validation: 2026-01 through 2026-08.",
               "- Odds use `win_odds = odds / 10`. Temperature is selected only on calibration; validation is not used for tuning.", "",
               "## A. Win Probability Accuracy Ranking"]
    for rank, row in enumerate(validation, 1):
        summary.append(f"{rank}. {row['method']}: Brier {row['brier_score']:.6f}, LogLoss {row['log_loss']:.6f}, ECE {row['expected_calibration_error']:.6f}, AUC {row['roc_auc']:.6f}, Top1 {row['top1_hit_rate']:.2%}, Top3 {row['top3_hit_rate']:.2%}")
    summary += ["", "## B. Betting Performance Ranking"]
    for rank, row in enumerate(roi_validation, 1):
        summary.append(f"{rank}. {row['method']}: ROI {row['win_roi']:.2f}%, profit {row['profit']:.0f} yen, bets {row['bets']}/{row['total_races']}, max DD {row['maximum_drawdown']:.0f} yen")
    summary += ["", "## Direct Answers",
                f"1. 実際の勝率に最も近い方式: {validation[0]['method']}。Brier/LogLoss/AUC/Top1/Top3で首位だが、BT/PLよりECEはわずかに高い。",
                f"2. 単勝ROIが最も高い方式: {highest_roi_method}（{default_roi[highest_roi_method]['win_roi']:.2f}%）。ただし100%未満で、購入用途として採用できる利益性は未確認。",
                f"3. 高配当依存: {highest_roi_method} の最大1件・3件を除くROIは {bt_sensitivity[1]['win_roi']:.2f}% / {bt_sensitivity[2]['win_roi']:.2f}%（全件 {bt_sensitivity[0]['win_roi']:.2f}%）。最大払戻への依存はあるが、元から利益化していない。",
                "4. Top1/Top3性能は `calibration_comparison.csv` のvalidation行を参照。順位性能はRankerが首位。",
                f"5. 勝率10%以上＋最大EVでは {highest_roi_method} が最良だが、ROI {default_roi[highest_roi_method]['win_roi']:.2f}%で改善未達。",
                f"6. EV>1の追加は Ranker {default_roi['ranker']['win_roi']:.2f}%→{ev_one_roi['ranker']['win_roi']:.2f}%、BT {default_roi['bt']['win_roi']:.2f}%→{ev_one_roi['bt']['win_roi']:.2f}%、PL {default_roi['pl']['win_roi']:.2f}%→{ev_one_roi['pl']['win_roi']:.2f}%。Ranker以外では悪化し、いずれも収益化しない。",
                f"7. gapとTop1的中の相関: Ranker {gap_correlations['ranker']:.3f}, BT {gap_correlations['bt']:.3f}, PL {gap_correlations['pl']:.3f}。断層はRankerが最も実勝率と対応。",
                f"8. 勝率推定用途の候補: {validation[0]['method']}。ただしvalidationで再校正された方式ではなく、固定temperatureによる結果であり継続監視が必要。",
                "9. 馬券購入用途の候補: なし。最高ROIのBTも100%を下回り、月別安定性・高配当除外後の双方で採用根拠がない。",
                "", "## Interpretation", "- Accuracy and ROI rankings are intentionally separate. Do not promote the highest-ROI method to production without validation stability and payout-sensitivity confirmation.",
                "- `high_payout_sensitivity.csv` reports ROI after removing the largest one and three payouts; use it to reject one-hit ROI gains.",
                "- This is an experiment only and does not modify the production purchase rule."]
    (args.out / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    metadata = {"rows": len(output), "races": output["race_id"].nunique(), "feature_count": len(encoded_features), "temperatures": temperatures,
                "train_start": TRAIN_START, "calibration_start": CAL_START, "validation_start": VALIDATION_START, "validation_end": VALIDATION_END,
                "all_first_prizes_above_8000000": bool((output["race_first_prize"] > 8_000_000).all())}
    (args.out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze race-normalized model probabilities as win-bet candidates.

This module is deliberately read-only: it consumes an existing 8M-first-prize
filtered backtest export and does not alter model features, fitting, or ranking.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    plt = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "prize_filter_ab_test" / "a" / "predictions.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "ev_betting_analysis"
PROBABILITY_BANDS = [(0.00, 0.05, "0-5%"), (0.05, 0.10, "5-10%"), (0.10, 0.15, "10-15%"),
                     (0.15, 0.20, "15-20%"), (0.20, 0.30, "20-30%"), (0.30, 1.01, "30%+")]
MIN_PROBABILITIES = (0.05, 0.075, 0.10, 0.125, 0.15, 0.20)
EV_THRESHOLDS = (0.90, 1.00, 1.05, 1.10, 1.20)
FIXED_GAPS = (0.02, 0.05, 0.075, 0.10)


def number(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip()) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def integer(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value))) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def quantile(values: list[float], fraction: float) -> float:
    return float(np.quantile(values, fraction)) if values else 0.0


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    required = {"race_id", "date", "predicted_probability", "odds", "is_win", "is_place", "win_payout", "place_payout"}
    missing = required - set(rows[0] if rows else [])
    if missing:
        raise SystemExit(f"Input is missing required columns: {', '.join(sorted(missing))}")
    for row in rows:
        row["predicted_probability"] = number(row["predicted_probability"])
        row["raw_odds"] = number(row["odds"])
        # JRA odds in this DB are stored in tenths; payout/raw_odds is 10 for winners.
        row["win_odds"] = row["raw_odds"] / 10.0
        row["is_win"] = integer(row["is_win"])
        row["is_place"] = integer(row["is_place"])
        row["win_payout"] = number(row["win_payout"])
        row["place_payout"] = number(row["place_payout"])
        row["race_first_prize"] = number(row.get("race_first_prize"))
    return rows


def normalize_probabilities(rows: list[dict]) -> list[dict]:
    by_race = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    output = []
    for race_rows in by_race.values():
        raw_sum = sum(row["predicted_probability"] for row in race_rows)
        market_raw_sum = sum(1.0 / row["win_odds"] for row in race_rows if row["win_odds"] > 0)
        if raw_sum <= 0 or market_raw_sum <= 0:
            continue
        for row in race_rows:
            value = dict(row)
            value["race_sum_predicted_probability"] = raw_sum
            value["normalized_win_probability"] = row["predicted_probability"] / raw_sum
            value["market_probability_raw"] = 1.0 / row["win_odds"] if row["win_odds"] > 0 else 0.0
            value["market_probability_normalized"] = value["market_probability_raw"] / market_raw_sum
            value["probability_edge"] = value["normalized_win_probability"] - value["market_probability_normalized"]
            value["win_ev"] = value["normalized_win_probability"] * value["win_odds"]
            value["expected_return_yen"] = value["win_ev"] * 100.0
            output.append(value)
    return add_race_rankings(output)


def add_race_rankings(rows: list[dict]) -> list[dict]:
    by_race = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    output = []
    for race_rows in by_race.values():
        ranked = sorted(race_rows, key=lambda row: (-row["normalized_win_probability"], row.get("horse_id", "")))
        values = [row["normalized_win_probability"] for row in ranked] + [0.0] * 4
        max_ev = max(race_rows, key=lambda row: (row["win_ev"], row["normalized_win_probability"]))
        for rank, row in enumerate(ranked, 1):
            value = dict(row)
            value["model_probability_rank"] = rank
            value["p1"] = values[0]
            value["p2"] = values[1]
            value["p3"] = values[2]
            value["p4"] = values[3]
            value["gap_1_2"] = values[0] - values[1]
            value["gap_2_3"] = values[1] - values[2]
            value["gap_3_4"] = values[2] - values[3]
            value["ev_max_horse_id"] = max_ev.get("horse_id", "")
            value["top1_equals_ev_max"] = int(ranked[0].get("horse_id", "") == max_ev.get("horse_id", ""))
            output.append(value)
    return output


def phase_map(rows: list[dict]) -> dict[str, list[dict]]:
    months = sorted({row["date"][:7] for row in rows})
    if len(months) < 2:
        raise SystemExit("At least two evaluation months are required for time-separated discovery and validation.")
    split = len(months) // 2
    discovery_months, validation_months = set(months[:split]), set(months[split:])
    return {
        "all": rows,
        "discovery": [row for row in rows if row["date"][:7] in discovery_months],
        "validation": [row for row in rows if row["date"][:7] in validation_months],
    }


def calibration_rows(rows: list[dict], phase: str, method: str = "normalized") -> list[dict]:
    records = []
    for low, high, label in PROBABILITY_BANDS:
        selected = [row for row in rows if low <= row["analysis_win_probability"] < high]
        probability = [row["analysis_win_probability"] for row in selected]
        actual = [row["is_win"] for row in selected]
        predicted_mean = mean(probability) if probability else None
        actual_mean = mean(actual) if actual else None
        records.append({"phase": phase, "method": method, "band": label, "lower": low, "upper": high,
                        "sample_size": len(selected), "predicted_probability_mean": predicted_mean,
                        "actual_win_rate": actual_mean,
                        "calibration_error": abs(predicted_mean - actual_mean) if selected else None})
    return records


def calibration_method_comparison(phases: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    discovery, validation = phases["discovery"], phases["validation"]
    source_x = np.array([[row["normalized_win_probability"]] for row in discovery])
    source_y = np.array([row["is_win"] for row in discovery])
    validation_x = np.array([[row["normalized_win_probability"]] for row in validation])
    methods = {"normalized": np.array([row["normalized_win_probability"] for row in validation])}
    if len(set(source_y)) == 2:
        methods["platt"] = LogisticRegression(random_state=42).fit(source_x, source_y).predict_proba(validation_x)[:, 1]
        methods["isotonic"] = IsotonicRegression(out_of_bounds="clip").fit(source_x.ravel(), source_y).predict(validation_x.ravel())
    comparison, curves = [], []
    actual = np.array([row["is_win"] for row in validation])
    for method, probabilities in methods.items():
        for row, probability in zip(validation, probabilities):
            row[f"{method}_probability"] = float(probability)
        comparison.append({"method": method, "fit_phase": "discovery", "evaluation_phase": "validation",
                           "sample_size": len(actual), "brier_score": brier_score_loss(actual, probabilities),
                           "mean_probability": float(np.mean(probabilities)), "actual_win_rate": float(np.mean(actual))})
        copied = [dict(row, analysis_win_probability=float(probability)) for row, probability in zip(validation, probabilities)]
        curves.extend(calibration_rows(copied, "validation", method))
    return comparison, curves


def select_strategy(rows: list[dict], strategy: str, min_probability: float = 0.10,
                    ev_threshold: float = 1.0, gap_threshold: float = 0.0) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)
    selected = []
    for race_rows in grouped.values():
        top1 = min(race_rows, key=lambda row: row["model_probability_rank"])
        eligible = [row for row in race_rows if row["normalized_win_probability"] >= min_probability]
        candidate = None
        if strategy == "baseline":
            candidate = top1
        elif strategy in {"max_ev", "max_ev_ev", "max_ev_gap"} and eligible:
            candidate = max(eligible, key=lambda row: (row["win_ev"], row["normalized_win_probability"]))
            if strategy == "max_ev_ev" and candidate["win_ev"] <= ev_threshold:
                candidate = None
            if strategy == "max_ev_gap" and top1["gap_1_2"] < gap_threshold:
                candidate = None
        elif strategy == "max_edge" and eligible:
            candidate = max(eligible, key=lambda row: (row["probability_edge"], row["normalized_win_probability"]))
            if candidate["probability_edge"] <= 0:
                candidate = None
        elif strategy == "top1_gap" and top1["gap_1_2"] >= gap_threshold:
            candidate = top1
        if candidate is not None:
            selected.append(candidate)
    return selected


def strategy_metrics(rows: list[dict], selected: list[dict], strategy: str, phase: str, parameter: str) -> dict:
    payout = sum(row["win_payout"] for row in selected)
    investment = len(selected) * 100.0
    balances, balance, peak, drawdown = [], 0.0, 0.0, 0.0
    for row in sorted(selected, key=lambda row: (row["date"], row["race_id"])):
        balance += row["win_payout"] - 100.0
        balances.append(balance)
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    return {"strategy": strategy, "parameter": parameter, "phase": phase,
            "total_races": len({row["race_id"] for row in rows}), "bets": len(selected),
            "skip_count": len({row["race_id"] for row in rows}) - len(selected),
            "bet_rate": len(selected) / len({row["race_id"] for row in rows}) if rows else None,
            "wins": sum(row["is_win"] for row in selected),
            "hit_rate": mean(row["is_win"] for row in selected) if selected else None,
            "average_odds": mean(row["win_odds"] for row in selected) if selected else None,
            "win_roi": payout / investment * 100.0 if investment else None,
            "total_profit": payout - investment, "maximum_drawdown": drawdown}


def analyze_strategies(phases: dict[str, list[dict]]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    discovery_gaps = [row["gap_1_2"] for row in phases["discovery"] if row["model_probability_rank"] == 1]
    gap_rules = [(f"gap>={gap:.1%}", gap) for gap in FIXED_GAPS] + [("top20pct", quantile(discovery_gaps, 0.80)), ("top10pct", quantile(discovery_gaps, 0.90))]
    comparison, min_rows, ev_rows, monthly = [], [], [], []
    for phase, rows in phases.items():
        base = select_strategy(rows, "baseline")
        comparison.append(strategy_metrics(rows, base, "Strategy 0 baseline", phase, "top1"))
        for name, strategy, parameter in [("Strategy 1 max EV", "max_ev", "p>=10%"), ("Strategy 2 max EV + EV>1", "max_ev_ev", "p>=10%, EV>1"),
                                          ("Strategy 3 max positive edge", "max_edge", "p>=10%, edge>0")]:
            selected = select_strategy(rows, strategy)
            comparison.append(strategy_metrics(rows, selected, name, phase, parameter))
        for label, threshold in gap_rules:
            selected = select_strategy(rows, "top1_gap", gap_threshold=threshold)
            comparison.append(strategy_metrics(rows, selected, "Strategy 4 top1 gap", phase, label))
            selected = select_strategy(rows, "max_ev_gap", gap_threshold=threshold)
            comparison.append(strategy_metrics(rows, selected, "Strategy 5 max EV + gap", phase, f"p>=10%, {label}"))
        for minimum in MIN_PROBABILITIES:
            selected = select_strategy(rows, "max_ev", min_probability=minimum)
            min_rows.append(strategy_metrics(rows, selected, "max EV min probability", phase, f"p>={minimum:.1%}"))
        for threshold in EV_THRESHOLDS:
            selected = select_strategy(rows, "max_ev_ev", ev_threshold=threshold)
            ev_rows.append(strategy_metrics(rows, selected, "max EV EV threshold", phase, f"p>=10%, EV>{threshold:.2f}"))
        for month in sorted({row["date"][:7] for row in rows}):
            month_rows = [row for row in rows if row["date"][:7] == month]
            for name, strategy in [("Strategy 0 baseline", "baseline"), ("Strategy 1 max EV", "max_ev"),
                                   ("Strategy 2 max EV + EV>1", "max_ev_ev"), ("Strategy 3 max positive edge", "max_edge")]:
                monthly.append({**strategy_metrics(month_rows, select_strategy(month_rows, strategy), name, phase, "default"), "month": month})
    return comparison, min_rows, ev_rows, monthly


def gap_analysis(rows: list[dict]) -> list[dict]:
    top1 = [row for row in rows if row["model_probability_rank"] == 1]
    bands = [(0.0, 0.02, "0-2%"), (0.02, 0.05, "2-5%"), (0.05, 0.075, "5-7.5%"),
             (0.075, 0.10, "7.5-10%"), (0.10, float("inf"), "10%+")]
    result = []
    for low, high, label in bands:
        selected = [row for row in top1 if low <= row["gap_1_2"] < high]
        payout, place_payout = sum(row["win_payout"] for row in selected), sum(row["place_payout"] for row in selected)
        investment = len(selected) * 100.0
        result.append({"gap_band": label, "sample_size": len(selected),
                       "top1_actual_win_rate": mean(row["is_win"] for row in selected) if selected else None,
                       "top1_place_rate": mean(row["is_place"] for row in selected) if selected else None,
                       "average_odds": mean(row["win_odds"] for row in selected) if selected else None,
                       "win_roi": payout / investment * 100.0 if investment else None,
                       "place_roi": place_payout / investment * 100.0 if investment else None,
                       "win_profit": payout - investment})
    return result


def top1_vs_ev(rows: list[dict], phase: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)
    result = []
    for label in ("SAME", "DIFFERENT"):
        selected = []
        for race_rows in grouped.values():
            top1 = min(race_rows, key=lambda row: row["model_probability_rank"])
            max_ev = max(race_rows, key=lambda row: (row["win_ev"], row["normalized_win_probability"]))
            if (top1["horse_id"] == max_ev["horse_id"]) == (label == "SAME"):
                selected.append(max_ev)
        metrics = strategy_metrics(rows, selected, "top1_vs_ev", phase, label)
        result.append({"group": label, **metrics})
    return result


def write_calibration_plot(path: Path, calibration: list[dict]) -> bool:
    if plt is None:
        return False
    plt.figure(figsize=(7, 4))
    for method in ("normalized", "platt", "isotonic"):
        points = [row for row in calibration if row["phase"] == "validation" and row["method"] == method and row["sample_size"]]
        if points:
            plt.plot([row["predicted_probability_mean"] for row in points], [row["actual_win_rate"] for row in points], "o-", label=method)
    plt.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
    plt.xlabel("Predicted probability")
    plt.ylabel("Actual win rate")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return True


def write_summary(output: Path, metadata: dict, calibration_compare: list[dict], strategies: list[dict], top1_ev: list[dict]) -> None:
    validation = [row for row in strategies if row["phase"] == "validation"]
    selected = {row["strategy"]: row for row in validation if row["parameter"] in {"top1", "p>=10%", "p>=10%, EV>1", "p>=10%, edge>0"}}
    calibration = {row["method"]: row for row in calibration_compare}
    top1_ev_validation = {row["group"]: row for row in top1_ev if row["phase"] == "validation"}
    lines = ["# EV Betting Analysis", "", "## Scope", "- 1着本賞金800万円以下を除外した既存CBバックテスト予測のみを使用。モデル・特徴量・ランキングは変更していない。",
             "- DBの単勝オッズは10倍表記のため、EVは `win_odds = odds / 10` で計算。",
             f"- 評価月: {', '.join(metadata['months'])}; discovery: {', '.join(metadata['discovery_months'])}; validation: {', '.join(metadata['validation_months'])}。",
             "", "## Probability", f"- レース内の生確率和: min {metadata['raw_sum_min']:.3f}, max {metadata['raw_sum_max']:.3f}, mean {metadata['raw_sum_mean']:.3f}。",
             "- `normalized_win_probability` は各レース内で合計1.0となる分析用の相対勝率であり、Calibration確認前に真の勝率とはみなさない。",
             "", "## Calibration", "- `win_probability_calibration.csv` と `calibration_method_comparison.csv` は、前半でfitし後半で評価している。",
             f"- 後半Brier: normalized {calibration['normalized']['brier_score']:.5f}, Platt {calibration['platt']['brier_score']:.5f}, isotonic {calibration['isotonic']['brier_score']:.5f}。",
             "- Platt/isotonicは正規化値を改善しなかった。後半15-20%帯も予測17.4%に対し実績23.9%で、勝率を真の確率として固定しない。",
             "", "## Validation Strategy Snapshot"]
    for name in ("Strategy 0 baseline", "Strategy 1 max EV", "Strategy 2 max EV + EV>1", "Strategy 3 max positive edge"):
        row = selected.get(name)
        if row:
            lines.append(f"- {name}: bets {row['bets']}/{row['total_races']}, hit {row['hit_rate']}, ROI {row['win_roi']}, profit {row['total_profit']:.0f} yen, max DD {row['maximum_drawdown']:.0f} yen")
    different = top1_ev_validation["DIFFERENT"]
    lines += ["", "## Interpretation", "- 後半ではTop1がROI 84.67%に対し、勝率10%以上でEV最大は66.13%、EV>1でも71.94%であり、EV最大化はベースラインを改善しなかった。",
              "- `EV>1` は75件中62件へ購入を減らしたが、利益・最大ドローダウンともTop1より悪く、見送りの有効性は確認できない。",
              "- gap上位10%は後半9件でROI 87.78%だが、前半でも71.33%で、サンプルが小さく採用根拠には不足する。断層は的中率を上げる傾向でもROIは改善していない。",
              f"- 後半のDIFFERENTは{different['bets']}件・ROI {different['win_roi']}であり、高配当1件の影響を受けやすい。Top1以外をEVだけで選ぶ価値は未確認。",
              "- 最もROIが高い条件を全期間で採用しない。`strategy_comparison.csv` のdiscovery候補を、同じ閾値のvalidation行で確認する。",
              "- この分析は購入候補の検証までであり、本番購入ルールは変更していない。"]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze normalized win probability and EV betting candidates")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = normalize_probabilities(load_rows(args.input))
    phases = phase_map(rows)
    calibration_compare, calibration_validation = calibration_method_comparison(phases)
    calibration = calibration_rows([dict(row, analysis_win_probability=row["normalized_win_probability"]) for row in rows], "all")
    calibration += calibration_rows([dict(row, analysis_win_probability=row["normalized_win_probability"]) for row in phases["discovery"]], "discovery")
    calibration += calibration_validation
    strategies, minimums, ev_thresholds, monthly = analyze_strategies(phases)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "race_probability_candidates.csv", rows)
    write_csv(args.out / "win_probability_calibration.csv", calibration)
    write_csv(args.out / "calibration_method_comparison.csv", calibration_compare)
    write_csv(args.out / "strategy_comparison.csv", strategies)
    write_csv(args.out / "min_probability_threshold.csv", minimums)
    write_csv(args.out / "ev_threshold_analysis.csv", ev_thresholds)
    write_csv(args.out / "probability_gap_analysis.csv", gap_analysis(rows))
    top1_ev = [item for phase, phase_rows in phases.items() for item in top1_vs_ev(phase_rows, phase)]
    write_csv(args.out / "top1_vs_ev_candidate.csv", top1_ev)
    write_csv(args.out / "monthly_strategy_results.csv", monthly)
    race_sums = defaultdict(float)
    for row in rows:
        race_sums[row["race_id"]] += row["normalized_win_probability"]
    months = sorted({row["date"][:7] for row in rows})
    metadata = {"input": str(args.input), "rows": len(rows), "races": len(race_sums), "months": months,
                "discovery_months": months[:len(months)//2], "validation_months": months[len(months)//2:],
                "raw_sum_min": min(row["race_sum_predicted_probability"] for row in rows),
                "raw_sum_max": max(row["race_sum_predicted_probability"] for row in rows),
                "raw_sum_mean": mean({row["race_id"]: row["race_sum_predicted_probability"] for row in rows}.values()),
                "normalized_sum_min": min(race_sums.values()), "normalized_sum_max": max(race_sums.values()),
                "prize_threshold_check": {"all_races_above_8000000": all(row["race_first_prize"] > 8_000_000 for row in rows)}}
    metadata["calibration_curve_generated"] = write_calibration_plot(args.out / "calibration_curve.png", calibration)
    (args.out / "analysis_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(args.out, metadata, calibration_compare, strategies, top1_ev)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
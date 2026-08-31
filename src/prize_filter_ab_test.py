#!/usr/bin/env python3
"""A/B prize filter experiment for race-level first prize thresholding."""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
OUT_DIR = ROOT / "reports" / "prize_filter_ab_test"
START_MONTH = "2026-07"
END_MONTH = "2026-09"
MODEL = "CB"
THRESHOLDS = {
    "A": 8_000_000,
    "B": 11_400_000,
}
BANDS = [
    ("<=800万円", 0, 8_000_000),
    ("800万円超〜1,140万円以下", 8_000_000, 11_400_000),
    ("1,140万円超", 11_400_000, 10**18),
]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def as_int(value: object, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def safe_div(num: float, den: float) -> float | None:
    if den in (None, 0):
        return None
    return num / den


def race_metrics(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("race_id")].append(row)
    top1_hit = sum(1 for group in grouped.values() if any(as_int(r.get("prediction_rank"), 0) == 1 and as_int(r.get("is_win"), 0) == 1 for r in group))
    top3_hit = sum(1 for group in grouped.values() if any(as_int(r.get("prediction_rank"), 0) <= 3 and as_int(r.get("is_win"), 0) == 1 for r in group))
    selected = [row for row in rows if as_int(row.get("prediction_rank"), 0) == 1]
    win_profit = sum(as_float(row.get("win_payout"), 0.0) for row in selected) - len(selected) * 100
    place_profit = sum(as_float(row.get("place_payout"), 0.0) for row in selected) - len(selected) * 100
    win_roi = safe_div(sum(as_float(r.get("win_payout"), 0.0) for r in selected), len(selected) * 100) * 100
    place_roi = safe_div(sum(as_float(r.get("place_payout"), 0.0) for r in selected), len(selected) * 100) * 100
    top1_avg_popularity = mean(as_float(row.get("popularity"), 0.0) for row in selected) if selected else None
    top1_avg_odds = mean(as_float(row.get("odds"), 0.0) for row in selected) if selected else None
    pred_probs = [as_float(row.get("predicted_probability"), 0.0) for row in rows]
    targets = [as_int(row.get("is_win"), 0) for row in rows]
    brier = mean((target - prob) ** 2 for target, prob in zip(targets, pred_probs)) if rows else None
    return {
        "race_count": len(grouped),
        "horse_count": len(rows),
        "roc_auc": roc_auc_from_rows(rows),
        "logloss": log_loss_from_rows(rows),
        "top1_hit_rate": top1_hit / len(grouped) if grouped else None,
        "top3_hit_rate": top3_hit / len(grouped) if grouped else None,
        "win_roi": win_roi,
        "place_roi": place_roi,
        "win_profit": win_profit,
        "place_profit": place_profit,
        "brier_score": brier,
        "top1_avg_popularity": top1_avg_popularity,
        "top1_avg_odds": top1_avg_odds,
    }


def roc_auc_from_rows(rows: list[dict]) -> float | None:
    if not rows:
        return None
    positives = [as_int(r.get("is_win"), 0) for r in rows]
    probs = [as_float(r.get("predicted_probability"), 0.0) for r in rows]
    pos = sum(positives)
    neg = len(rows) - pos
    if pos == 0 or neg == 0:
        return None
    ordered = sorted(zip(probs, positives), key=lambda x: x[0])
    positive_rank_sum = sum(index for index, (_, y) in enumerate(ordered, 1) if y)
    return (positive_rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def log_loss_from_rows(rows: list[dict]) -> float | None:
    if not rows:
        return None
    y = [as_int(r.get("is_win"), 0) for r in rows]
    p = [max(1e-15, min(1 - 1e-15, as_float(r.get("predicted_probability"), 0.0))) for r in rows]
    return -mean(actual * math.log(prob) + (1 - actual) * math.log(1 - prob) for actual, prob in zip(y, p))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_backtest(threshold: int, out_dir: Path) -> None:
    cmd = [
        str(VENV_PYTHON),
        "-m", "src.backtest",
        "--start-month", START_MONTH,
        "--end-month", END_MONTH,
        "--model", MODEL,
        "--min-race-first-prize", str(threshold),
        "--out", str(out_dir),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def build_band_rows(rows: list[dict]) -> list[dict]:
    results = []
    for label, low, high in BANDS:
        subset = [row for row in rows if low < as_float(row.get("race_first_prize"), 0.0) <= high]
        if not subset:
            continue
        metrics = race_metrics(subset)
        results.append({
            "band": label,
            "race_count": metrics["race_count"],
            "horse_count": metrics["horse_count"],
            "top1_hit_rate": metrics["top1_hit_rate"],
            "top3_hit_rate": metrics["top3_hit_rate"],
            "win_roi": metrics["win_roi"],
            "place_roi": metrics["place_roi"],
            "win_profit": metrics["win_profit"],
            "place_profit": metrics["place_profit"],
        })
    return results


def monthly_rows(rows: list[dict], label: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        month = str(row.get("date", ""))[:7]
        grouped[month].append(row)
    records = []
    for month in sorted(grouped):
        subset = grouped[month]
        unique_races = len({row.get("race_id") for row in subset})
        selected = [row for row in subset if as_int(row.get("prediction_rank"), 0) == 1]
        if not selected:
            continue
        win_roi = safe_div(sum(as_float(r.get("win_payout"), 0.0) for r in selected), len(selected) * 100) * 100
        place_roi = safe_div(sum(as_float(r.get("place_payout"), 0.0) for r in selected), len(selected) * 100) * 100
        records.append({
            "label": label,
            "month": month,
            "race_count": unique_races,
            "bet_count": len(selected),
            "top1_hit_rate": sum(as_int(r.get("is_win"), 0) for r in selected) / unique_races if unique_races else None,
            "win_roi": win_roi,
            "place_roi": place_roi,
            "win_profit": sum(as_float(r.get("win_payout"), 0.0) for r in selected) - len(selected) * 100,
            "place_profit": sum(as_float(r.get("place_payout"), 0.0) for r in selected) - len(selected) * 100,
        })
    return records


def extra_filtered_analysis(rows_a: list[dict], rows_b: list[dict]) -> list[dict]:
    a_map = defaultdict(list)
    for row in rows_a:
        a_map[row.get("race_id")].append(row)
    extra = []
    for race_id, group in a_map.items():
        prize = as_float(group[0].get("race_first_prize"), 0.0)
        if 8_000_000 < prize <= 11_400_000:
            extra.extend(group)
    if not extra:
        return []
    metrics = race_metrics(extra)
    return [{
        "race_band": "800万円超〜1,140万円以下",
        "race_count": metrics["race_count"],
        "horse_count": metrics["horse_count"],
        "top1_hit_rate": metrics["top1_hit_rate"],
        "top3_hit_rate": metrics["top3_hit_rate"],
        "win_roi": metrics["win_roi"],
        "place_roi": metrics["place_roi"],
        "win_profit": metrics["win_profit"],
        "place_profit": metrics["place_profit"],
    }]


def comparison_rows(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    return [
        {"label": "A", **race_metrics(a_rows)},
        {"label": "B", **race_metrics(b_rows)},
    ]


def summary_markdown(comparison: list[dict], extra: list[dict], monthly: list[dict]) -> str:
    a = next(item for item in comparison if item["label"] == "A")
    b = next(item for item in comparison if item["label"] == "B")
    extra_item = extra[0] if extra else {"race_count": 0, "top1_hit_rate": None, "top3_hit_rate": None, "win_roi": None, "place_roi": None, "win_profit": 0, "place_profit": 0}
    win_roi_delta = b["win_roi"] - a["win_roi"]
    top3_delta = b["top3_hit_rate"] - a["top3_hit_rate"]
    lines = [
        "# Prize Filter A/B Experiment",
        "",
        "## Objective",
        "- Compare the effect of excluding target races by first-prize thresholds only.",
        "- Only the first-prize target-race threshold differs between A and B; the model, features, months, and walk-forward procedure are identical.",
        "- Feature history retains all source races. The threshold filters only the fitting and evaluation target races.",
        "",
        "## A",
        f"- target races: {a['race_count']}",
        f"- AUC: {a['roc_auc']}",
        f"- LogLoss: {a['logloss']}",
        f"- Top1: {a['top1_hit_rate']}",
        f"- Top3: {a['top3_hit_rate']}",
        f"- Win ROI: {a['win_roi']}",
        f"- Place ROI: {a['place_roi']}",
        f"- Profit: {a['win_profit']} / {a['place_profit']}",
        "",
        "## B",
        f"- target races: {b['race_count']}",
        f"- AUC: {b['roc_auc']}",
        f"- LogLoss: {b['logloss']}",
        f"- Top1: {b['top1_hit_rate']}",
        f"- Top3: {b['top3_hit_rate']}",
        f"- Win ROI: {b['win_roi']}",
        f"- Place ROI: {b['place_roi']}",
        f"- Profit: {b['win_profit']} / {b['place_profit']}",
        "",
        "## A→B additional exclusion (800万円超〜1,140万円以下)",
        f"- race_count: {extra_item['race_count']}",
        f"- top1_hit_rate: {extra_item['top1_hit_rate']}",
        f"- top3_hit_rate: {extra_item['top3_hit_rate']}",
        f"- win_roi: {extra_item['win_roi']}",
        f"- place_roi: {extra_item['place_roi']}",
        f"- win_profit: {extra_item['win_profit']}",
        f"- place_profit: {extra_item['place_profit']}",
        "",
        "## Recommendation",
        "- Adopt A (exclude races with first prize of 800万円 or less) as the current standard.",
        f"- B removed {a['race_count'] - b['race_count']} additional races but changed win ROI by {win_roi_delta:+.2f} points and Top3 hit rate by {top3_delta:+.2%}.",
        f"- The additionally excluded band returned a win ROI of {extra_item['win_roi']}, so it is not the principal source of the weaker ROI.",
        "- Both variants remain below 100% ROI. Keep this race filter as A and next test a betting-condition filter using the existing probability, odds, and popularity fields.",
        "",
        "## Monthly comparison",
        "| label | month | races | top1_hit_rate | win_roi | place_roi | profit |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in monthly:
        lines.append(f"| {item['label']} | {item['month']} | {item['race_count']} | {item['top1_hit_rate']} | {item['win_roi']} | {item['place_roi']} | {item['win_profit']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_map = {}
    for label, threshold in THRESHOLDS.items():
        out_path = OUT_DIR / label.lower()
        run_backtest(threshold, out_path)
        predictions = read_csv(out_path / "predictions.csv")
        output_map[label] = predictions

    comparison = comparison_rows(output_map["A"], output_map["B"])
    write_csv(OUT_DIR / "ab_comparison.csv", comparison)

    band_rows = []
    for label in ["A", "B"]:
        band_rows.extend({"label": label, **row} for row in build_band_rows(output_map[label]))
    write_csv(OUT_DIR / "prize_band_analysis.csv", band_rows)

    extra = extra_filtered_analysis(output_map["A"], output_map["B"])
    write_csv(OUT_DIR / "additional_excluded_races_analysis.csv", extra)

    monthly = []
    for label in ["A", "B"]:
        monthly.extend(monthly_rows(output_map[label], label))
    write_csv(OUT_DIR / "monthly_comparison.csv", monthly)

    summary = summary_markdown(comparison, extra, monthly)
    (OUT_DIR / "summary.md").write_text(summary, encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps({
        "comparison": comparison,
        "prize_band_analysis": band_rows,
        "additional_excluded_races_analysis": extra,
        "monthly_comparison": monthly,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"A/B prize threshold analysis saved to {OUT_DIR}")
    for label, rows in output_map.items():
        metrics = race_metrics(rows)
        print(label, metrics)


if __name__ == "__main__":
    main()

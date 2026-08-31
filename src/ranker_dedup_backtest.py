#!/usr/bin/env python3
"""Full-year Ranker walk-forward backtest after removing the redundant near-run margin family.

Drops raw margin (last1_margin/last2_margin/last3_margin/best_margin_last3/mean_margin_last3/
weighted_margin_last3), last1-3_raw_performance, and every margin_x_* interaction, since these
duplicate the already class/pace/opponent-adjusted last1-3_adjusted_performance signal
(see reports/ranker_feature_audit/summary.md). Same monthly expanding-window design, calibration
window, and target filter as reports/ranker_walk_forward_12m so results are directly comparable.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import DEDUP_MARGIN_FEATURES
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf
    from backtest import DEDUP_MARGIN_FEATURES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_dedup_redesign"
BASELINE_PREDICTIONS = ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_baseline() -> pd.DataFrame:
    rows = pd.read_csv(BASELINE_PREDICTIONS)
    rows["date"] = pd.to_datetime(rows["date"])
    return rows


def monthly_metrics(variant: str, rows: pd.DataFrame) -> list[dict]:
    return [{"variant": variant, "month": month, **wf.metrics(subset)}
            for month, subset in rows.groupby(rows["date"].dt.strftime("%Y-%m"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deduplicated near-run performance feature set through the full-year Ranker walk-forward")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    frame, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    removed = sorted(set(baseline_features) - set(dedup_features))
    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    dedup_rows, training_log = wf.monthly_walk_forward(frame, dedup_features, months, wf.CALIBRATION_MONTHS)
    baseline_rows = load_baseline()
    comparison = [{"variant": "baseline_cleanup_b", "feature_count": len(baseline_features), **wf.metrics(baseline_rows)},
                  {"variant": "dedup_no_raw_margin", "feature_count": len(dedup_features), **wf.metrics(dedup_rows)}]
    monthly_rows = monthly_metrics("baseline_cleanup_b", baseline_rows) + monthly_metrics("dedup_no_raw_margin", dedup_rows)
    args.out.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds",
                      "popularity", "ranker_score", "ranker_win_probability", "prediction_rank", "win_payout",
                      "model_train_end_date", "evaluation_mode"]
    write_csv(args.out / "dedup_predictions.csv",
              dedup_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(args.out / "monthly_results.csv", monthly_rows)
    write_csv(args.out / "comparison.csv", comparison)
    write_csv(args.out / "removed_features.csv", [{"feature": feature} for feature in removed])
    (args.out / "monthly_training_log.csv").write_text("", encoding="utf-8")
    write_csv(args.out / "monthly_training_log.csv", training_log)
    baseline, dedup = comparison
    lines = ["# Ranker Dedup Redesign (Raw Margin Removed)", "",
             "## Change", f"- Removed {len(removed)} features that duplicate `last1-3_adjusted_performance`: raw margin values, `last1-3_raw_performance`, and every `margin_x_*` interaction.",
             "- Everything else (feature set, monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged from `reports/ranker_walk_forward_12m`.",
             "", "## Full-Year Comparison (2025-09 to 2026-08)",
             f"- Baseline (CLEANUP_B, {baseline['feature_count']} features): Brier {baseline['brier']:.6f}, LogLoss {baseline['logloss']:.6f}, AUC {baseline['auc']:.6f}, Top1 {baseline['top1_hit_rate']:.2%}, Top3 {baseline['top3_hit_rate']:.2%}, Top1 Win ROI {baseline['top1_win_roi']:.2f}%, Top1 profit {baseline['top1_profit']:.0f} yen.",
             f"- Dedup (raw margin removed, {dedup['feature_count']} features): Brier {dedup['brier']:.6f}, LogLoss {dedup['logloss']:.6f}, AUC {dedup['auc']:.6f}, Top1 {dedup['top1_hit_rate']:.2%}, Top3 {dedup['top3_hit_rate']:.2%}, Top1 Win ROI {dedup['top1_win_roi']:.2f}%, Top1 profit {dedup['top1_profit']:.0f} yen.",
             "", "## Removed Features"]
    lines += [f"- {feature}" for feature in removed]
    lines += ["", "## Outputs", "- `dedup_predictions.csv`: per-horse predictions from the dedup variant, same schema as `walk_forward_predictions.csv`.",
              "- `monthly_results.csv`: month-by-month metrics for both variants.", "- `comparison.csv`: full-year metrics for both variants."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), "removed_feature_count": len(removed), "baseline": baseline, "dedup": dedup}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

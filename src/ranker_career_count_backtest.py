#!/usr/bin/env python3
"""Full-year Ranker walk-forward backtest after dropping career_win_rate/career_races.

Continues the redesign started in ranker_dedup_backtest.py (raw margin removed). This
step additionally drops `career_win_rate` (a raw win-rate score) and `career_races`
(lifetime start count): the prize-based class score already carries an experience/level
signal, and the categorical class_label (NEWCOMER/MAIDEN/CLASS_1/.../G1) was removed from
feature generation entirely in src/backtest.py (race_conditions() still computes it
internally for the unrelated history-filter experiment, but it is no longer stored as a
model feature). Same monthly expanding-window design, calibration window, and target
filter as reports/ranker_walk_forward_12m so results are directly comparable.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import CAREER_COUNT_FEATURES, DEDUP_MARGIN_FEATURES
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf
    from backtest import CAREER_COUNT_FEATURES, DEDUP_MARGIN_FEATURES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_career_count_redesign"
BASELINE_PREDICTIONS = ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv"
DEDUP_PREDICTIONS = ROOT / "reports" / "ranker_dedup_redesign" / "dedup_predictions.csv"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_saved(path: Path) -> pd.DataFrame:
    rows = pd.read_csv(path)
    rows["date"] = pd.to_datetime(rows["date"])
    return rows


def monthly_metrics(variant: str, rows: pd.DataFrame) -> list[dict]:
    return [{"variant": variant, "month": month, **wf.metrics(subset)}
            for month, subset in rows.groupby(rows["date"].dt.strftime("%Y-%m"))]


def market_group_summary(rows: pd.DataFrame, label: str) -> list[dict]:
    top1 = rows[rows["prediction_rank"] == 1].copy()
    top1["market_group"] = pd.cut(top1["popularity"], bins=[0, 1, 3, 6, float("inf")],
                                  labels=["A_favorite", "B_2_3", "C_4_6", "D_7_plus"])
    out = []
    for name, group in top1.groupby("market_group", observed=True):
        out.append({"variant": label, "market_group": str(name), "races": len(group),
                    "predicted_win_probability": group["ranker_win_probability"].mean(),
                    "actual_win_rate": group["target"].mean(),
                    "win_roi": group["win_payout"].sum() / (len(group) * 100) * 100})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the career_win_rate/career_races-dropped feature set through the full-year Ranker walk-forward")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    frame, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    reduced_features = [feature for feature in dedup_features if feature not in CAREER_COUNT_FEATURES]
    removed = sorted(set(dedup_features) - set(reduced_features))
    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    reduced_rows, training_log = wf.monthly_walk_forward(frame, reduced_features, months, wf.CALIBRATION_MONTHS)
    baseline_rows = load_saved(BASELINE_PREDICTIONS)
    dedup_rows = load_saved(DEDUP_PREDICTIONS)
    comparison = [{"variant": "baseline_cleanup_b", "feature_count": len(baseline_features), **wf.metrics(baseline_rows)},
                  {"variant": "dedup_no_raw_margin", "feature_count": len(dedup_features), **wf.metrics(dedup_rows)},
                  {"variant": "no_career_win_rate_no_career_races", "feature_count": len(reduced_features), **wf.metrics(reduced_rows)}]
    monthly_rows = (monthly_metrics("baseline_cleanup_b", baseline_rows) + monthly_metrics("dedup_no_raw_margin", dedup_rows)
                    + monthly_metrics("no_career_win_rate_no_career_races", reduced_rows))
    market_rows = (market_group_summary(baseline_rows, "baseline_cleanup_b") + market_group_summary(dedup_rows, "dedup_no_raw_margin")
                   + market_group_summary(reduced_rows, "no_career_win_rate_no_career_races"))
    args.out.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds",
                      "popularity", "ranker_score", "ranker_win_probability", "prediction_rank", "win_payout",
                      "model_train_end_date", "evaluation_mode"]
    write_csv(args.out / "reduced_predictions.csv",
              reduced_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(args.out / "monthly_results.csv", monthly_rows)
    write_csv(args.out / "comparison.csv", comparison)
    write_csv(args.out / "market_disagreement_comparison.csv", market_rows)
    write_csv(args.out / "removed_features.csv", [{"feature": feature} for feature in removed])
    write_csv(args.out / "monthly_training_log.csv", training_log)
    baseline, dedup, reduced = comparison
    lines = ["# Ranker Career Win-Rate / Race-Count Redesign", "",
             "## Change", f"- Dropped `career_win_rate` and `career_races` on top of the raw-margin dedup ({len(removed)} feature(s) removed here).",
             "- The categorical class_label (`race_class_label`, `last1-3_race_class`) is now removed from feature generation entirely in `src/backtest.py`; it was already absent from this Ranker feature set, so this run confirms no regression from that removal, not a new ablation.",
             "- Everything else (monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged.",
             "", "## Full-Year Comparison (2025-09 to 2026-08)",
             f"- Baseline (CLEANUP_B, {baseline['feature_count']} features): Brier {baseline['brier']:.6f}, AUC {baseline['auc']:.6f}, Top1 {baseline['top1_hit_rate']:.2%}, Top3 {baseline['top3_hit_rate']:.2%}, Top1 Win ROI {baseline['top1_win_roi']:.2f}%, profit {baseline['top1_profit']:.0f} yen.",
             f"- Dedup (raw margin removed, {dedup['feature_count']} features): Brier {dedup['brier']:.6f}, AUC {dedup['auc']:.6f}, Top1 {dedup['top1_hit_rate']:.2%}, Top3 {dedup['top3_hit_rate']:.2%}, Top1 Win ROI {dedup['top1_win_roi']:.2f}%, profit {dedup['top1_profit']:.0f} yen.",
             f"- No career_win_rate/career_races ({reduced['feature_count']} features): Brier {reduced['brier']:.6f}, AUC {reduced['auc']:.6f}, Top1 {reduced['top1_hit_rate']:.2%}, Top3 {reduced['top3_hit_rate']:.2%}, Top1 Win ROI {reduced['top1_win_roi']:.2f}%, profit {reduced['top1_profit']:.0f} yen.",
             "", "## Removed In This Step", *[f"- {feature}" for feature in removed],
             "", "## Outputs", "- `reduced_predictions.csv`: per-horse predictions for the new variant.",
             "- `monthly_results.csv` / `comparison.csv`: month-by-month and full-year metrics for all three variants.",
             "- `market_disagreement_comparison.csv`: popularity-band predicted-vs-actual for all three variants."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), "removed_this_step": removed, "baseline": baseline, "dedup": dedup, "reduced": reduced}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Full-year Ranker walk-forward backtest after adding winning-margin and class-matched recent form.

Continues the redesign started in ranker_dedup_backtest.py (raw margin removed) and
ranker_career_count_backtest.py (career_win_rate/career_races removed). This step adds the
two CLEANUP_E feature families on top of that reduced set:
- WINNING_MARGIN_FEATURES: how decisively last1-3 was won (winner-vs-runner-up TimeDiff via
  margin_value()), 0.0 when the horse itself did not win that prior race.
- CLASS_MATCHED_FORM_FEATURES: last1-3 adjusted_performance restricted to prior races within
  +/-1 legacy class tier of the current race (plain recency for 2yo/3yo-only conditions; a
  horse's first aged-company start also pulls in any prior graded runs), plus the sample count.
Same monthly expanding-window design, calibration window, and target filter as
reports/ranker_walk_forward_12m so results are directly comparable. These columns did not exist
in the phase5-feature-cache-v1 Parquet cache, so `python -m src.build_feature_cache --model F`
must be re-run (regenerating phase5-feature-cache-v2) before this script can find them.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import CAREER_COUNT_FEATURES, CLASS_MATCHED_FORM_FEATURES, DEDUP_MARGIN_FEATURES, WINNING_MARGIN_FEATURES
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf
    from backtest import CAREER_COUNT_FEATURES, CLASS_MATCHED_FORM_FEATURES, DEDUP_MARGIN_FEATURES, WINNING_MARGIN_FEATURES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_cleanup_e_redesign"
BASELINE_PREDICTIONS = ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv"
DEDUP_PREDICTIONS = ROOT / "reports" / "ranker_dedup_redesign" / "dedup_predictions.csv"
REDUCED_PREDICTIONS = ROOT / "reports" / "ranker_career_count_redesign" / "reduced_predictions.csv"
ADDED_FEATURES = WINNING_MARGIN_FEATURES + CLASS_MATCHED_FORM_FEATURES


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


def load_cleanup_e_frame(reduced_features: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Mirrors wf.load_frame() but also pulls the new WINNING_MARGIN/CLASS_MATCHED columns."""
    identifiers = ["race_id", "date", "horse_id", "horse_name", "actual_rank", "target", "odds", "popularity", "umaban", "race_first_prize"]
    available = set(pd.read_parquet(wf.CACHE).columns)
    requested = list(dict.fromkeys(identifiers + reduced_features + ADDED_FEATURES))
    missing = [column for column in ADDED_FEATURES if column not in available]
    if missing:
        raise SystemExit(f"Feature cache is missing {missing}. Rebuild it with `python -m src.build_feature_cache --model F`.")
    frame = pd.read_parquet(wf.CACHE, columns=[column for column in requested if column in available])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[(frame["race_first_prize"] > 8_000_000) & (frame["actual_rank"] > 0) & (frame["odds"] > 0) & (frame["date"] < wf.TEST_END)].copy()
    values = wf.payout_map()
    frame["win_payout"] = [values.get((race_id, int(umaban)), 0.0) for race_id, umaban in zip(frame["race_id"], frame["umaban"])]
    frame.sort_values(["date", "race_id", "horse_id"], inplace=True)
    features = [column for column in reduced_features + ADDED_FEATURES if column in frame.columns]
    return frame.reset_index(drop=True), features


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CLEANUP_E feature set (winning margin + class-matched form) through the full-year Ranker walk-forward")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    _, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    reduced_features = [feature for feature in dedup_features if feature not in CAREER_COUNT_FEATURES]
    frame, cleanup_e_features = load_cleanup_e_frame(reduced_features)
    added = sorted(set(cleanup_e_features) - set(reduced_features))
    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    cleanup_e_rows, training_log = wf.monthly_walk_forward(frame, cleanup_e_features, months, wf.CALIBRATION_MONTHS)
    baseline_rows = load_saved(BASELINE_PREDICTIONS)
    dedup_rows = load_saved(DEDUP_PREDICTIONS)
    reduced_rows = load_saved(REDUCED_PREDICTIONS)
    comparison = [{"variant": "baseline_cleanup_b", "feature_count": len(baseline_features), **wf.metrics(baseline_rows)},
                  {"variant": "dedup_no_raw_margin", "feature_count": len(dedup_features), **wf.metrics(dedup_rows)},
                  {"variant": "no_career_win_rate_no_career_races", "feature_count": len(reduced_features), **wf.metrics(reduced_rows)},
                  {"variant": "cleanup_e_winning_margin_class_matched", "feature_count": len(cleanup_e_features), **wf.metrics(cleanup_e_rows)}]
    monthly_rows = (monthly_metrics("baseline_cleanup_b", baseline_rows) + monthly_metrics("dedup_no_raw_margin", dedup_rows)
                    + monthly_metrics("no_career_win_rate_no_career_races", reduced_rows)
                    + monthly_metrics("cleanup_e_winning_margin_class_matched", cleanup_e_rows))
    market_rows = (market_group_summary(baseline_rows, "baseline_cleanup_b") + market_group_summary(dedup_rows, "dedup_no_raw_margin")
                   + market_group_summary(reduced_rows, "no_career_win_rate_no_career_races")
                   + market_group_summary(cleanup_e_rows, "cleanup_e_winning_margin_class_matched"))
    args.out.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds",
                      "popularity", "ranker_score", "ranker_win_probability", "prediction_rank", "win_payout",
                      "model_train_end_date", "evaluation_mode"]
    write_csv(args.out / "cleanup_e_predictions.csv",
              cleanup_e_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(args.out / "monthly_results.csv", monthly_rows)
    write_csv(args.out / "comparison.csv", comparison)
    write_csv(args.out / "market_disagreement_comparison.csv", market_rows)
    write_csv(args.out / "added_features.csv", [{"feature": feature} for feature in added])
    write_csv(args.out / "monthly_training_log.csv", training_log)
    baseline, dedup, reduced, cleanup_e = comparison
    lines = ["# Ranker CLEANUP_E Redesign (Winning Margin + Class-Matched Form)", "",
             "## Change", f"- Added {len(added)} feature(s) on top of the career-count-reduced set: winner-vs-runner-up winning margin for last1-3, and last1-3 adjusted_performance restricted to prior races within +/-1 legacy class tier (with sample count).",
             "- Everything else (monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged.",
             "", "## Full-Year Comparison (2025-09 to 2026-08)",
             f"- Baseline (CLEANUP_B, {baseline['feature_count']} features): Brier {baseline['brier']:.6f}, AUC {baseline['auc']:.6f}, Top1 {baseline['top1_hit_rate']:.2%}, Top3 {baseline['top3_hit_rate']:.2%}, Top1 Win ROI {baseline['top1_win_roi']:.2f}%, profit {baseline['top1_profit']:.0f} yen.",
             f"- Dedup (raw margin removed, {dedup['feature_count']} features): Brier {dedup['brier']:.6f}, AUC {dedup['auc']:.6f}, Top1 {dedup['top1_hit_rate']:.2%}, Top3 {dedup['top3_hit_rate']:.2%}, Top1 Win ROI {dedup['top1_win_roi']:.2f}%, profit {dedup['top1_profit']:.0f} yen.",
             f"- No career_win_rate/career_races ({reduced['feature_count']} features): Brier {reduced['brier']:.6f}, AUC {reduced['auc']:.6f}, Top1 {reduced['top1_hit_rate']:.2%}, Top3 {reduced['top3_hit_rate']:.2%}, Top1 Win ROI {reduced['top1_win_roi']:.2f}%, profit {reduced['top1_profit']:.0f} yen.",
             f"- CLEANUP_E (winning margin + class-matched form, {cleanup_e['feature_count']} features): Brier {cleanup_e['brier']:.6f}, AUC {cleanup_e['auc']:.6f}, Top1 {cleanup_e['top1_hit_rate']:.2%}, Top3 {cleanup_e['top3_hit_rate']:.2%}, Top1 Win ROI {cleanup_e['top1_win_roi']:.2f}%, profit {cleanup_e['top1_profit']:.0f} yen.",
             "", "## Added In This Step", *[f"- {feature}" for feature in added],
             "", "## Outputs", "- `cleanup_e_predictions.csv`: per-horse predictions for the new variant.",
             "- `monthly_results.csv` / `comparison.csv`: month-by-month and full-year metrics for all four variants.",
             "- `market_disagreement_comparison.csv`: popularity-band predicted-vs-actual for all four variants."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), "added_this_step": added, "baseline": baseline, "dedup": dedup,
                      "reduced": reduced, "cleanup_e": cleanup_e}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

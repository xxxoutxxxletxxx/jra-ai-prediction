#!/usr/bin/env python3
"""Screen focused Ranker feature ablations before full-year confirmation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "ranker_feature_ablation"
SCREEN_START = pd.Timestamp("2026-08-01")
SCREEN_END = pd.Timestamp("2026-09-01")

CANDIDATES = {
    "drop_weighted_adjusted_performance_last3": {"weighted_adjusted_performance_last3"},
    "drop_last1_raw_performance": {"last1_raw_performance"},
    "drop_career_win_rate": {"career_win_rate"},
    "drop_prize_ratio_vs_last3_mean": {"prize_ratio_vs_last3_mean"},
    "drop_finish_margin_group": {
        "weighted_adjusted_performance_last3", "last1_raw_performance", "weighted_margin_last3",
        "last1_adjusted_performance", "mean_adjusted_performance_last3", "last2_adjusted_performance",
        "mean_margin_last3", "last2_raw_performance", "best_strong_opponent_performance_last3",
        "last1_margin_x_prize_strength", "last3_margin_x_prize_strength", "best_adjusted_performance_last3",
        "last3_adjusted_performance", "last2_margin_x_prize_strength", "last2_margin", "last3_raw_performance",
        "last1_margin", "last1_margin_x_winner_strength_v2",
    },
    "drop_race_class_prize_group": {
        "prize_ratio_vs_last3_mean", "prize_change_from_last3_mean", "prize_ratio_vs_last1",
        "race_first_prize", "race_total_top5_prize", "race_second_prize",
    },
    "drop_career_recent_group": {"career_win_rate", "career_races", "recent3_place_rate", "races_last_180d", "career_places", "recent3_win_rate"},
}


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ev_one_metrics(rows: pd.DataFrame) -> dict:
    top1 = rows[rows["prediction_rank"] == 1].copy()
    top1["ev"] = top1["ranker_win_probability"] * (top1["odds"] / 10.0)
    selected = top1[top1["ev"] >= 1.0]
    stake = len(selected) * 100
    return {"top1_average_popularity": top1["popularity"].mean(), "top1_average_odds": (top1["odds"] / 10.0).mean(),
            "top1_ev_ge_1_bets": len(selected), "top1_ev_ge_1_roi": selected["win_payout"].sum() / stake * 100 if stake else None}


def run_variant(frame: pd.DataFrame, features: list[str], label: str, removed: set[str], start: pd.Timestamp, end: pd.Timestamp) -> dict:
    active = [feature for feature in features if feature not in removed]
    months = wf.month_starts(start, end)
    rows, _ = wf.monthly_walk_forward(frame, active, months, wf.CALIBRATION_MONTHS)
    return {"variant": label, "removed_features": ";".join(sorted(removed)), "feature_count": len(active), "period_start": start.strftime("%Y-%m-%d"),
            "period_end_exclusive": end.strftime("%Y-%m-%d"), **wf.metrics(rows), **ev_one_metrics(rows)}


def run_screen_variant(frame: pd.DataFrame, features: list[str], label: str, removed: set[str]) -> dict:
    """One-month candidate screen; T=0.7 was set before August by the baseline's prior-only calibration."""
    active = [feature for feature in features if feature not in removed]
    evaluation = frame[(frame["date"] >= SCREEN_START) & (frame["date"] < SCREEN_END)]
    train = frame[frame["date"] < SCREEN_START]
    scores = wf.ranker_scores(train, evaluation, active)
    rows = wf.add_probabilities(evaluation, scores, 0.7, SCREEN_START - pd.Timedelta(days=1), "ablation_screen")
    return {"variant": label, "removed_features": ";".join(sorted(removed)), "feature_count": len(active), "period_start": SCREEN_START.strftime("%Y-%m-%d"),
            "period_end_exclusive": SCREEN_END.strftime("%Y-%m-%d"), "screen_temperature": 0.7, **wf.metrics(rows), **ev_one_metrics(rows)}


def monthly_retrain_with_baseline_temperatures(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """One retrained Ranker per month; T was selected before each month in the saved baseline."""
    log = pd.read_csv(ROOT / "reports" / "ranker_walk_forward_12m" / "monthly_training_log.csv")
    predictions = []
    for month in wf.month_starts(wf.TEST_START, wf.TEST_END):
        evaluation = frame[(frame["date"] >= month) & (frame["date"] < month + pd.DateOffset(months=1))]
        train = frame[frame["date"] < month]
        temperature = float(log.loc[log["prediction_month"] == month.strftime("%Y-%m"), "temperature"].iloc[0])
        scores = wf.ranker_scores(train, evaluation, features)
        predictions.append(wf.add_probabilities(evaluation, scores, temperature, month - pd.Timedelta(days=1), "ablation_monthly_retrain"))
    return pd.concat(predictions, ignore_index=True)


def saved_baseline() -> pd.DataFrame:
    rows = pd.read_csv(ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv")
    rows["date"] = pd.to_datetime(rows["date"])
    return rows


def sensitivity(rows: pd.DataFrame) -> list[dict]:
    top1 = rows[rows["prediction_rank"] == 1].sort_values("win_payout", ascending=False)
    result = []
    for excluded in (0, 1, 3):
        keep = top1.iloc[excluded:]
        stake = len(keep) * 100
        result.append({"excluded_largest_payouts": excluded, "bets": len(keep), "roi": keep["win_payout"].sum() / stake * 100 if stake else None,
                       "profit": keep["win_payout"].sum() - stake})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Focused Ranker feature-ablation workflow")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--screen-only", action="store_true", help="Run and save the August candidate screen without full-year confirmation.")
    args = parser.parse_args()
    frame, features = wf.load_frame()
    screen = [("baseline", set())] + list(CANDIDATES.items())
    screen_rows = [run_screen_variant(frame, features, label, removed) for label, removed in screen]
    baseline = screen_rows[0]
    # Candidates must improve the short screen ROI without a worse Brier score before full-year confirmation.
    finalists = [row["variant"] for row in screen_rows[1:] if row["top1_win_roi"] > baseline["top1_win_roi"] and row["brier"] <= baseline["brier"] + 0.0005]
    finalists = finalists[:1]
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "ablation_screen_2026_08.csv", screen_rows)
    if args.screen_only:
        print(json.dumps({"screen_candidates": len(CANDIDATES), "full_year_finalists": finalists, "output": str(args.out)}, ensure_ascii=False, indent=2))
        return
    full_variants = [(name, CANDIDATES[name]) for name in finalists]
    full_rows, monthly_rows, sensitivity_rows = [], [], []
    baseline_predictions = saved_baseline()
    baseline_summary = {"variant": "baseline", "removed_features": "", "feature_count": len(features), **wf.metrics(baseline_predictions), **ev_one_metrics(baseline_predictions)}
    full_rows.append(baseline_summary)
    for month, subset in baseline_predictions.groupby(baseline_predictions["date"].dt.strftime("%Y-%m")):
        monthly_rows.append({"variant": "baseline", "month": month, **wf.metrics(subset), **ev_one_metrics(subset)})
    for row in sensitivity(baseline_predictions): sensitivity_rows.append({"variant": "baseline", **row})
    for label, removed in full_variants:
        active = [feature for feature in features if feature not in removed]
        predictions = monthly_retrain_with_baseline_temperatures(frame, active)
        summary = {"variant": label, "removed_features": ";".join(sorted(removed)), "feature_count": len(active),
                   "temperature_policy": "baseline_prior_only_monthly", **wf.metrics(predictions), **ev_one_metrics(predictions)}
        full_rows.append(summary)
        for month, subset in predictions.groupby(predictions["date"].dt.strftime("%Y-%m")):
            monthly_rows.append({"variant": label, "month": month, **wf.metrics(subset), **ev_one_metrics(subset)})
        for row in sensitivity(predictions): sensitivity_rows.append({"variant": label, **row})
    write_csv(args.out / "ablation_screen_2026_06_to_08.csv", screen_rows)
    write_csv(args.out / "ablation_full_year.csv", full_rows)
    write_csv(args.out / "ablation_full_year_monthly.csv", monthly_rows)
    write_csv(args.out / "ablation_high_payout_sensitivity.csv", sensitivity_rows)
    lines = ["# Focused Ranker Ablation", "", "## Method", "- Screen: 2026-08 only with the baseline's prior-only temperature (T=0.7); it selects candidates without accessing later outcomes.",
             "- Full year: only the highest ranked screen candidate that improves ROI while keeping Brier within +0.0005 of baseline is run with monthly retraining. It uses the saved baseline's per-month, prior-only temperatures to avoid a second calibration-model training pass.",
             "- The screen chooses candidates, not a deployable purchase condition.", "", "## Full-Year Results"]
    for row in full_rows:
        lines.append(f"- {row['variant']}: Brier {row['brier']:.6f}, AUC {row['auc']:.6f}, Top1 {row['top1_hit_rate']:.2%}, ROI {row['top1_win_roi']:.2f}%, EV>=1 ROI {row['top1_ev_ge_1_roi']}, removed {row['removed_features'] or 'none'}")
    if not finalists:
        lines.append("- No screen candidate met the preregistered Brier/ROI gate; no non-baseline full-year ablation was run.")
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"screen_candidates": len(CANDIDATES), "full_year_finalists": finalists, "output": str(args.out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

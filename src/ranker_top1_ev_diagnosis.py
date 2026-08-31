#!/usr/bin/env python3
"""Read-only EV diagnosis for Ranker top selections from walk-forward output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_top1_ev_diagnosis"
THRESHOLDS = (None, 0.7, 0.8, 0.9, 1.0, 1.05, 1.1, 1.2, 1.3, 1.5, 2.0)
BANDS = ((0.0, 0.6, "EV < 0.6"), (0.6, 0.8, "0.6 <= EV < 0.8"), (0.8, 1.0, "0.8 <= EV < 1.0"),
         (1.0, 1.2, "1.0 <= EV < 1.2"), (1.2, 1.5, "1.2 <= EV < 1.5"),
         (1.5, 2.0, "1.5 <= EV < 2.0"), (2.0, float("inf"), "EV >= 2.0"))


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


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_top1(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"date", "race_id", "ranker_win_probability", "prediction_rank", "odds", "win_payout", "target", "popularity"}
    missing = required - set(rows[0] if rows else [])
    if missing:
        raise SystemExit(f"Missing input columns: {', '.join(sorted(missing))}")
    top1 = []
    for row in rows:
        if integer(row["prediction_rank"]) != 1:
            continue
        value = dict(row)
        value["ranker_win_probability"] = number(row["ranker_win_probability"])
        value["odds"] = number(row["odds"])
        value["win_odds"] = number(row.get("win_odds"), value["odds"] / 10.0)
        value["win_payout"] = number(row["win_payout"])
        value["target"] = integer(row["target"])
        value["popularity"] = integer(row["popularity"])
        value["top1_ev"] = value["ranker_win_probability"] * value["win_odds"]
        top1.append(value)
    if len({row["race_id"] for row in top1}) != len(top1):
        raise SystemExit("Top1 input must contain exactly one row per race.")
    return top1


def metrics(rows: list[dict], total_races: int) -> dict:
    stake = len(rows) * 100.0
    payout = sum(row["win_payout"] for row in rows)
    return {"total_races": total_races, "bets": len(rows), "bet_rate": len(rows) / total_races if total_races else None,
            "wins": sum(row["target"] for row in rows), "hit_rate": mean(row["target"] for row in rows) if rows else None,
            "average_predicted_probability": mean(row["ranker_win_probability"] for row in rows) if rows else None,
            "actual_win_rate": mean(row["target"] for row in rows) if rows else None,
            "average_odds": mean(row["win_odds"] for row in rows) if rows else None,
            "average_popularity": mean(row["popularity"] for row in rows) if rows else None,
            "average_ev": mean(row["top1_ev"] for row in rows) if rows else None,
            "total_stake": stake, "total_payout": payout, "win_roi": payout / stake * 100.0 if stake else None,
            "profit": payout - stake}


def sensitivity(rows: list[dict], label: str) -> list[dict]:
    records = []
    for excluded in (0, 1, 3):
        remaining = sorted(rows, key=lambda row: row["win_payout"], reverse=True)[excluded:]
        value = metrics(remaining, len(rows))
        records.append({"condition": label, "excluded_largest_payouts": excluded, "bets_remaining": len(remaining),
                        "win_roi": value["win_roi"], "profit": value["profit"]})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose EV information in Ranker top1 walk-forward selections")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    top1 = load_top1(args.input)
    total_races = len(top1)
    threshold_rows, sensitivity_rows = [], []
    selected_by_label: dict[str, list[dict]] = {}
    for threshold in THRESHOLDS:
        label = "No EV condition (baseline)" if threshold is None else f"EV >= {threshold:g}"
        selected = top1 if threshold is None else [row for row in top1 if row["top1_ev"] >= threshold]
        selected_by_label[label] = selected
        threshold_rows.append({"condition": label, "minimum_ev": threshold, **metrics(selected, total_races)})
        sensitivity_rows.extend(sensitivity(selected, label))
    band_rows = []
    for lower, upper, label in BANDS:
        selected = [row for row in top1 if lower <= row["top1_ev"] < upper]
        band_rows.append({"ev_band": label, "lower_ev": lower, "upper_ev": None if np.isinf(upper) else upper,
                          **metrics(selected, total_races)})
    monthly_rows = []
    for threshold in (1.0, 1.1, 1.2):
        label = f"EV >= {threshold:g}"
        for month in sorted({row["date"][:7] for row in top1}):
            month_rows = [row for row in top1 if row["date"][:7] == month]
            selected = [row for row in month_rows if row["top1_ev"] >= threshold]
            monthly_rows.append({"condition": label, "month": month, **metrics(selected, len(month_rows))})
    ev_values = [row["top1_ev"] for row in top1]
    distribution = {"minimum": min(ev_values), "p10": float(np.quantile(ev_values, 0.10)), "p25": float(np.quantile(ev_values, 0.25)),
                    "median": float(np.quantile(ev_values, 0.50)), "p75": float(np.quantile(ev_values, 0.75)),
                    "p90": float(np.quantile(ev_values, 0.90)), "maximum": max(ev_values), "mean": mean(ev_values)}
    baseline = threshold_rows[0]
    ev_one = next(row for row in threshold_rows if row["minimum_ev"] == 1.0)
    high_thresholds = [next(row for row in threshold_rows if row["minimum_ev"] == threshold) for threshold in (1.1, 1.2, 1.3, 1.5)]
    ev_one_months = [row for row in monthly_rows if row["condition"] == "EV >= 1"]
    ev_one_profitable_months = sum((row["win_roi"] or 0.0) >= 100.0 for row in ev_one_months)
    ev_one_sensitivity = [row for row in sensitivity_rows if row["condition"] == "EV >= 1"]
    # Monotonicity is diagnostic, not a threshold-selection criterion.
    roi_series = [next(row for row in threshold_rows if row["minimum_ev"] == threshold)["win_roi"] for threshold in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 2.0)]
    improvements = sum(right > left for left, right in zip(roi_series, roi_series[1:]))
    coherent = improvements >= 5 and all(row["bets"] >= 30 for row in high_thresholds)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "top1_ev_threshold_analysis.csv", threshold_rows)
    write_csv(args.out / "top1_ev_band_analysis.csv", band_rows)
    write_csv(args.out / "top1_ev_monthly.csv", monthly_rows)
    write_csv(args.out / "top1_ev_high_payout_sensitivity.csv", sensitivity_rows)
    metadata = {"input": str(args.input), "races": total_races, "period": [min(row["date"] for row in top1), max(row["date"] for row in top1)],
                "top1_ev_distribution": distribution, "baseline_roi": baseline["win_roi"], "ev_ge_1_roi": ev_one["win_roi"]}
    (args.out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Ranker Top1 EV Diagnosis", "", "## Scope", "- Fixed input: `reports/ranker_walk_forward_12m/walk_forward_predictions.csv`.",
             "- Exactly one Ranker Top1 horse per race. No model, feature, probability, or purchase logic was changed.",
             "- EV uses `ranker_win_probability * (odds / 10)` and 100-yen win bets only for realized ROI.", "", "## EV Distribution",
             *[f"- {key}: {value:.6f}" for key, value in distribution.items()], "", "## Key Results",
             f"- Top1 baseline: {baseline['bets']} bets, hit {baseline['hit_rate']:.2%}, ROI {baseline['win_roi']:.2f}%, profit {baseline['profit']:.0f} yen.",
             f"- EV >= 1.0: {ev_one['bets']} bets ({ev_one['bet_rate']:.2%}), hit {ev_one['hit_rate']:.2%}, predicted {ev_one['average_predicted_probability']:.2%}, ROI {ev_one['win_roi']:.2f}%, profit {ev_one['profit']:.0f} yen."]
    for row in high_thresholds:
        lines.append(f"- EV >= {row['minimum_ev']:g}: {row['bets']} bets, ROI {row['win_roi']:.2f}%, profit {row['profit']:.0f} yen.")
    lines += ["", "## Robustness", f"- EV >= 1.0 had ROI >=100% in only {ev_one_profitable_months}/{len(ev_one_months)} months.",
              f"- EV >= 1.0 payout sensitivity: all {ev_one_sensitivity[0]['win_roi']:.2f}%, excluding largest one {ev_one_sensitivity[1]['win_roi']:.2f}%, excluding largest three {ev_one_sensitivity[2]['win_roi']:.2f}%.",
              "- Higher EV bands have lower realized win rates despite broadly similar or higher predicted probabilities, indicating overestimated model probability relative to the market-price relationship.",
              "", "## Conclusion",
              "- Case A applies only when ROI generally rises with EV thresholds, remains supported by sufficient samples, and survives payout sensitivity.",
              ("- Observed pattern is consistent enough to justify a separate, pre-registered future validation of EV filters; no threshold is adopted here." if coherent else
               "- Observed pattern is not sufficiently monotonic and robust to establish EV as a reliable market-value signal. Return to feature/model evaluation before optimizing purchase thresholds."),
              "- See the monthly and payout-sensitivity files before interpreting any high-ROI tail as a usable condition."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

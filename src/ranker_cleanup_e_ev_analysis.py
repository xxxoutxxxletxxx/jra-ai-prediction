#!/usr/bin/env python3
"""Expected-value betting analysis + rank-probability calibration for CLEANUP_E.

Betting rule: for every horse ranked 1st-5th by the Ranker (prediction_rank <= 5),
compute EV = win_odds * ranker_win_probability (single ticket, 100 yen). Only bet
when EV > 100%; races with no qualifying horse are skipped (no forced bet).

Calibration check: does the Ranker's own win_probability sum up correctly?
- Rank1: mean(win_probability) of the top-rated horse vs its actual win rate.
- Rank1+2: mean(sum of win_probability for rank1+rank2) vs the empirical rate that
  the actual winner is ranked 1st or 2nd (i.e. top2 hit rate).
- Rank1+2+3: same idea for the top3.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS = ROOT / "reports" / "ranker_cleanup_e_redesign" / "cleanup_e_predictions.csv"
OUTPUT = ROOT / "reports" / "ranker_cleanup_e_ev_analysis"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ev_bucket(ev: float) -> str:
    if ev < 1.0:
        return "100%未満(見送り)"
    if ev < 1.2:
        return "100-120%"
    if ev < 1.5:
        return "120-150%"
    if ev < 2.0:
        return "150-200%"
    return "200%以上"


def roi_summary(rows: pd.DataFrame) -> dict:
    count = len(rows)
    investment = count * 100
    win_return = rows["win_payout"].sum() if count else 0.0
    return {"bets": count, "hit_count": int(rows["target"].sum()) if count else 0,
            "hit_rate": rows["target"].mean() if count else None,
            "mean_ev": rows["ev"].mean() if count else None,
            "investment": investment, "return": win_return,
            "roi": win_return / investment * 100 if investment else None}


def main() -> None:
    df = pd.read_csv(PREDICTIONS)
    top5 = df[df["prediction_rank"] <= 5].copy()
    top5["ev"] = top5["win_odds"] * top5["ranker_win_probability"]
    top5["ev_bucket"] = top5["ev"].map(ev_bucket)

    bucket_order = ["100%未満(見送り)", "100-120%", "120-150%", "150-200%", "200%以上"]
    bucket_rows = [{"ev_bucket": bucket, **roi_summary(top5[top5["ev_bucket"] == bucket])} for bucket in bucket_order]

    bets = top5[top5["ev"] >= 1.0].copy()
    overall = roi_summary(bets)
    races_with_bet = bets["race_id"].nunique()
    total_races = top5["race_id"].nunique()

    # calibration: does the model's own probability match the empirical hit rate at each rank depth?
    winners = df[df["target"] == 1][["race_id", "prediction_rank"]].rename(columns={"prediction_rank": "winner_rank"})
    calibration_rows = []
    for depth in (1, 2, 3):
        subset = df[df["prediction_rank"] <= depth]
        predicted_per_race = subset.groupby("race_id")["ranker_win_probability"].sum()
        predicted_mean = predicted_per_race.mean()
        actual_rate = (winners["winner_rank"] <= depth).mean()
        calibration_rows.append({"top_n": depth, "predicted_mean_probability": predicted_mean,
                                 "actual_hit_rate": actual_rate, "gap_actual_minus_predicted": actual_rate - predicted_mean})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "ev_bucket_roi.csv", bucket_rows)
    top5.to_csv(OUTPUT / "top5_ev_bets.csv", index=False)
    write_csv(OUTPUT / "rank_probability_calibration.csv", calibration_rows)

    summary = {"strategy": "prediction_rank<=5 のうち win_odds*ranker_win_probability(EV) >= 100% の馬に単勝100円",
               "total_races": total_races, "races_with_a_bet": races_with_bet,
               "races_skipped_no_positive_ev": total_races - races_with_bet,
               "overall": overall, "by_ev_bucket": bucket_rows, "rank_probability_calibration": calibration_rows}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def pct(value):
        return "N/A" if value is None else f"{value:.2%}"

    def roi_fmt(value):
        return "N/A" if value is None else f"{value:.1f}%"

    lines = ["# CLEANUP_E Expected-Value Betting + Rank Probability Calibration", "",
             f"- 対象レース数: {total_races}（うち少なくとも1頭がEV>=100%だったレース: {races_with_bet}, 見送り: {total_races - races_with_bet}）",
             f"- EV>=100%の馬に単勝100円: {overall['bets']}件購入, 的中{overall['hit_count']}件, 的中率{pct(overall['hit_rate'])}, ROI {roi_fmt(overall['roi'])}",
             "", "## EV帯別ROI（prediction_rank<=5の馬すべてを分類）", "| EV帯 | 購入数 | 的中率 | 平均EV | ROI |", "|---|---:|---:|---:|---:|"]
    for row in bucket_rows:
        lines.append(f"| {row['ev_bucket']} | {row['bets']} | {pct(row['hit_rate'])} | {roi_fmt((row['mean_ev'] or 0) * 100)} | {roi_fmt(row['roi'])} |")
    lines += ["", "## モデルの確率が実際の的中率と一致しているか（キャリブレーション）",
             "| 評価順位 | モデル予測確率の合計(平均) | 実際の的中率 | 差分(実績-予測) |", "|---|---:|---:|---:|"]
    for row in calibration_rows:
        lines.append(f"| 上位{row['top_n']}位まで | {pct(row['predicted_mean_probability'])} | {pct(row['actual_hit_rate'])} | {row['gap_actual_minus_predicted']:+.2%} |")
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "overall": overall, "calibration": calibration_rows}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

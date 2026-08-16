#!/usr/bin/env python3
"""Model Dのレース内予測集中度を事後分析する独立モジュール。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "backtest_prize_D_verified" / "predictions.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "concentration_analysis"


def number(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip() or default)
    except (TypeError, ValueError):
        return default


def integer(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip() or default))
    except (TypeError, ValueError):
        return default


def load_races(path: Path) -> dict[str, list[dict]]:
    races = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row["predicted_probability"] = number(row.get("predicted_probability"))
            row["prediction_rank"] = integer(row.get("prediction_rank"))
            row["actual_rank"] = integer(row.get("actual_rank"))
            row["odds"] = number(row.get("odds"))
            row["win_payout"] = number(row.get("win_payout"))
            row["place_payout"] = number(row.get("place_payout"))
            row["is_win"] = integer(row.get("is_win"))
            races[row["race_id"]].append(row)
    for rows in races.values():
        rows.sort(key=lambda row: (row["prediction_rank"], row.get("horse_id", "")))
    return dict(races)


def load_payouts(db_path: Path) -> dict[str, dict]:
    columns = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    for kind, count in (("Umaren", 3), ("Umatan", 6), ("Wide", 7)):
        columns += [f"Pay{kind}{i}{suffix}" for i in range(count) for suffix in ("Kumi", "Pay")]
    connection = sqlite3.connect(db_path)
    available = {row[1] for row in connection.execute("PRAGMA table_info(NL_HR_PAY)")}
    selected = [column for column in columns if column in available]
    result = {}
    for row in connection.execute(f"SELECT {', '.join(selected)} FROM NL_HR_PAY"):
        values = dict(zip(selected, row))
        key = "-".join(str(values.get(column, "")).strip() for column in ("idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"))
        result[key] = values
    connection.close()
    return result


def payout_for(pay: dict | None, kind: str, selection: str) -> float:
    if not pay or not selection:
        return 0.0
    count = {"Umaren": 3, "Umatan": 6, "Wide": 7}[kind]
    target = str(selection).zfill(4)
    if kind in ("Umaren", "Wide"):
        target = "".join(sorted((target[:2], target[2:])))
    for index in range(count):
        value = str(pay.get(f"Pay{kind}{index}Kumi", "") or "").zfill(4)
        if kind in ("Umaren", "Wide"):
            value = "".join(sorted((value[:2], value[2:])))
        if value == target:
            return number(pay.get(f"Pay{kind}{index}Pay"))
    return 0.0


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(item <= value for item in values) / len(values) * 100


def safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def analyze_race(rows: list[dict], payouts: dict[str, dict] | None = None) -> dict:
    probabilities = [max(0.0, row["predicted_probability"]) for row in rows]
    total = sum(probabilities)
    shares = [value / total for value in probabilities] if total else [1 / len(rows)] * len(rows)
    p = shares + [0.0] * max(0, 4 - len(shares))
    entropy = -sum(value * math.log(value) for value in shares if value > 0)
    normalized_entropy = entropy / math.log(len(shares)) if len(shares) > 1 else 0.0
    actual = sorted(rows, key=lambda row: (row["actual_rank"] or 999, row.get("horse_id", "")))
    actual_top3 = [row.get("horse_id", "") for row in actual[:3]]
    predicted_top3 = [row.get("horse_id", "") for row in rows[:3]]
    top2_ids = {row.get("horse_id", "") for row in rows[:2]}
    actual_top2 = {row.get("horse_id", "") for row in actual[:2]}
    top1 = rows[0] if rows else {}
    top2 = rows[1] if len(rows) > 1 else {}
    top3 = rows[2] if len(rows) > 2 else {}
    top4 = rows[3] if len(rows) > 3 else {}
    pay = (payouts or {}).get(rows[0].get("race_id", ""))
    selection_box = "".join(sorted((str(integer(top1.get("umaban", 0))).zfill(2), str(integer(top2.get("umaban", 0))).zfill(2)))) if top2 else ""
    selection_order = str(integer(top1.get("umaban", 0))).zfill(2) + str(integer(top2.get("umaban", 0))).zfill(2) if top2 else ""
    quinella_payout = payout_for(pay, "Umaren", selection_box)
    exacta_payout = payout_for(pay, "Umatan", selection_order)
    top3_candidates = [row for row in rows[:3] if row.get("odds", 0) > 0]
    highest_odds_candidate = max(top3_candidates, key=lambda row: row.get("odds", 0), default={})
    edge_candidate = max(top3_candidates, key=lambda row: row.get("predicted_probability", 0) * row.get("odds", 0), default={})
    gap_1_2 = p[0] - p[1]
    gap_2_3 = p[1] - p[2]
    gap_3_4 = p[2] - p[3]
    recommendations = []
    return {
        "race_id": rows[0].get("race_id", ""), "date": rows[0].get("date", ""),
        "racecourse": rows[0].get("racecourse", ""), "race_number": rows[0].get("race_number", ""),
        "pred_rank1_horse": top1.get("horse_name", ""), "pred_rank2_horse": top2.get("horse_name", ""),
        "pred_rank3_horse": top3.get("horse_name", ""), "p1": p[0], "p2": p[1], "p3": p[2], "p4": p[3],
        "gap_1_2": gap_1_2, "gap_2_3": gap_2_3, "gap_3_4": gap_3_4,
        "ratio_1_2": safe_ratio(p[0], p[1]), "ratio_2_3": safe_ratio(p[1], p[2]), "ratio_3_4": safe_ratio(p[2], p[3]),
        "top1_share": sum(shares[:1]), "top2_share": sum(shares[:2]), "top3_share": sum(shares[:3]),
        "prediction_entropy": entropy, "normalized_entropy": normalized_entropy,
        "prediction_std": pstdev(probabilities) if len(probabilities) > 1 else 0.0,
        "prediction_range": max(probabilities, default=0.0) - min(probabilities, default=0.0),
        "actual_winner": actual[0].get("horse_name", "") if actual else "",
        "actual_second": actual[1].get("horse_name", "") if len(actual) > 1 else "",
        "actual_third": actual[2].get("horse_name", "") if len(actual) > 2 else "",
        "top1_hit": int(bool(rows and rows[0]["is_win"])),
        "top1_place_hit": int(bool(rows and 1 <= rows[0]["actual_rank"] <= 3)),
        "top2_box_hit": int(top2_ids == actual_top2),
        "top2_exact_hit": int(rows[:2] and [row.get("horse_id", "") for row in rows[:2]] == [row.get("horse_id", "") for row in actual[:2]]),
        "top3_box_hit": int(set(predicted_top3) == set(actual_top3)),
        "top2_order_hit": int(rows[:2] and [row.get("horse_id", "") for row in rows[:2]] == [row.get("horse_id", "") for row in actual[:2]]),
        "top1_odds": top1.get("odds", 0.0),
        "top1_win_payout": top1.get("win_payout", 0.0),
        "top1_place_payout": top1.get("place_payout", 0.0),
        "top3_highest_odds_hit": integer(highest_odds_candidate.get("is_win", 0)),
        "top3_highest_odds_payout": number(highest_odds_candidate.get("win_payout", 0)),
        "top3_edge_hit": integer(edge_candidate.get("is_win", 0)),
        "top3_edge_payout": number(edge_candidate.get("win_payout", 0)),
        "top1_fair_odds": safe_ratio(1.0, top1.get("predicted_probability", 0.0)),
        "top1_market_implied_probability": safe_ratio(1.0, top1.get("odds", 0.0)),
        "top1_edge": top1.get("predicted_probability", 0.0) - (safe_ratio(1.0, top1.get("odds", 0.0)) or 0.0),
        "top1_expected_return": top1.get("predicted_probability", 0.0) * top1.get("odds", 0.0),
        "quinella_payout": quinella_payout, "exacta_payout": exacta_payout,
        "payout_available": int(bool(pay)),
        "recommendation": "UNSET",
    }


def metric_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"races": 0}
    return {
        "races": len(rows), "top1_win_rate": mean(row["top1_hit"] for row in rows),
        "top1_place_rate": mean(row["top1_place_hit"] for row in rows),
        "top2_box_rate": mean(row["top2_box_hit"] for row in rows),
        "top2_exact_order_rate": mean(row["top2_exact_hit"] for row in rows),
        "top3_box_rate": mean(row["top3_box_hit"] for row in rows),
        "top2_order_rate": mean(row["top2_order_hit"] for row in rows),
        "quinella_hit_rate": mean(row["top2_box_hit"] for row in rows),
        "exacta_hit_rate": mean(row["top2_exact_hit"] for row in rows),
        "quinella_average_payout": mean(row["quinella_payout"] for row in rows if row["quinella_payout"] > 0) if any(row["quinella_payout"] > 0 for row in rows) else None,
        "exacta_average_payout": mean(row["exacta_payout"] for row in rows if row["exacta_payout"] > 0) if any(row["exacta_payout"] > 0 for row in rows) else None,
        "quinella_roi": sum(row["quinella_payout"] for row in rows) / (len(rows) * 100) * 100 if rows and any(row["payout_available"] for row in rows) else None,
        "exacta_roi": sum(row["exacta_payout"] for row in rows) / (len(rows) * 100) * 100 if rows and any(row["payout_available"] for row in rows) else None,
        "mean_top1_odds": mean(row["top1_odds"] for row in rows),
        "win_roi_if_top1_100yen": sum(row.get("top1_win_payout", 0.0) for row in rows) / (len(rows) * 100) * 100 if rows else None,
    }


def percentile_analysis(rows: list[dict], metric: str) -> list[dict]:
    values = [row[metric] for row in rows]
    result = []
    for low, high in zip(range(0, 100, 10), range(10, 110, 10)):
        selected = [row for row in rows if low <= percentile(row[metric], values) < high]
        if high == 100:
            selected = [row for row in rows if percentile(row[metric], values) >= low]
        summary = metric_summary(selected)
        result.append({"metric": metric, "percentile_bin": f"{low}-{high}%", "lower_threshold": quantile(values, low / 100),
                   "upper_threshold": quantile(values, high / 100),
                   "avg_gap_1_2": mean(row["gap_1_2"] for row in selected) if selected else None,
                   "avg_gap_2_3": mean(row["gap_2_3"] for row in selected) if selected else None,
                   "avg_gap_3_4": mean(row["gap_3_4"] for row in selected) if selected else None,
                   "avg_entropy": mean(row["normalized_entropy"] for row in selected) if selected else None,
                   "avg_top1_share": mean(row["top1_share"] for row in selected) if selected else None,
                   "avg_top2_share": mean(row["top2_share"] for row in selected) if selected else None,
                   "avg_top3_share": mean(row["top3_share"] for row in selected) if selected else None,
                   **summary})
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def cross_gap_analysis(rows: list[dict]) -> list[dict]:
    gap12 = [row["gap_1_2"] for row in rows]
    gap23 = [row["gap_2_3"] for row in rows]
    result = []
    for outer_low, outer_high in ((0, 20), (20, 50), (50, 80), (80, 100)):
        outer = [row for row in rows if outer_low <= percentile(row["gap_2_3"], gap23) < outer_high or (outer_high == 100 and percentile(row["gap_2_3"], gap23) >= outer_low)]
        for inner_low, inner_high in ((0, 20), (20, 50), (50, 80), (80, 100)):
            selected = [row for row in outer if inner_low <= percentile(row["gap_1_2"], gap12) < inner_high or (inner_high == 100 and percentile(row["gap_1_2"], gap12) >= inner_low)]
            summary = metric_summary(selected)
            result.append({"gap_2_3_percentile": f"{outer_low}-{outer_high}%", "gap_1_2_percentile": f"{inner_low}-{inner_high}%", **summary})
    return result


def value_strategy(rows: list[dict], strategy: str) -> dict:
    selected = []
    for row in rows:
        if strategy == "top1":
            selected.append(row)
        elif strategy == "highest_odds_top3":
            selected.append(row)
    if strategy == "highest_odds_top3":
        hit_key, payout_key = "top3_highest_odds_hit", "top3_highest_odds_payout"
    elif strategy == "edge_top3":
        hit_key, payout_key = "top3_edge_hit", "top3_edge_payout"
    else:
        hit_key, payout_key = "top1_hit", "top1_win_payout"
    return {"bets": len(rows), "hits": sum(row[hit_key] for row in rows),
            "hit_rate": mean(row[hit_key] for row in rows) if rows else None,
            "stake": len(rows) * 100, "return": sum(row[payout_key] for row in rows),
            "roi": sum(row[payout_key] for row in rows) / (len(rows) * 100) * 100 if rows else None}


def assign_recommendations(rows: list[dict]) -> None:
    gap12 = [row["gap_1_2"] for row in rows]
    gap23 = [row["gap_2_3"] for row in rows]
    gap34 = [row["gap_3_4"] for row in rows]
    entropy = [row["normalized_entropy"] for row in rows]
    for row in rows:
        p12 = percentile(row["gap_1_2"], gap12)
        p23 = percentile(row["gap_2_3"], gap23)
        p34 = percentile(row["gap_3_4"], gap34)
        ent = percentile(row["normalized_entropy"], entropy)
        if p12 >= 90 and p23 < 60:
            row["recommendation"] = "ONE_HORSE"
        elif p23 >= 90 and p12 >= 50:
            row["recommendation"] = "TWO_HORSE_CONCENTRATED"
        elif p34 >= 90:
            row["recommendation"] = "THREE_HORSE"
        elif ent <= 20:
            row["recommendation"] = "FLAT_VALUE"
        elif ent >= 80:
            row["recommendation"] = "CHAOTIC_SKIP"
        else:
            row["recommendation"] = "UNSET"
        row["order_confidence"] = "HIGH" if p12 >= 80 else "MEDIUM" if p12 >= 50 else "LOW"


def write_report(rows: list[dict], output: Path, input_path: Path) -> None:
    assign_recommendations(rows)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "race_concentration.csv", rows)
    write_csv(output / "gap_1_2_analysis.csv", percentile_analysis(rows, "gap_1_2"))
    write_csv(output / "gap_2_3_analysis.csv", percentile_analysis(rows, "gap_2_3"))
    write_csv(output / "gap_3_4_analysis.csv", percentile_analysis(rows, "gap_3_4"))
    write_csv(output / "entropy_analysis.csv", percentile_analysis(rows, "normalized_entropy"))
    write_csv(output / "gap_cross_analysis.csv", cross_gap_analysis(rows))
    write_csv(output / "top2_concentration.csv", [metric_summary(rows)])
    write_csv(output / "top3_concentration.csv", [metric_summary(rows)])
    recommendation_rows = []
    for label in sorted({row["recommendation"] for row in rows}):
        selected = [row for row in rows if row["recommendation"] == label]
        recommendation_rows.append({"recommendation": label, **metric_summary(selected)})
    write_csv(output / "recommendation_analysis.csv", recommendation_rows)
    write_csv(output / "gap_1_2_detailed.csv", percentile_analysis(rows, "gap_1_2"))
    write_csv(output / "gap_2_3_detailed.csv", percentile_analysis(rows, "gap_2_3"))
    write_csv(output / "gap_3_4_detailed.csv", percentile_analysis(rows, "gap_3_4"))
    write_csv(output / "entropy_detailed.csv", percentile_analysis(rows, "normalized_entropy"))
    write_csv(output / "one_horse_analysis.csv", [metric_summary([row for row in rows if row["recommendation"] == "ONE_HORSE"]),
                                                    metric_summary([row for row in rows if row["gap_1_2"] >= quantile([item["gap_1_2"] for item in rows], 0.9)])])
    write_csv(output / "two_horse_concentration.csv", [metric_summary([row for row in rows if row["recommendation"] == "TWO_HORSE_CONCENTRATED"]),
                                                        metric_summary([row for row in rows if row["gap_2_3"] >= quantile([item["gap_2_3"] for item in rows], 0.9)])])
    write_csv(output / "two_horse_order_analysis.csv", [metric_summary([row for row in rows if row["recommendation"] == "TWO_HORSE_CONCENTRATED" and row["order_confidence"] == level]) for level in ("HIGH", "MEDIUM", "LOW")])
    write_csv(output / "three_horse_analysis.csv", [metric_summary([row for row in rows if row["recommendation"] == "THREE_HORSE"])])
    flat = [row for row in rows if row["recommendation"] == "FLAT_VALUE"]
    write_csv(output / "flat_value_analysis.csv", [{"strategy": label, **value_strategy(flat, label)} for label in ("top1", "highest_odds_top3", "edge_top3")])
    write_csv(output / "betting_roi_summary.csv", [{"strategy": label, **value_strategy(rows, label)} for label in ("top1", "highest_odds_top3", "edge_top3")])
    summary = {"input": str(input_path), "races": len(rows), "payout_available_races": sum(row["payout_available"] for row in rows), "overall": metric_summary(rows),
               "recommendations": recommendation_rows,
               "method": "集中度はModel Dの予測確率のみで計算。recommendationの候補分類は同一評価期間内のgap/entropy percentileに基づく探索用で、固定閾値による購入判断ではない。",
               "odds_layer": "fair_odds=1/predicted_probability, market_implied_probability=1/odds, edge=p-model_market, expected_return=p*odds。オッズはModel D学習には投入しない。"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(output / "summary.md", summary, rows)


def write_summary(path: Path, summary: dict, rows: list[dict]) -> None:
    lines = ["# Concentration Analysis", "", "## Overall", f"- Races: {summary['races']}",
             f"- Top1 win rate: {summary['overall']['top1_win_rate']:.2%}",
             f"- Top2 box hit rate: {summary['overall']['top2_box_rate']:.2%}",
             f"- Top2 exact order rate: {summary['overall']['top2_exact_order_rate']:.2%}",
             f"- Top3 box hit rate: {summary['overall']['top3_box_rate']:.2%}",
             "- 馬連/馬単は予測CSVに払戻列がないため、的中率のみ計算し、配当・ROIはN/A。", "", "## Recommendation exploration",
             "分類は同一期間のpercentileを使った探索用であり、固定閾値・自動購入判断ではありません。", "| Type | Races | Top1 | Top2 box | Top2 order | Top3 box |", "|---|---:|---:|---:|---:|---:|"]
    for row in summary["recommendations"]:
        lines.append(f"| {row['recommendation']} | {row['races']} | {row.get('top1_win_rate', 0):.2%} | {row.get('top2_box_rate', 0):.2%} | {row.get('top2_exact_order_rate', 0):.2%} | {row.get('top3_box_rate', 0):.2%} |")
    lines += ["", "## Gap analysis", "gap_1_2 / gap_2_3 / gap_3_4 とTop2・Top3独占率、順序一致率、ROIは各 *_analysis.csv を参照。", "", "## Leakage and odds", "予測確率・収束度はオッズを使わず計算。オッズは後段のfair odds/edge分析だけに使用。結果列は評価専用で、特徴量生成には使用しない。", "", "## Interpretation", "Top2 boxは予測上位2頭が実際の1・2着を占めた割合、Top3 boxは予測上位3頭が実際の1～3着を占めた割合。サンプル数とpercentile分布を併記し、収束度を因果的な確信度とは断定しない。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def percentile_bins(values: list[float], metric: str) -> list[dict]:
    result = []
    for low, high in zip(range(0, 100, 10), range(10, 110, 10)):
        selected = [row for row in values if low <= percentile(row[metric], [item[metric] for item in values]) < high]
        if high == 100:
            selected = [row for row in values if percentile(row[metric], [item[metric] for item in values]) >= low]
        result.append((low, high, selected))
    return result


def phase3_analyze(races: dict[str, list[dict]], analyzed: list[dict], payouts: dict[str, dict], output: Path) -> None:
    """Anchor、全隣接Major Gap、cluster、流し馬券を分析する。閾値は探索用90 percentile。"""
    output.mkdir(parents=True, exist_ok=True)
    by_id = {row["race_id"]: row for row in analyzed}
    anchors = []
    all_gaps = []
    race_structures = []
    for race_id, horses in races.items():
        ordered = sorted(horses, key=lambda row: (integer(row.get("prediction_rank")), row.get("horse_id", "")))
        if not ordered:
            continue
        probabilities = [row["predicted_probability"] for row in ordered]
        p1, p2 = probabilities[0], probabilities[1] if len(probabilities) > 1 else 0.0
        median_field = sorted(probabilities)[len(probabilities) // 2]
        race_row = by_id.get(race_id, {})
        anchor_base = {"race_id": race_id, "horse_id": ordered[0].get("horse_id", ""),
                       "horse_name": ordered[0].get("horse_name", ""), "prediction_rank": 1,
                       "prediction_score": p1, "gap_1_2": p1 - p2,
                       "top1_share": race_row.get("top1_share", 0.0), "entropy": race_row.get("normalized_entropy", 0.0),
                       "p1_minus_median": p1 - median_field,
                       "actual_finish": ordered[0].get("actual_rank", 0),
                       "win_hit": int(ordered[0].get("actual_rank") == 1),
                       "top2_hit": int(1 <= integer(ordered[0].get("actual_rank")) <= 2),
                       "top3_hit": int(1 <= integer(ordered[0].get("actual_rank")) <= 3),
                       "win_payout": number(ordered[0].get("win_payout")), "place_payout": number(ordered[0].get("place_payout"))}
        anchors.append(anchor_base)
        for index in range(len(ordered) - 1):
            upper, lower = ordered[index], ordered[index + 1]
            raw_gap = probabilities[index] - probabilities[index + 1]
            all_gaps.append({"race_id": race_id, "gap_rank_upper": index + 1, "gap_rank_lower": index + 2,
                             "upper_horse": upper.get("horse_name", ""), "lower_horse": lower.get("horse_name", ""),
                             "upper_score": probabilities[index], "lower_score": probabilities[index + 1],
                             "raw_gap": raw_gap, "gap_ratio": safe_ratio(probabilities[index], probabilities[index + 1]),
                             "cluster_above_size": index + 1})
    gap_values = [row["raw_gap"] for row in all_gaps]
    for row in all_gaps:
        row["gap_percentile"] = percentile(row["raw_gap"], gap_values)
        row["gap_strength"] = row["gap_percentile"]
        row["is_major_gap"] = int(row["gap_percentile"] >= 90)
    anchor_gap = [row["gap_1_2"] for row in anchors]
    anchor_share = [row["top1_share"] for row in anchors]
    anchor_entropy = [row["entropy"] for row in anchors]
    anchor_median = [row["p1_minus_median"] for row in anchors]
    for row in anchors:
        strength_parts = [percentile(row["gap_1_2"], anchor_gap), percentile(row["top1_share"], anchor_share),
                          100 - percentile(row["entropy"], anchor_entropy), percentile(row["p1_minus_median"], anchor_median)]
        row["anchor_strength"] = mean(strength_parts)
    def anchor_summary(selected: list[dict]) -> dict:
        if not selected:
            return {"races": 0}
        return {"races": len(selected), "win_rate": mean(row["win_hit"] for row in selected),
                "top2_rate": mean(row["top2_hit"] for row in selected), "top3_rate": mean(row["top3_hit"] for row in selected),
                "average_finish": mean(row["actual_finish"] for row in selected),
                "median_finish": sorted(row["actual_finish"] for row in selected)[len(selected) // 2],
                "win_roi": sum(row["win_payout"] for row in selected) / (len(selected) * 100) * 100,
                "place_roi": sum(row["place_payout"] for row in selected) / (len(selected) * 100) * 100}
    anchor_analysis = []
    for low, high, selected in percentile_bins(anchors, "anchor_strength"):
        anchor_analysis.append({"anchor_strength_bin": f"{low}-{high}%", **anchor_summary(selected)})
    # Build clusters at major-gap boundaries. A race may have multiple major gaps.
    cluster_rows, cluster_reliability, flow_rows = [], [], []
    for race_id, horses in races.items():
        ordered = sorted(horses, key=lambda row: integer(row.get("prediction_rank")))
        gaps = [row for row in all_gaps if row["race_id"] == race_id]
        boundaries = {row["gap_rank_lower"] for row in gaps if row["is_major_gap"]}
        cluster_id = 1
        previous = 0
        clusters = []
        for boundary in sorted(boundaries | {len(ordered) + 1}):
            group = ordered[previous:boundary - 1]
            if group:
                clusters.append((cluster_id, group)); cluster_id += 1
            previous = boundary - 1
        if not clusters:
            clusters = [(1, ordered)]
        for cid, group in clusters:
            for row in group:
                cluster_rows.append({"race_id": race_id, "rank": integer(row.get("prediction_rank")), "horse_id": row.get("horse_id", ""),
                                     "horse_name": row.get("horse_name", ""), "prediction_score": row.get("predicted_probability"),
                                     "cluster_id": cid, "cluster_size": len(group), "is_anchor": int(cid == 1 and integer(row.get("prediction_rank")) == 1),
                                     "is_primary_opponent": int(cid == 2), "gap_before": next((g["raw_gap"] for g in gaps if g["gap_rank_lower"] == integer(row.get("prediction_rank"))), 0),
                                     "gap_after": next((g["raw_gap"] for g in gaps if g["gap_rank_upper"] == integer(row.get("prediction_rank"))), 0)})
        top_group = clusters[0][1]
        top_ids = {row.get("horse_id", "") for row in top_group}
        actual = sorted(ordered, key=lambda row: integer(row.get("actual_rank")) or 999)
        cluster_reliability.append({"race_id": race_id, "cluster_size": len(top_group),
                                    "winner_inside_cluster": int(actual and actual[0].get("horse_id", "") in top_ids),
                                    "top2_inside_cluster": int(set(row.get("horse_id", "") for row in actual[:2]) <= top_ids),
                                    "top3_inside_cluster": int(set(row.get("horse_id", "") for row in actual[:3]) <= top_ids)})
        if len(clusters) > 1:
            anchor = ordered[0]
            opponents = clusters[1][1]
            pay = payouts.get(race_id)
            quinella_return = sum(payout_for(pay, "Umaren", "".join(sorted((str(integer(anchor.get("umaban", 0))).zfill(2), str(integer(opponent.get("umaban", 0))).zfill(2))))) for opponent in opponents)
            exacta_return = sum(payout_for(pay, "Umatan", str(integer(anchor.get("umaban", 0))).zfill(2) + str(integer(opponent.get("umaban", 0))).zfill(2)) for opponent in opponents)
            wide_return = sum(payout_for(pay, "Wide", "".join(sorted((str(integer(anchor.get("umaban", 0))).zfill(2), str(integer(opponent.get("umaban", 0))).zfill(2))))) for opponent in opponents)
            flow_rows.append({"race_id": race_id, "anchor": anchor.get("horse_name", ""), "opponent_cluster": "/".join(row.get("horse_name", "") for row in opponents),
                              "opponent_count": len(opponents), "quinella_tickets": len(opponents), "quinella_hit": int(quinella_return > 0),
                              "quinella_stake": len(opponents) * 100, "quinella_return": quinella_return,
                              "quinella_roi": quinella_return / (len(opponents) * 100) * 100 if opponents else 0,
                              "exacta_tickets": len(opponents), "exacta_hit": int(exacta_return > 0),
                              "exacta_stake": len(opponents) * 100, "exacta_return": exacta_return,
                              "exacta_roi": exacta_return / (len(opponents) * 100) * 100 if opponents else 0,
                              "wide_tickets": len(opponents), "wide_stake": len(opponents) * 100,
                              "wide_return": wide_return, "wide_roi": wide_return / (len(opponents) * 100) * 100 if opponents else 0})
    write_csv(output / "anchor_horses.csv", anchors)
    write_csv(output / "anchor_percentile_analysis.csv", anchor_analysis)
    write_csv(output / "anchor_strength_analysis.csv", anchor_analysis)
    write_csv(output / "all_adjacent_gaps.csv", all_gaps)
    write_csv(output / "major_gaps.csv", [row for row in all_gaps if row["is_major_gap"]])
    write_csv(output / "gap_strength_analysis.csv", [{"gap_strength_bin": f"{low}-{high}%", "gaps": len(selected),
                                                       "mean_gap": mean(row["raw_gap"] for row in selected) if selected else None}
                                                      for low, high, selected in percentile_bins(all_gaps, "gap_strength")])
    write_csv(output / "race_clusters.csv", cluster_rows)
    write_csv(output / "cluster_reliability.csv", cluster_reliability)
    write_csv(output / "anchor_opponent_cluster.csv", flow_rows)
    for filename in ("anchor_win_roi.csv", "anchor_place_roi.csv"):
        metric = "win_payout" if "win" in filename else "place_payout"
        write_csv(output / filename, [{"races": len(anchors), "return": sum(row[metric] for row in anchors), "stake": len(anchors) * 100,
                                      "roi": sum(row[metric] for row in anchors) / (len(anchors) * 100) * 100}])
    write_csv(output / "anchor_quinella_flow_roi.csv", flow_rows)
    write_csv(output / "anchor_wide_flow_roi.csv", flow_rows)
    (output / "phase3_summary.md").write_text(
        "# Phase 3 Anchor and Major Gap\n\n"
        f"- Races: {len(anchors)}\n"
        f"- Anchor strength is an equal mean of percentile(gap_1_2), percentile(top1_share), inverse percentile(entropy), and percentile(p1-minus-field-median).\n"
        "- Major gap: exploratory top 10 percentile of all adjacent gaps; no production threshold is claimed.\n"
        "- Anchor rates and ROI are separated: see anchor_percentile_analysis.csv.\n"
        "- Cluster and multi-gap structure: see race_clusters.csv and major_gaps.csv.\n"
        "- Anchor to opponent-cluster quinella/exacta flow uses one 100-yen ticket per opponent; stake equals ticket count.\n"
        "- Wide flow uses NL_HR_PAY PayWide0..6 and accounts for one ticket per opponent.\n"
        "- No odds are used in Model D or Anchor/Gap features; odds and payouts are research-only.\n"
        "- All source rows are out-of-sample Model D predictions; no target/result columns are used to form features.\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Model D race concentration")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "raw" / "race.db")
    args = parser.parse_args()
    races = load_races(args.input)
    payouts = load_payouts(args.db)
    rows = [analyze_race(values, payouts) for values in races.values() if values]
    write_report(rows, args.out, args.input)
    phase3_analyze(races, rows, payouts, ROOT / "reports" / "anchor_phase3")
    print(json.dumps({"output": str(args.out), "races": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
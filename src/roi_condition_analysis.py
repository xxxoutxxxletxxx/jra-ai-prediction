#!/usr/bin/env python3
""""モデル自体の改善前に、ROI を削っている条件を特定するための分析"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median, mean

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "cleanup_B_cached_50_verified" / "predictions.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "roi_condition_analysis"


def number(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def integer(value: object, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def safe_ratio(num: float, den: float) -> float | None:
    if den in (None, 0):
        return None
    return num / den


def percentile(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if value <= ordered[0]:
        return 0.0
    if value >= ordered[-1]:
        return 100.0
    count = sum(1 for item in ordered if item <= value)
    return (count / len(ordered)) * 100.0


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * fraction
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def popularity_band(value: int | float) -> str:
    pop = int(value)
    if pop == 1:
        return "1番人気"
    if 2 <= pop <= 3:
        return "2〜3番人気"
    if 4 <= pop <= 6:
        return "4〜6番人気"
    if 7 <= pop <= 9:
        return "7〜9番人気"
    return "10番人気以下"


def gap_band(values: list[float], value: float, bins: int = 5) -> str:
    if not values:
        return "N/A"
    thresholds = [quantile(values, idx / bins) for idx in range(1, bins)]
    for idx, threshold in enumerate(thresholds, 1):
        if value <= threshold:
            return f"Q{idx}"
    return f"Q{bins}"


def roi_metrics(rows: list[dict], kind: str) -> dict:
    if not rows:
        return {"bets": 0, "wins": 0, "places": 0, "hit_rate": None, "roi": None, "profit": 0.0, "payout": 0.0, "investment": 0.0}
    payout_key = "win_payout" if kind == "win" else "place_payout"
    hit_key = "is_win" if kind == "win" else "is_place"
    investment = len(rows) * 100
    payout_total = sum(number(row.get(payout_key), 0.0) for row in rows)
    wins = sum(integer(row.get(hit_key), 0) for row in rows)
    hit_rate = wins / len(rows) if rows else None
    roi = ((payout_total - investment) / investment * 100.0) if investment else None
    return {
        "bets": len(rows),
        "wins": wins,
        "hit_rate": hit_rate,
        "roi": roi,
        "profit": payout_total - investment,
        "payout": payout_total,
        "investment": investment,
    }


def clean_predictions(rows: list[dict]) -> list[dict]:
    cleaned = []
    for row in rows:
        normalized = dict(row)
        for key in ["predicted_probability", "odds", "actual_rank", "prediction_rank", "popularity",
                    "win_payout", "place_payout", "field_size", "is_win", "is_place", "distance"]:
            if key in normalized:
                if key in {"predicted_probability", "odds", "win_payout", "place_payout", "distance"}:
                    normalized[key] = number(normalized.get(key), 0.0)
                else:
                    normalized[key] = integer(normalized.get(key), 0)
        normalized["popularity_band"] = popularity_band(normalized.get("popularity", 0))
        normalized["market_probability"] = safe_ratio(1.0, normalized.get("odds", 0.0))
        normalized["edge"] = normalized.get("predicted_probability", 0.0) - (normalized.get("market_probability") or 0.0)
        normalized["expected_value"] = normalized.get("predicted_probability", 0.0) * normalized.get("odds", 0.0)
        cleaned.append(normalized)
    return cleaned


def load_predictions(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return clean_predictions(rows)


def compute_race_level(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("race_id", "")].append(row)

    records = []
    for race_id, race_rows in grouped.items():
        ordered = sorted(race_rows, key=lambda item: (integer(item.get("prediction_rank"), 999), item.get("horse_id", "")))
        if not ordered:
            continue
        p1 = ordered[0].get("predicted_probability", 0.0)
        p2 = ordered[1].get("predicted_probability", 0.0) if len(ordered) > 1 else 0.0
        p3 = ordered[2].get("predicted_probability", 0.0) if len(ordered) > 2 else 0.0
        gap_1_2 = p1 - p2
        gap_2_3 = p2 - p3
        gap_1_3 = p1 - p3
        ratio_1_2 = safe_ratio(p1, p2)
        top1 = ordered[0]
        records.append({
            "race_id": race_id,
            "date": top1.get("date", ""),
            "racecourse": top1.get("racecourse", ""),
            "surface": top1.get("surface", ""),
            "distance": top1.get("distance", 0),
            "class_code": top1.get("class_code", "UNKNOWN"),
            "race_class_label": top1.get("race_class_label", "UNKNOWN"),
            "race_class_score": top1.get("race_class_score", 0.0),
            "top1_horse_id": top1.get("horse_id", ""),
            "top1_horse_name": top1.get("horse_name", ""),
            "top1_popularity": integer(top1.get("popularity"), 0),
            "top1_popularity_band": popularity_band(top1.get("popularity", 0)),
            "top1_odds": number(top1.get("odds"), 0.0),
            "top1_probability": p1,
            "p2_probability": p2,
            "p3_probability": p3,
            "gap_1_2": gap_1_2,
            "gap_2_3": gap_2_3,
            "gap_1_3": gap_1_3,
            "ratio_1_2": ratio_1_2,
            "top1_actual_rank": integer(top1.get("actual_rank"), 0),
            "top1_is_win": integer(top1.get("is_win"), 0),
            "top1_is_place": integer(top1.get("is_place"), 0),
            "top1_win_payout": number(top1.get("win_payout"), 0.0),
            "top1_place_payout": number(top1.get("place_payout"), 0.0),
            "market_probability": safe_ratio(1.0, top1.get("odds", 0.0)),
            "edge": p1 - (safe_ratio(1.0, top1.get("odds", 0.0)) or 0.0),
            "expected_value": p1 * number(top1.get("odds"), 0.0),
        })
    return records


def summarize_top1_by_popularity(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        if integer(row.get("prediction_rank"), 0) == 1:
            grouped[popularity_band(integer(row.get("popularity"), 0))].append(row)

    records = []
    for band, band_rows in sorted(grouped.items()):
        win = roi_metrics(band_rows, "win")
        place = roi_metrics(band_rows, "place")
        odds = [number(row.get("odds"), 0.0) for row in band_rows]
        records.append({
            "popularity_band": band,
            "races": len({row["race_id"] for row in band_rows}),
            "bets": len(band_rows),
            "wins": win["wins"],
            "places": place["wins"],
            "win_hit_rate": win["hit_rate"],
            "place_hit_rate": place["hit_rate"],
            "win_ROI": win["roi"],
            "place_ROI": place["roi"],
            "win_profit": win["profit"],
            "place_profit": place["profit"],
            "average_odds": mean(odds) if odds else None,
            "median_odds": median(odds) if odds else None,
        })
    return records


def summarize_gap_bands(records: list[dict], bins: int = 5) -> list[dict]:
    values = [float(row.get("gap_1_2", 0.0)) for row in records]
    records_by_band = defaultdict(list)
    for row in records:
        records_by_band[gap_band(values, float(row.get("gap_1_2", 0.0)), bins=bins)].append(row)

    result = []
    for band in sorted(records_by_band.keys(), key=lambda item: int(item[1:])):
        rows = records_by_band[band]
        top1_rows = [row for row in rows]
        win = roi_metrics([{"prediction_rank": 1, "is_win": row["top1_is_win"], "win_payout": row["top1_win_payout"], "actual_rank": row["top1_actual_rank"], "odds": row["top1_odds"]} for row in top1_rows], "win")
        place = roi_metrics([{"prediction_rank": 1, "is_place": row["top1_is_place"], "place_payout": row["top1_place_payout"], "actual_rank": row["top1_actual_rank"], "odds": row["top1_odds"]} for row in top1_rows], "place")
        odds = [row["top1_odds"] for row in top1_rows]
        result.append({
            "gap_band": band,
            "sample_size": len(rows),
            "top1_win_rate": mean([row["top1_is_win"] for row in rows]) if rows else None,
            "top1_place_rate": mean([row["top1_is_place"] for row in rows]) if rows else None,
            "win_ROI": win["roi"],
            "place_ROI": place["roi"],
            "average_odds": mean(odds) if odds else None,
            "profit": win["profit"],
        })
    return result


def summarize_popularity_gap_cross(rows: list[dict], gap_bins: int = 5) -> list[dict]:
    all_races = compute_race_level(rows)
    gap_values = [float(row["gap_1_2"]) for row in all_races]
    records = []
    for band in ["1番人気", "2〜3番人気", "4〜6番人気", "7〜9番人気", "10番人気以下"]:
        for gap_band_name in [f"Q{idx}" for idx in range(1, gap_bins + 1)]:
            cell = [row for row in all_races if row["top1_popularity_band"] == band and gap_band(gap_values, float(row["gap_1_2"]), bins=gap_bins) == gap_band_name]
            if not cell:
                continue
            win = roi_metrics([{**row, "is_win": row["top1_is_win"], "win_payout": row["top1_win_payout"], "prediction_rank": 1} for row in cell], "win")
            place = roi_metrics([{**row, "is_place": row["top1_is_place"], "place_payout": row["top1_place_payout"], "prediction_rank": 1} for row in cell], "place")
            odds = [row["top1_odds"] for row in cell]
            records.append({
                "popularity_band": band,
                "gap_band": gap_band_name,
                "sample_size": len(cell),
                "win_hit_rate": win["hit_rate"],
                "place_hit_rate": place["hit_rate"],
                "average_odds": mean(odds) if odds else None,
                "win_ROI": win["roi"],
                "place_ROI": place["roi"],
                "profit": win["profit"],
            })
    return records


def summarize_by_race_class(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        if integer(row.get("prediction_rank"), 0) == 1:
            class_key = row.get("race_class_label") or row.get("class_code") or "UNKNOWN"
            grouped[class_key].append(row)

    records = []
    for label, band_rows in sorted(grouped.items(), key=lambda item: str(item[0])):
        win = roi_metrics(band_rows, "win")
        place = roi_metrics(band_rows, "place")
        records.append({
            "race_class": label,
            "sample_size": len(band_rows),
            "top1_hit_rate": win["hit_rate"],
            "top3_hit_rate": sum(integer(row.get("is_place"), 0) for row in band_rows) / len(band_rows) if band_rows else None,
            "win_ROI": win["roi"],
            "place_ROI": place["roi"],
            "profit": win["profit"],
        })
    return records


def candidate_type_summary(records: list[dict]) -> list[dict]:
    gap_values = [float(row.get("gap_1_2", 0.0)) for row in records]
    thresholds = [0.60, 0.70, 0.80]
    candidates = []
    for threshold in thresholds:
        q = quantile(gap_values, threshold)
        one_clear = [row for row in records if float(row.get("gap_1_2", 0.0)) >= q]
        two_clear = [row for row in records if float(row.get("gap_1_2", 0.0)) < q and float(row.get("gap_2_3", 0.0)) >= q]
        three_clear = [row for row in records if float(row.get("gap_1_2", 0.0)) < q and float(row.get("gap_2_3", 0.0)) < q and float(row.get("gap_1_3", 0.0)) >= q]
        flat = [row for row in records if row not in one_clear and row not in two_clear and row not in three_clear]
        groups = [
            ("ONE_CLEAR", one_clear),
            ("TWO_CLEAR", two_clear),
            ("THREE_CLEAR", three_clear),
            ("FLAT", flat),
        ]
        row = {"candidate_name": f"q{int(threshold * 100)}", "threshold_gap_value": q, "threshold_pct": threshold}
        for kind, subset in groups:
            if not subset:
                row[f"{kind}_sample_size"] = 0
                row[f"{kind}_top1_win_rate"] = None
                row[f"{kind}_top1_place_rate"] = None
                row[f"{kind}_win_ROI"] = None
                row[f"{kind}_place_ROI"] = None
                row[f"{kind}_average_odds"] = None
                row[f"{kind}_profit"] = 0.0
                continue
            win = roi_metrics([{**item, "is_win": item["top1_is_win"], "win_payout": item["top1_win_payout"], "prediction_rank": 1} for item in subset], "win")
            place = roi_metrics([{**item, "is_place": item["top1_is_place"], "place_payout": item["top1_place_payout"], "prediction_rank": 1} for item in subset], "place")
            odds = [item["top1_odds"] for item in subset]
            row[f"{kind}_sample_size"] = len(subset)
            row[f"{kind}_top1_win_rate"] = mean(item["top1_is_win"] for item in subset)
            row[f"{kind}_top1_place_rate"] = mean(item["top1_is_place"] for item in subset)
            row[f"{kind}_win_ROI"] = win["roi"]
            row[f"{kind}_place_ROI"] = place["roi"]
            row[f"{kind}_average_odds"] = mean(odds) if odds else None
            row[f"{kind}_profit"] = win["profit"]
        candidates.append(row)
    return candidates


def summarize_calibration(rows: list[dict]) -> list[dict]:
    bins = [
        ("0～5%", 0.0, 0.05),
        ("5～10%", 0.05, 0.10),
        ("10～15%", 0.10, 0.15),
        ("15～20%", 0.15, 0.20),
        ("20～25%", 0.20, 0.25),
        ("25～30%", 0.25, 0.30),
        ("30%以上", 0.30, 1.0),
    ]
    records = []
    for label, low, high in bins:
        selected = [row for row in rows if low <= float(row.get("predicted_probability", 0.0)) < high or (label == "30%以上" and float(row.get("predicted_probability", 0.0)) >= 0.30)]
        if not selected:
            records.append({"bin": label, "sample_size": 0, "mean_predicted_probability": None, "actual_win_rate": None, "difference": None})
            continue
        preds = [float(row.get("predicted_probability", 0.0)) for row in selected]
        actual = [integer(row.get("is_win"), 0) for row in selected]
        mean_pred = mean(preds)
        actual_rate = mean(actual)
        records.append({
            "bin": label,
            "sample_size": len(selected),
            "mean_predicted_probability": mean_pred,
            "actual_win_rate": actual_rate,
            "difference": actual_rate - mean_pred,
        })
    return records


def summarize_market_edge(rows: list[dict]) -> list[dict]:
    top1_rows = [row for row in rows if integer(row.get("prediction_rank"), 0) == 1]
    records = []
    for label, low, high in [
        ("edge_0_0.05", 0.0, 0.05),
        ("edge_0.05_0.1", 0.05, 0.10),
        ("edge_0.1_plus", 0.10, 1.0),
        ("edge_negative", -1.0, 0.0),
    ]:
        selected = []
        for row in top1_rows:
            edge = float(row.get("edge", 0.0))
            if label == "edge_negative":
                ok = edge < 0.0
            else:
                ok = low <= edge < high
            if ok:
                selected.append(row)
        if not selected:
            records.append({"edge_band": label, "sample_size": 0, "actual_win_rate": None, "win_ROI": None, "profit": 0.0})
            continue
        win = roi_metrics(selected, "win")
        records.append({
            "edge_band": label,
            "sample_size": len(selected),
            "actual_win_rate": win["hit_rate"],
            "win_ROI": win["roi"],
            "profit": win["profit"],
        })
    return records


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def format_roi(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def build_summary(rows: list[dict], output_dir: Path) -> str:
    race_records = compute_race_level(rows)
    popularity_rows = summarize_top1_by_popularity(rows)
    gap_rows = summarize_gap_bands(race_records)
    popularity_gap_rows = summarize_popularity_gap_cross(rows)
    class_rows = summarize_by_race_class(rows)
    calibration_rows = summarize_calibration(rows)
    market_rows = summarize_market_edge(rows)
    type_rows = candidate_type_summary(race_records)

    top1_selected = [row for row in rows if integer(row.get("prediction_rank"), 0) == 1]
    top1_win = roi_metrics(top1_selected, "win")
    top1_place = roi_metrics(top1_selected, "place")
    strongest_popularity = max(popularity_rows, key=lambda item: (item["win_ROI"] if item["win_ROI"] is not None else -999999.0, item["races"])) if popularity_rows else {}
    strongest_gap = max(gap_rows, key=lambda item: (item["win_ROI"] if item["win_ROI"] is not None else -999999.0, item["sample_size"])) if gap_rows else {}

    lines = [
        "# ROI condition analysis",
        "",
        "## Data scope",
        "- Input: existing predictions CSV only; no future result columns were created or re-used for training.",
        "- All analysis is performed on the current backtest output, preserving the same predicted probability, rank, odds, payout, popularity, and race metadata already present in the generated CSV.",
        "- This report is descriptive only; it does not claim a production threshold for betting.",
        "",
        "## A. ROIを最も削っている条件",
        f"- Top1 selections overall: win ROI {format_roi(top1_win['roi'])}, place ROI {format_roi(top1_place['roi'])}, win profit {top1_win['profit']:.0f} yen.",
        f"- 最もROIが悪い人気帯: {strongest_popularity.get('popularity_band', 'N/A')} (win ROI {format_roi(strongest_popularity.get('win_ROI'))}, place ROI {format_roi(strongest_popularity.get('place_ROI'))}, bets {strongest_popularity.get('bets', 0)}).",
        f"- 最もROIが悪い確信度帯: gap band {strongest_gap.get('gap_band', 'N/A')} (win ROI {format_roi(strongest_gap.get('win_ROI'))}, place ROI {format_roi(strongest_gap.get('place_ROI'))}, sample {strongest_gap.get('sample_size', 0)}).",
        "- 一般に、1番人気かつ高確信度の領域は的中率は高くても、オッズが低くなってROIが削られやすい。4〜6番人気と高確信度は、Top1 hit rate と ROI のバランスが比較的良い可能性がある。",
        "",
        "## B. モデルが強い条件",
        f"- 最も強い人気帯は {max(popularity_rows, key=lambda item: item['win_ROI'] if item['win_ROI'] is not None else -999999.0)['popularity_band']} で、win ROI {format_roi(max(popularity_rows, key=lambda item: item['win_ROI'] if item['win_ROI'] is not None else -999999.0)['win_ROI'])} 付近に集中している可能性がある。",
        f"- 最も強い gap band は {max(gap_rows, key=lambda item: item['win_ROI'] if item['win_ROI'] is not None else -999999.0)['gap_band']} で、sample size と ROI を併せて見る必要がある。",
        "- この分析は「chance AND market edge」が同時に成立する領域を見つけるための探索として使うべきで、固定閾値採用には慎重すべき。",
        "",
        "## C. 「当たるけど儲からない」条件",
        "- オッズが低い人気帯・低い差分帯では、Top1 hit rate は上がっていても、回収率の改善が弱い。",
        "- 1番人気の予測1位は娛楽的な『当たりやすさ』を示しても、期待値の高さは低くなりやすい。",
        "- こうした条件を見分けるには、勝率とオッズの両方を確認し、market_probability との差に相関があるかを見る必要がある。",
        "",
        "## D. 「モデルが市場より強い可能性がある」条件",
        "- edge が正であるtop1馬の群では、model probability が market implied probability を上回る可能性があり、ROI improvement を期待できる。",
        f"- 現時点の edge analysis では sample size と成績を併せて見るべき; positive edge のセルは {sum(1 for item in market_rows if item['edge_band'] in {'edge_0_0.05','edge_0.05_0.1','edge_0.1_plus'} and item['sample_size'] > 0)} 件の帯に分布している。",
        "",
        "## E. 見送り候補",
        "- 高確信度であるが ROI が悪化している帯、また sample size が小さく、期間の再現性が弱い帯は見送り候補とするのが安全。",
        "- 断層タイプの候補分析では、ONE_CLEAR / FLAT を分ける閾値が ROI に強く影響するため、いきなり固定しないこと。",
        "",
        "## Files generated",
        f"- Popularity band: {output_dir / 'popularity_band_analysis.csv'}",
        f"- Gap band: {output_dir / 'gap_band_analysis.csv'}",
        f"- Popularity x gap: {output_dir / 'popularity_gap_cross.csv'}",
        f"- Race class: {output_dir / 'race_class_analysis.csv'}",
        f"- Race type candidates: {output_dir / 'race_type_candidates.csv'}",
        f"- Calibration: {output_dir / 'calibration_analysis.csv'}",
        f"- Market edge: {output_dir / 'market_edge_analysis.csv'}",
        "",
        "## Leakage note",
        "- This analysis reads only the generated backtest CSV and never creates new future-aware columns. It does not use target-race results, payout data for model training, or any post-race leakage.",
        "- It is intended to isolate conditions where the model is accurate but not profitable, before any model change is considered.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    input_path = DEFAULT_INPUT
    output_dir = DEFAULT_OUTPUT
    rows = load_predictions(input_path)
    race_records = compute_race_level(rows)

    popularity_rows = summarize_top1_by_popularity(rows)
    gap_rows = summarize_gap_bands(race_records)
    popularity_gap_rows = summarize_popularity_gap_cross(rows)
    class_rows = summarize_by_race_class(rows)
    calibration_rows = summarize_calibration(rows)
    market_rows = summarize_market_edge(rows)
    type_rows = candidate_type_summary(race_records)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "popularity_band_analysis.csv", popularity_rows)
    write_csv(output_dir / "gap_band_analysis.csv", gap_rows)
    write_csv(output_dir / "popularity_gap_cross.csv", popularity_gap_rows)
    write_csv(output_dir / "race_class_analysis.csv", class_rows)
    write_csv(output_dir / "race_type_candidates.csv", type_rows)
    write_csv(output_dir / "calibration_analysis.csv", calibration_rows)
    write_csv(output_dir / "market_edge_analysis.csv", market_rows)
    write_csv(output_dir / "race_level_features.csv", race_records)

    summary_text = build_summary(rows, output_dir)
    (output_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    # Also write a compact result JSON for quick automation use.
    summary_json = {
        "popularity_band_analysis": popularity_rows,
        "gap_band_analysis": gap_rows,
        "popularity_gap_cross": popularity_gap_rows,
        "race_class_analysis": class_rows,
        "race_type_candidates": type_rows,
        "calibration_analysis": calibration_rows,
        "market_edge_analysis": market_rows,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated ROI condition analysis under {output_dir}")
    print(f"Rows read: {len(rows)} | races: {len(race_records)}")


if __name__ == "__main__":
    main()

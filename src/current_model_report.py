#!/usr/bin/env python3
"""現行モデル（CLEANUP_E minus recent3_place_rate, 92特徴量）の直近3ヶ月レポート。

`src/ranker_cleanup_e_no_place_rate_analysis.py` と同一の特徴量構成・学習条件で、
直近3ヶ月分を月次walk-forwardで再評価し、全出走馬の予測値と条件別回収率を出力する。
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pandas as pd

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import (
        CAREER_COUNT_FEATURES,
        DEDUP_MARGIN_FEATURES,
        distance_band,
        odds_band,
        popularity_band,
    )
    from src.ranker_cleanup_e_backtest import ADDED_FEATURES
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf
    from backtest import (
        CAREER_COUNT_FEATURES,
        DEDUP_MARGIN_FEATURES,
        distance_band,
        odds_band,
        popularity_band,
    )
    from ranker_cleanup_e_backtest import ADDED_FEATURES

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "reports" / "current_model_report_2026_09"
EXCLUDED_FEATURE = "recent3_place_rate"
EVAL_START = pd.Timestamp("2026-06-01")
EVAL_END = pd.Timestamp("2026-09-01")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def place_payout_map() -> dict[tuple[str, int], float]:
    key_columns = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    pay_columns = [f"PayFukusyo{index}{suffix}" for index in range(5) for suffix in ("Umaban", "Pay")]
    query = f"SELECT {', '.join(key_columns + pay_columns)} FROM NL_HR_PAY WHERE idYear >= '2012'"
    values: dict[tuple[str, int], float] = {}
    with sqlite3.connect(wf.RACE_DB) as connection:
        for record in connection.execute(query):
            row = dict(zip(key_columns + pay_columns, record))
            race_id = "-".join(str(row[column]).strip() for column in key_columns)
            for index in range(5):
                try:
                    umaban = int(float(row[f"PayFukusyo{index}Umaban"] or 0))
                    payout = float(row[f"PayFukusyo{index}Pay"] or 0)
                except (TypeError, ValueError):
                    continue
                if umaban:
                    values[(race_id, umaban)] = payout
    return values


def load_frame_with_conditions(reduced_features: list[str]) -> tuple[pd.DataFrame, list[str]]:
    identifiers = ["race_id", "date", "horse_id", "horse_name", "actual_rank", "target", "odds", "popularity",
                   "umaban", "race_first_prize", "racecourse", "surface", "distance", "field_size"]
    available = set(pd.read_parquet(wf.CACHE).columns)
    requested = list(dict.fromkeys(identifiers + reduced_features + ADDED_FEATURES))
    frame = pd.read_parquet(wf.CACHE, columns=[column for column in requested if column in available])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[(frame["race_first_prize"] > 8_000_000) & (frame["actual_rank"] > 0) & (frame["odds"] > 0)
                  & (frame["date"] < wf.TEST_END)].copy()
    win_values = wf.payout_map()
    place_values = place_payout_map()
    frame["win_payout"] = [win_values.get((race_id, int(umaban)), 0.0) for race_id, umaban in zip(frame["race_id"], frame["umaban"])]
    frame["place_payout"] = [place_values.get((race_id, int(umaban)), 0.0) for race_id, umaban in zip(frame["race_id"], frame["umaban"])]
    frame["is_win"] = (frame["actual_rank"] == 1).astype(int)
    frame["is_place"] = (frame["actual_rank"] <= 3).astype(int)
    frame.sort_values(["date", "race_id", "horse_id"], inplace=True)
    features = [column for column in reduced_features + ADDED_FEATURES if column in frame.columns]
    return frame.reset_index(drop=True), features


def full_metrics(rows: pd.DataFrame) -> dict:
    metrics = wf.metrics(rows)
    top1 = rows[rows["prediction_rank"] == 1]
    investment = len(top1) * 100
    metrics["top1_place_hit_rate"] = top1["is_place"].mean() if len(top1) else None
    metrics["top1_place_roi"] = top1["place_payout"].sum() / investment * 100 if investment else None
    metrics["top1_place_profit"] = top1["place_payout"].sum() - investment if investment else None
    return metrics


def condition_roi(top1: pd.DataFrame, key: str) -> list[dict]:
    rows = []
    for value, group in top1.groupby(key, observed=True):
        if len(group) == 0:
            continue
        investment = len(group) * 100
        rows.append({
            key: value, "bets": len(group),
            "win_hit_rate": group["is_win"].mean(), "win_roi": group["win_payout"].sum() / investment * 100,
            "place_hit_rate": group["is_place"].mean(), "place_roi": group["place_payout"].sum() / investment * 100,
            "sample_warning": "LOW SAMPLE" if len(group) < 30 else "",
        })
    return sorted(rows, key=lambda row: str(row[key]))


def main() -> None:
    _, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    reduced_features = [feature for feature in dedup_features if feature not in CAREER_COUNT_FEATURES]
    frame, cleanup_e_features = load_frame_with_conditions(reduced_features)
    features = [feature for feature in cleanup_e_features if feature != EXCLUDED_FEATURE]

    months = wf.month_starts(EVAL_START, EVAL_END)
    walk_rows, training_log = wf.monthly_walk_forward(frame, features, months, wf.CALIBRATION_MONTHS)
    walk_rows["distance_band"] = walk_rows["distance"].apply(distance_band)
    walk_rows["popularity_band"] = walk_rows["popularity"].apply(popularity_band)
    walk_rows["odds_band"] = walk_rows["odds"].apply(lambda value: odds_band(value / 10.0))

    overall = full_metrics(walk_rows)
    monthly_rows = [{"month": month, **full_metrics(subset)} for month, subset in walk_rows.groupby(walk_rows["date"].dt.strftime("%Y-%m"))]

    top1 = walk_rows[walk_rows["prediction_rank"] == 1].copy()
    top1["month"] = top1["date"].dt.strftime("%Y-%m")
    roi_by_racecourse = condition_roi(top1, "racecourse")
    roi_by_surface = condition_roi(top1, "surface")
    roi_by_distance = condition_roi(top1, "distance_band")
    roi_by_popularity = condition_roi(top1, "popularity_band")
    roi_by_odds = condition_roi(top1, "odds_band")
    roi_by_month = condition_roi(top1, "month")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "racecourse", "surface", "distance", "field_size", "horse_id", "horse_name",
                      "actual_rank", "target", "odds", "win_odds", "popularity", "ranker_score", "ranker_win_probability",
                      "prediction_rank", "is_win", "win_payout", "is_place", "place_payout",
                      "model_train_end_date", "evaluation_mode"]
    export_rows = walk_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records")
    write_csv(OUTPUT / "predictions_last_3_months.csv", export_rows)
    write_csv(OUTPUT / "monthly_results.csv", monthly_rows)
    write_csv(OUTPUT / "roi_by_racecourse.csv", roi_by_racecourse)
    write_csv(OUTPUT / "roi_by_surface.csv", roi_by_surface)
    write_csv(OUTPUT / "roi_by_distance_band.csv", roi_by_distance)
    write_csv(OUTPUT / "roi_by_popularity_band.csv", roi_by_popularity)
    write_csv(OUTPUT / "roi_by_odds_band.csv", roi_by_odds)
    write_csv(OUTPUT / "roi_by_month.csv", roi_by_month)
    write_csv(OUTPUT / "monthly_training_log.csv", training_log)

    metadata = {"model": "cleanup_e_minus_recent3_place_rate", "feature_count": len(features),
                "eval_start": EVAL_START.strftime("%Y-%m-%d"), "eval_end_exclusive": EVAL_END.strftime("%Y-%m-%d"),
                "calibration_months": wf.CALIBRATION_MONTHS, "prize_filter": "race_first_prize > 8,000,000",
                "prediction_months": [month.strftime("%Y-%m") for month in months], "total_bets_top1": len(top1)}
    (OUTPUT / "metadata.json").write_text(json.dumps({**metadata, "overall": overall}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def pct(value):
        return "N/A" if value is None else f"{value:.2%}"

    def roi_fmt(value):
        return "N/A" if value is None else f"{value:.1f}%"

    lines = ["# 現行モデル 直近3ヶ月レポート", "",
              f"評価期間: {EVAL_START.date()} 〜 {EVAL_END.date()}（対象月: {', '.join(metadata['prediction_months'])}）",
              f"対象: 1着賞金800万円超のレース。単勝100円・複勝100円で予測1位馬にのみ賭けた場合の回収率。",
              f"特徴量数: {len(features)}（詳細は `feature_list.md`）", "",
              "## 全体成績", f"- レース数: {overall['races']} / 出走馬数: {overall['horses']}",
              f"- Brier: {overall['brier']:.6f} / LogLoss: {overall['logloss']:.6f} / AUC: {overall['auc']:.6f}",
              f"- Top1的中率: {pct(overall['top1_hit_rate'])} / Top3的中率: {pct(overall['top3_hit_rate'])}",
              f"- 単勝回収率(Top1): {roi_fmt(overall['top1_win_roi'])}（利益 {overall['top1_profit']:.0f} 円）",
              f"- 複勝回収率(Top1): {roi_fmt(overall['top1_place_roi'])}（利益 {overall['top1_place_profit']:.0f} 円）", "",
              "## 月別成績", "| 月 | レース数 | Top1的中率 | 単勝ROI | 複勝ROI |", "|---|---:|---:|---:|---:|"]
    for row in monthly_rows:
        lines.append(f"| {row['month']} | {row['races']} | {pct(row['top1_hit_rate'])} | {roi_fmt(row['top1_win_roi'])} | {roi_fmt(row['top1_place_roi'])} |")

    lines += ["", "## 競馬場別回収率（予測1位のみ）", "| 競馬場 | 賭け数 | 単勝的中率 | 単勝ROI | 複勝的中率 | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for row in roi_by_racecourse:
        lines.append(f"| {row['racecourse']} | {row['bets']} | {pct(row['win_hit_rate'])} | {roi_fmt(row['win_roi'])} | {pct(row['place_hit_rate'])} | {roi_fmt(row['place_roi'])} {row['sample_warning']} |")

    lines += ["", "## 馬場（芝・ダート）別回収率", "| 馬場 | 賭け数 | 単勝的中率 | 単勝ROI | 複勝的中率 | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for row in roi_by_surface:
        lines.append(f"| {row['surface']} | {row['bets']} | {pct(row['win_hit_rate'])} | {roi_fmt(row['win_roi'])} | {pct(row['place_hit_rate'])} | {roi_fmt(row['place_roi'])} {row['sample_warning']} |")

    lines += ["", "## 距離帯別回収率", "| 距離帯 | 賭け数 | 単勝的中率 | 単勝ROI | 複勝的中率 | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for row in roi_by_distance:
        lines.append(f"| {row['distance_band']} | {row['bets']} | {pct(row['win_hit_rate'])} | {roi_fmt(row['win_roi'])} | {pct(row['place_hit_rate'])} | {roi_fmt(row['place_roi'])} {row['sample_warning']} |")

    lines += ["", "## 人気帯別回収率", "| 人気帯 | 賭け数 | 単勝的中率 | 単勝ROI | 複勝的中率 | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for row in roi_by_popularity:
        lines.append(f"| {row['popularity_band']} | {row['bets']} | {pct(row['win_hit_rate'])} | {roi_fmt(row['win_roi'])} | {pct(row['place_hit_rate'])} | {roi_fmt(row['place_roi'])} {row['sample_warning']} |")

    lines += ["", "## オッズ帯別回収率", "| オッズ帯 | 賭け数 | 単勝的中率 | 単勝ROI | 複勝的中率 | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for row in roi_by_odds:
        lines.append(f"| {row['odds_band']} | {row['bets']} | {pct(row['win_hit_rate'])} | {roi_fmt(row['win_roi'])} | {pct(row['place_hit_rate'])} | {roi_fmt(row['place_roi'])} {row['sample_warning']} |")

    lines += ["", "## 注記",
              "- ROIはサンプル数が少ない条件では統計的有意性を示さない。`LOW SAMPLE`は賭け数30未満。",
              "- `predictions_last_3_months.csv` に評価期間内の全出走馬（Top1に限らない）の予測勝率・確定着順・払戻を出力。",
              "- 学習・キャリブレーション条件は `feature_list.md` の「モデル構成・評価条件」を参照。"]
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), **metadata, "overall": overall}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

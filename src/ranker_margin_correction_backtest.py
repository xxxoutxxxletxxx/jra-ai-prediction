#!/usr/bin/env python3
"""12-month Ranker re-evaluation for the raw-result/margin-correction redesign.

The comparison uses the same monthly expanding-window and calibration procedure for
the pre-change production feature set and the requested post-change set.  Result
columns are retained in the cache, but only as-of historical derived features enter
the Ranker.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pyarrow.parquet as parquet

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import (
        CLEANUP_E_FEATURES,
        CLEANUP_F_PLUS_MARGIN_FEATURES,
    )
except ModuleNotFoundError:  # Supports direct script execution.
    import ranker_walk_forward_backtest as wf
    from backtest import CLEANUP_E_FEATURES, CLEANUP_F_PLUS_MARGIN_FEATURES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "reports" / "ranker_margin_correction_12m"
EXCLUDED_FEATURES = {
    "career_win_rate",
    "career_races",
    "recent3_win_rate",
    "recent3_place_rate",
    "last1_finish",
    "last2_finish",
    "last3_finish",
    "last1_margin",
    "last2_margin",
    "last3_margin",
    "best_margin_last3",
    "mean_margin_last3",
    "weighted_margin_last3",
}


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cache_columns() -> set[str]:
    return set(parquet.ParquetFile(wf.CACHE).schema.names)


def payout_maps() -> tuple[dict[tuple[str, int], float], dict[tuple[str, int], float]]:
    """Read win and place payouts in the same (race_id, umaban) convention as wf."""
    key_columns = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    columns = key_columns + [
        f"PayTansyo{i}{suffix}" for i in range(3) for suffix in ("Umaban", "Pay")
    ] + [f"PayFukusyo{i}{suffix}" for i in range(5) for suffix in ("Umaban", "Pay")]
    wins: dict[tuple[str, int], float] = {}
    places: dict[tuple[str, int], float] = {}
    with sqlite3.connect(wf.RACE_DB) as connection:
        for values in connection.execute(f"SELECT {', '.join(columns)} FROM NL_HR_PAY WHERE idYear >= '2012'"):
            row = dict(zip(columns, values))
            race_id = "-".join(str(row[column]).strip() for column in key_columns)
            for i in range(3):
                try:
                    umaban = int(float(row[f"PayTansyo{i}Umaban"] or 0))
                    payout = float(row[f"PayTansyo{i}Pay"] or 0)
                except (TypeError, ValueError):
                    continue
                if umaban:
                    wins[(race_id, umaban)] = payout
            for i in range(5):
                try:
                    umaban = int(float(row[f"PayFukusyo{i}Umaban"] or 0))
                    payout = float(row[f"PayFukusyo{i}Pay"] or 0)
                except (TypeError, ValueError):
                    continue
                if umaban:
                    places[(race_id, umaban)] = payout
    return wins, places


def load_frame(features: list[str]) -> pd.DataFrame:
    identifiers = [
        "race_id", "date", "horse_id", "horse_name", "actual_rank", "target",
        "odds", "popularity", "umaban", "race_first_prize",
    ]
    available = cache_columns()
    missing = [feature for feature in features if feature not in available]
    if missing:
        raise SystemExit(
            f"Feature cache is missing {missing}. Rebuild it with "
            "`python -m src.build_feature_cache --model F`."
        )
    columns = [column for column in dict.fromkeys(identifiers + features) if column in available]
    frame = pd.read_parquet(wf.CACHE, columns=columns)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[
        (frame["race_first_prize"] > 8_000_000)
        & (frame["actual_rank"] > 0)
        & (frame["odds"] > 0)
        & (frame["date"] < wf.TEST_END)
    ].copy()
    win_values, place_values = payout_maps()
    frame["win_payout"] = [
        win_values.get((race_id, int(umaban)), 0.0)
        for race_id, umaban in zip(frame["race_id"], frame["umaban"])
    ]
    frame["place_payout"] = [
        place_values.get((race_id, int(umaban)), 0.0)
        for race_id, umaban in zip(frame["race_id"], frame["umaban"])
    ]
    frame.sort_values(["date", "race_id", "horse_id"], inplace=True)
    return frame.reset_index(drop=True)


def safe_rate(value: float, denominator: int) -> float | None:
    return value / denominator if denominator else None


def format_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def format_roi(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def roi(payout: float, bets: int) -> float | None:
    """ROI percent for a 100-yen stake (payouts are stored in yen)."""
    return payout / bets if bets else None


def metrics(rows: pd.DataFrame) -> dict:
    top1 = rows[rows["prediction_rank"] == 1].copy()
    return {
        "races": int(rows["race_id"].nunique()),
        "horses": int(len(rows)),
        "top1_hit_rate": float(top1["target"].mean()) if len(top1) else None,
        "top1_win_roi": roi(float(top1["win_payout"].sum()), len(top1)),
        "top1_place_roi": roi(float(top1["place_payout"].sum()), len(top1)),
        "ai_favorite_mean_popularity": float(top1["popularity"].mean()) if len(top1) else None,
    }


def popularity_rows(rows: pd.DataFrame, label: str) -> list[dict]:
    top1 = rows[rows["prediction_rank"] == 1].copy()
    groups = [
        ("1", top1["popularity"] == 1),
        ("2", top1["popularity"] == 2),
        ("3-6", top1["popularity"].between(3, 6)),
        ("7_plus", top1["popularity"] >= 7),
    ]
    output = []
    for name, mask in groups:
        group = top1[mask]
        output.append({
            "variant": label,
            "popularity_group": name,
            "races": int(len(group)),
            "top1_hit_rate": float(group["target"].mean()) if len(group) else None,
            "win_roi": roi(float(group["win_payout"].sum()), len(group)),
            "place_roi": roi(float(group["place_payout"].sum()), len(group)),
            "predicted_win_rate": float(group["ranker_win_probability"].mean()) if len(group) else None,
            "actual_win_rate": float(group["target"].mean()) if len(group) else None,
            "prediction_minus_actual": (
                float(group["ranker_win_probability"].mean() - group["target"].mean())
                if len(group) else None
            ),
        })
    return output


def load_correction_rows() -> pd.DataFrame:
    columns = [
        "race_id", "date", "horse_id", "actual_rank", "race_class_score",
        "blowout_excluded", "blowout_correction_applied",
    ]
    available = cache_columns()
    missing = [column for column in columns if column not in available]
    if missing:
        raise SystemExit(
            f"Feature cache is missing correction columns {missing}. "
            "Rebuild it with `python -m src.build_feature_cache --model F`."
        )
    rows = pd.read_parquet(wf.CACHE, columns=columns)
    rows["date"] = pd.to_datetime(rows["date"])
    return rows[rows["actual_rank"] > 0].sort_values(["horse_id", "date", "race_id"]).reset_index(drop=True)


def correction_outcomes(rows: pd.DataFrame) -> tuple[dict, list[dict]]:
    """Measure next-1/2/3-start wins and same-class-or-higher wins."""
    corrected = rows[
        (rows["blowout_excluded"].astype(bool))
        & (rows["date"] >= wf.TEST_START)
        & (rows["date"] < wf.TEST_END)
    ]
    all_future = {horse: group for horse, group in rows.groupby("horse_id", sort=False)}
    records = []
    for _, source in corrected.iterrows():
        future = all_future.get(source["horse_id"], pd.DataFrame())
        future = future[
            (future["date"] > source["date"]) & (future["race_id"] != source["race_id"])
        ].head(3)
        records.append({
            "horse_id": source["horse_id"],
            "source_race_id": source["race_id"],
            "source_date": source["date"].strftime("%Y-%m-%d"),
            "source_class_score": float(source["race_class_score"]),
            "next_starts_available": int(len(future)),
            **{
                f"wins_within_{n}": int((future.head(n)["actual_rank"] == 1).any())
                for n in (1, 2, 3)
            },
            **{
                f"same_or_higher_class_win_within_{n}": int(
                    (
                        (future.head(n)["actual_rank"] == 1)
                        & (future.head(n)["race_class_score"] >= source["race_class_score"])
                    ).any()
                )
                for n in (1, 2, 3)
            },
        })
    summary = {
        "all_corrected_horse_rows": int(rows["blowout_excluded"].astype(bool).sum()),
        "all_corrected_races": int(rows[rows["blowout_correction_applied"].astype(bool)]["race_id"].nunique()),
        "corrected_horse_rows": int(len(corrected)),
        "corrected_races": int(corrected["race_id"].nunique()) if len(corrected) else 0,
        "correction_rate_rows": safe_rate(
            len(corrected),
            len(rows[(rows["date"] >= wf.TEST_START) & (rows["date"] < wf.TEST_END)]),
        ),
    }
    for n in (1, 2, 3):
        eligible = [record for record in records if record["next_starts_available"] >= n]
        summary[f"next_{n}_start_win_rate"] = safe_rate(
            sum(record[f"wins_within_{n}"] for record in eligible), len(eligible)
        )
        summary[f"same_or_higher_class_win_rate_within_{n}"] = safe_rate(
            sum(record[f"same_or_higher_class_win_within_{n}"] for record in eligible), len(eligible)
        )
        summary[f"eligible_rows_within_{n}"] = len(eligible)
    return summary, records


def serialise_predictions(rows: pd.DataFrame) -> list[dict]:
    columns = [
        "date", "race_id", "horse_id", "horse_name", "actual_rank", "target",
        "odds", "win_odds", "popularity", "ranker_score", "ranker_win_probability",
        "prediction_rank", "win_payout", "place_payout", "model_train_end_date",
        "evaluation_mode",
    ]
    return rows[columns].assign(date=lambda value: value["date"].dt.strftime("%Y-%m-%d")).to_dict("records")


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-evaluate the margin-correction Ranker over 12 months")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    before_features = [
        feature for feature in CLEANUP_E_FEATURES if feature != "recent3_place_rate"
    ]
    after_features = list(dict.fromkeys(CLEANUP_F_PLUS_MARGIN_FEATURES))
    forbidden_after = sorted(set(after_features) & EXCLUDED_FEATURES)
    if forbidden_after:
        raise SystemExit(f"Forbidden raw-result features remain in new Ranker input: {forbidden_after}")
    frame = load_frame(list(dict.fromkeys(before_features + after_features)))
    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    before_rows, before_log = wf.monthly_walk_forward(
        frame, before_features, months, wf.CALIBRATION_MONTHS
    )
    after_rows, after_log = wf.monthly_walk_forward(
        frame, after_features, months, wf.CALIBRATION_MONTHS
    )
    comparison = [
        {"variant": "before_margin_correction", "feature_count": len(before_features), **metrics(before_rows)},
        {"variant": "after_margin_correction", "feature_count": len(after_features), **metrics(after_rows)},
    ]
    popularity = popularity_rows(before_rows, "before_margin_correction") + popularity_rows(
        after_rows, "after_margin_correction"
    )
    correction_summary, correction_records = correction_outcomes(load_correction_rows())
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "predictions_before.csv", serialise_predictions(before_rows))
    write_csv(args.out / "predictions_after.csv", serialise_predictions(after_rows))
    write_csv(args.out / "comparison.csv", comparison)
    write_csv(args.out / "popularity_metrics.csv", popularity)
    write_csv(args.out / "correction_outcomes.csv", correction_records)
    write_csv(args.out / "training_log_before.csv", before_log)
    write_csv(args.out / "training_log_after.csv", after_log)
    (args.out / "correction_summary.json").write_text(
        json.dumps(correction_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metadata = {
        "test_start": wf.TEST_START.strftime("%Y-%m-%d"),
        "test_end_exclusive": wf.TEST_END.strftime("%Y-%m-%d"),
        "before_features": before_features,
        "after_features": after_features,
        "excluded_from_after": sorted(EXCLUDED_FEATURES),
        "threshold_1_to_3_seconds": 0.6,
        "threshold_1_to_2_seconds": 0.5,
        "correction_summary": correction_summary,
    }
    (args.out / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    before, after = comparison
    lines = [
        "# Ranker 着差補正 12か月 walk-forward 再評価",
        "",
        "## 実装",
        "- raw結果読込直後に元の着順・TimeDiffを保持し、`corrected_margin`、`effective_rank`、`blowout_margin_value`を共通生成。",
        "- 1着→3着差0.6秒以上を対象とし、1着→2着差0.5秒以上は1着のみ、それ未満は1・2着を除外して着差を再計算。",
        "- 除外馬の自然な実測差を負の着差として近走パフォーマンスへ反映。",
        "- Ranker入力から career_win_rate / career_races / recent3_win_rate / recent3_place_rate と生の着順・着差系を除外。",
        "- 過去5走の実際の勝利時着差、勝利マージン平均・最大を追加（非勝利走は平均から除外）。",
        "",
        "## 補正件数・その後の成績",
        f"- 全期間の補正対象馬行: {correction_summary['all_corrected_horse_rows']:,}、補正レース: {correction_summary['all_corrected_races']:,}。",
        f"- 評価期間の補正対象馬行: {correction_summary['corrected_horse_rows']:,}、補正レース: {correction_summary['corrected_races']:,}。",
    ]
    for n in (1, 2, 3):
        lines.append(
            f"- {n}走以内: 勝率 {format_pct(correction_summary[f'next_{n}_start_win_rate'])}、"
            f"同クラス以上勝ち上がり率 {format_pct(correction_summary[f'same_or_higher_class_win_rate_within_{n}'])} "
            f"(対象 {correction_summary[f'eligible_rows_within_{n}']:,})"
        )
    lines += [
        "",
        "## 変更前後（2025-09〜2026-08）",
        f"- 変更前 ({before['feature_count']}特徴): Top1 {format_pct(before['top1_hit_rate'])}, 単勝ROI {format_roi(before['top1_win_roi'])}, 複勝ROI {format_roi(before['top1_place_roi'])}, AI本命平均人気 {before['ai_favorite_mean_popularity']:.2f}",
        f"- 変更後 ({after['feature_count']}特徴): Top1 {format_pct(after['top1_hit_rate'])}, 単勝ROI {format_roi(after['top1_win_roi'])}, 複勝ROI {format_roi(after['top1_place_roi'])}, AI本命平均人気 {after['ai_favorite_mean_popularity']:.2f}",
        "",
        "## 人気別 Top1",
        "| variant | 人気帯 | 件数 | 的中率 | 単勝ROI | 複勝ROI | 予測勝率 | 実勝率 | 予測−実績 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {row['variant']} | {row['popularity_group']} | {row['races']} | "
            f"{format_pct(row['top1_hit_rate'])} | {format_roi(row['win_roi'])} | "
            f"{format_roi(row['place_roi'])} | {format_pct(row['predicted_win_rate'])} | "
            f"{format_pct(row['actual_win_rate'])} | {format_pct(row['prediction_minus_actual'])} |"
            for row in popularity
        ],
        "`predicted_win_rate` と `actual_win_rate` の差は予測−実績。詳細は `popularity_metrics.csv`。",
        "",
        "## 出力",
        "- `predictions_before.csv` / `predictions_after.csv`: 同一月次walk-forwardの予測。",
        "- `comparison.csv`、`popularity_metrics.csv`: 指定指標の比較。",
        "- `correction_outcomes.csv` / `correction_summary.json`: 補正対象馬の後続1〜3走と同クラス以上の成績。",
    ]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), "comparison": comparison, "correction": correction_summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

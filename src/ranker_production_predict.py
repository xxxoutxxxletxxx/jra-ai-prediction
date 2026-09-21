#!/usr/bin/env python3
"""Production prediction using the validated margin-correction Ranker."""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES, build_v1_features, load_data
from src.betting_rules import decide_bet, reason_text
from src.ranker_walk_forward_backtest import (
    CALIBRATION_MONTHS,
    forecast_ranker,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "raw" / "race.db"
OUTPUT_DIR = ROOT / "output"
JRA_CODES = {f"{index:02d}" for index in range(1, 11)}
LOGGER = logging.getLogger(__name__)


def _race_first_prize(row: pd.Series) -> float:
    value = row.get("race_first_prize", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _prepare_frame(prediction_start: pd.Timestamp, days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    data, _, _ = load_data(DB_PATH, min_year=2020)
    training_start = (prediction_start - pd.DateOffset(years=5)).date()
    prediction_end = prediction_start + pd.Timedelta(days=days)
    data = [
        row for row in data
        if str(row.get("idJyoCD", "")).zfill(2) in JRA_CODES
        and row["date"] >= training_start
        and row["date"] < prediction_end.date()
    ]
    rows = build_v1_features(data, include_unfinished=True)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("特徴量を生成できるレースデータがありません")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["idJyoCD"].astype(str).str.zfill(2).isin(JRA_CODES)].copy()
    frame = frame[~frame["surface"].astype(str).str.contains("障", na=False)].copy()
    training = frame[
        (frame["date"] < prediction_start)
        & (frame["actual_rank"] > 0)
        & (pd.to_numeric(frame["odds"], errors="coerce") > 0)
        & (frame["headDataKubun"].astype(str) == "7")
        & (frame.apply(_race_first_prize, axis=1) > 8_000_000)
    ].copy()
    upcoming = frame[
        (frame["date"] >= prediction_start)
        & (frame["date"] < prediction_start + pd.Timedelta(days=days))
        & (frame["actual_rank"].fillna(0) <= 0)
        & (frame["Umaban"].fillna(0).astype(int) > 0)
        & frame["horse_name"].astype(str).str.strip().ne("")
        & (frame.apply(_race_first_prize, axis=1) > 8_000_000)
    ].copy()
    return training, upcoming


def _validate_features(training: pd.DataFrame, upcoming: pd.DataFrame) -> None:
    expected = list(RANKER_MARGIN_CORRECTION_FEATURES)
    missing_train = [name for name in expected if name not in training.columns]
    missing_upcoming = [name for name in expected if name not in upcoming.columns]
    if missing_train or missing_upcoming:
        raise RuntimeError(
            f"Ranker特徴量不足: training={missing_train}, upcoming={missing_upcoming}"
        )
    if len(expected) != 86:
        raise RuntimeError(f"検証済みbaselineの特徴量数が86ではありません: {len(expected)}")
    if training[expected].isna().all(axis=0).any():
        missing_values = [name for name in expected if training[name].isna().all()]
        raise RuntimeError(f"学習データのRanker特徴量が全欠損です: {missing_values}")


def predict(prediction_start: pd.Timestamp, days: int = 2) -> pd.DataFrame:
    training, upcoming = _prepare_frame(prediction_start, days)
    _validate_features(training, upcoming)
    if upcoming.empty:
        LOGGER.warning("本日の日付に未確定の対象レースがありません")
        return upcoming

    upcoming, metadata = forecast_ranker(
        training,
        upcoming,
        RANKER_MARGIN_CORRECTION_FEATURES,
        prediction_start,
        CALIBRATION_MONTHS,
        "production_as_of",
    )
    upcoming["predicted_win_probability"] = upcoming["ranker_win_probability"]
    upcoming["ai_rank"] = upcoming["prediction_rank"]
    upcoming["Odds"] = pd.to_numeric(upcoming["odds"], errors="coerce")
    upcoming["popularity"] = pd.to_numeric(upcoming["Ninki"], errors="coerce").fillna(0).astype(int)
    upcoming["calibration_temperature"] = metadata["temperature"]
    upcoming.sort_values(["date", "race_id", "ai_rank"], inplace=True)
    LOGGER.info(
        "Ranker baseline: features=%d, train_horses=%d, races=%d, predictions=%d",
        len(RANKER_MARGIN_CORRECTION_FEATURES),
        metadata["train_horses"],
        upcoming["race_id"].nunique(),
        len(upcoming),
    )
    return upcoming


def write_output(predictions: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    columns = [
        "race_date", "idJyoCD", "競馬場名", "idRaceNum", "Umaban", "Bamei",
        "KisyuCode", "predicted_win_probability", "ai_rank", "Odds", "人気",
        "expected_value", "bet_decision", "bet_reason_code", "bet_reason",
        "ranker_score", "model_train_end_date", "evaluation_mode",
        "calibration_temperature", "feature_count",
    ]
    with (OUTPUT_DIR / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for _, row in predictions.iterrows():
            raw_odds = float(row["Odds"]) if pd.notna(row["Odds"]) else 0.0
            win_odds = raw_odds / 10.0 if raw_odds > 0 else None
            probability = float(row["predicted_win_probability"])
            bet_decision = bet_reason_code = bet_reason = ""
            if int(row["ai_rank"]) == 1:
                should_bet, bet_reason_code = decide_bet(win_odds, probability)
                bet_decision = "BET" if should_bet else "SKIP"
                bet_reason = reason_text(bet_reason_code)
            writer.writerow({
                "race_date": row["date"].date().isoformat(),
                "idJyoCD": str(row["idJyoCD"]).zfill(2),
                "競馬場名": str(row.get("racecourse", "")),
                "idRaceNum": str(row["idRaceNum"]),
                "Umaban": str(int(row["Umaban"])),
                "Bamei": str(row["horse_name"]),
                "KisyuCode": str(row.get("KisyuCode", "")),
                "predicted_win_probability": f"{probability:.6f}",
                "ai_rank": str(int(row["ai_rank"])),
                "Odds": f"{win_odds:.1f}" if win_odds is not None else "",
                "人気": str(int(row["popularity"])),
                "expected_value": f"{probability * win_odds:.6f}" if win_odds is not None else "",
                "bet_decision": bet_decision,
                "bet_reason_code": bet_reason_code,
                "bet_reason": bet_reason,
                "ranker_score": f"{float(row['ranker_score']):.6f}",
                "model_train_end_date": row["model_train_end_date"],
                "evaluation_mode": row["evaluation_mode"],
                "calibration_temperature": row["calibration_temperature"],
                "feature_count": len(RANKER_MARGIN_CORRECTION_FEATURES),
            })
    LOGGER.info("予想出力: %s (%d頭、%dレース)", OUTPUT_DIR / "predictions.csv", len(predictions), predictions["race_id"].nunique())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the validated production Ranker")
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Prediction window start date (YYYY-MM-DD; default: today)",
    )
    parser.add_argument("--days", type=int, default=2, help="Prediction window length")
    args = parser.parse_args()
    if args.days < 1:
        raise SystemExit("--days must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    prediction_start = pd.Timestamp(args.start_date)
    predictions = predict(prediction_start, args.days)
    write_output(predictions)
    if predictions.empty:
        LOGGER.info("本日分の予想対象レースは0件です（DBの出馬表更新が必要です）")


if __name__ == "__main__":
    main()

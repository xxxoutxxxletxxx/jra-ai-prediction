#!/usr/bin/env python3
"""Production prediction using the validated margin-correction Ranker."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES, build_v1_features, load_data, valid_result
from src.ranker_walk_forward_backtest import (
    CALIBRATION_MONTHS,
    encode_train_test,
    ranker_scores,
    select_temperature,
    softmax_by_race,
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


def _prepare_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    data, _, _ = load_data(DB_PATH)
    rows = build_v1_features(data, include_unfinished=True)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("特徴量を生成できるレースデータがありません")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["idJyoCD"].astype(str).str.zfill(2).isin(JRA_CODES)].copy()
    today = pd.Timestamp(date.today())
    training = frame[
        (frame["date"] < today)
        & (frame["actual_rank"] > 0)
        & (frame["headDataKubun"].astype(str) == "7")
        & (frame.apply(_race_first_prize, axis=1) > 8_000_000)
    ].copy()
    upcoming = frame[
        (frame["date"] >= today)
        & (frame["date"] < today + pd.Timedelta(days=2))
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
    if len(expected) != 95:
        raise RuntimeError(f"検証済みbaselineの特徴量数が95ではありません: {len(expected)}")
    if training[expected].isna().all(axis=0).any():
        missing_values = [name for name in expected if training[name].isna().all()]
        raise RuntimeError(f"学習データのRanker特徴量が全欠損です: {missing_values}")


def predict() -> pd.DataFrame:
    training, upcoming = _prepare_frame()
    _validate_features(training, upcoming)
    if upcoming.empty:
        LOGGER.warning("本日の日付に未確定の対象レースがありません")
        return upcoming

    today = pd.Timestamp(date.today())
    calibration_start = today - pd.DateOffset(months=CALIBRATION_MONTHS)
    calibration_train = training[training["date"] < calibration_start]
    calibration = training[(training["date"] >= calibration_start) & (training["date"] < today)]
    temperature = 1.0
    if not calibration_train.empty and not calibration.empty:
        calibration_scores = ranker_scores(calibration_train, calibration, RANKER_MARGIN_CORRECTION_FEATURES)
        temperature, _ = select_temperature(calibration, calibration_scores)

    scores = ranker_scores(training, upcoming, RANKER_MARGIN_CORRECTION_FEATURES)
    upcoming = upcoming.copy()
    upcoming["ranker_score"] = scores
    upcoming["predicted_win_probability"] = softmax_by_race(
        scores, upcoming["race_id"], temperature
    )
    upcoming["ai_rank"] = (
        upcoming.groupby("race_id")["predicted_win_probability"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    upcoming["Odds"] = pd.to_numeric(upcoming["odds"], errors="coerce")
    upcoming["popularity"] = pd.to_numeric(upcoming["Ninki"], errors="coerce").fillna(0).astype(int)
    upcoming.sort_values(["date", "race_id", "ai_rank"], inplace=True)
    LOGGER.info(
        "Ranker baseline: features=%d, train_horses=%d, races=%d, predictions=%d",
        len(RANKER_MARGIN_CORRECTION_FEATURES),
        len(training),
        upcoming["race_id"].nunique(),
        len(upcoming),
    )
    return upcoming


def write_output(predictions: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    columns = [
        "race_date", "idJyoCD", "競馬場名", "idRaceNum", "Umaban", "Bamei",
        "KisyuCode", "predicted_win_probability", "ai_rank", "Odds", "人気",
    ]
    with (OUTPUT_DIR / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(columns) + "\n")
        for _, row in predictions.iterrows():
            values = [
                row["date"].date().isoformat(),
                str(row["idJyoCD"]).zfill(2),
                str(row.get("racecourse", "")),
                str(row["idRaceNum"]),
                str(int(row["Umaban"])),
                str(row["horse_name"]),
                str(row.get("KisyuCode", "")),
                f"{row['predicted_win_probability']:.6f}",
                str(int(row["ai_rank"])),
                str(float(row["Odds"])) if pd.notna(row["Odds"]) else "",
                str(int(row["popularity"])),
            ]
            handle.write(",".join(f'"{value}"' if "," in value else value for value in values) + "\n")
    LOGGER.info("予想出力: %s (%d頭、%dレース)", OUTPUT_DIR / "predictions.csv", len(predictions), predictions["race_id"].nunique())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    predictions = predict()
    write_output(predictions)
    if predictions.empty:
        LOGGER.info("本日分の予想対象レースは0件です（DBの出馬表更新が必要です）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build public RACEVERSE condition data from the checked-in backtest CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "reports/raceverse/weekly_5y_202109_202609/condition_analysis/roi_by_combination.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/data/raceverse/conditions.json"
CONDITION_COLUMNS = ("クラス", "競馬場", "芝ダート", "距離", "馬場")
REQUIRED_COLUMNS = {
    "model",
    *CONDITION_COLUMNS,
    "bets",
    "win_roi_pct",
    "win_roi_first_half_pct",
    "win_roi_second_half_pct",
}
MIN_BETS = 30
# 重賞は開催数が少ないため、少ない件数の条件も掲載する
GRADED_CLASSES = {"G1", "G2", "G3"}
MIN_BETS_GRADED = 10


def _number(value: str, column: str, line_number: int) -> float | None:
    if not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {column} on CSV line {line_number}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Invalid {column} on CSV line {line_number}: {value!r}")
    return number


def build_payload(input_path: Path) -> dict:
    conditions = []
    with input_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"Missing columns in {input_path}: {', '.join(sorted(missing_columns))}")

        for line_number, row in enumerate(reader, start=2):
            try:
                bets = int(row["bets"])
            except ValueError as exc:
                raise ValueError(f"Invalid bets on CSV line {line_number}: {row['bets']!r}") from exc
            roi = _number(row["win_roi_pct"], "win_roi_pct", line_number)
            if roi is None:
                raise ValueError(f"Missing win_roi_pct on CSV line {line_number}")
            minimum = MIN_BETS_GRADED if row["クラス"].strip() in GRADED_CLASSES else MIN_BETS
            if bets < minimum or roi <= 100:
                continue

            model = row["model"].strip()
            if model != "formation":
                continue
            values = {column: row[column].strip() for column in CONDITION_COLUMNS}
            if not model or any(not value for value in values.values()):
                raise ValueError(f"Missing condition label on CSV line {line_number}")
            conditions.append(
                {
                    "model": model,
                    "class": values["クラス"],
                    "track": values["競馬場"],
                    "surface": values["芝ダート"],
                    "distance": values["距離"],
                    "going": values["馬場"],
                    "bets": bets,
                    "win_roi_pct": roi,
                    "win_roi_first_half_pct": _number(
                        row["win_roi_first_half_pct"], "win_roi_first_half_pct", line_number
                    ),
                    "win_roi_second_half_pct": _number(
                        row["win_roi_second_half_pct"], "win_roi_second_half_pct", line_number
                    ),
                }
            )

    conditions.sort(
        key=lambda row: (
            -row["win_roi_pct"],
            -row["bets"],
            row["model"],
            row["class"],
            row["track"],
            row["surface"],
            row["distance"],
            row["going"],
        )
    )
    return {
        "evaluation_period": "2021年9月〜2026年8月",
        "minimum_bets": MIN_BETS,
        "minimum_bets_graded": MIN_BETS_GRADED,
        "conditions": conditions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_payload(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['conditions'])} conditions to {args.output}")


if __name__ == "__main__":
    main()

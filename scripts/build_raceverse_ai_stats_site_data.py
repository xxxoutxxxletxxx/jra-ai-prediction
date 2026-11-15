#!/usr/bin/env python3
"""Build public AI performance data for Tokyo, Kyoto, and Fukushima."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "reports/raceverse/weekly_5y_202109_202609"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/data/raceverse/ai-stats.json"
DEFAULT_DB = PROJECT_ROOT / "data/raw/race.db"
TRACKS = {"05": "東京", "08": "京都", "03": "福島"}
ODDS_BANDS = [
    (0.0, 2.0, "2.0倍未満"),
    (2.0, 3.0, "2.0〜3.0倍未満"),
    (3.0, 5.0, "3.0〜5.0倍未満"),
    (5.0, 10.0, "5.0〜10.0倍未満"),
    (10.0, 20.0, "10.0〜20.0倍未満"),
    (20.0, 30.0, "20.0〜30.0倍未満"),
    (30.0, 50.0, "30.0〜50.0倍未満"),
    (50.0, 100.0, "50.0〜100.0倍未満"),
    (100.0, math.inf, "100.0倍以上"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def number(row: dict[str, str], key: str, *, default: float | None = None) -> float:
    value = row.get(key, "").strip()
    if not value and default is not None:
        return default
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {key}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Invalid {key}: {value!r}")
    return result


def summarize(rows: list[dict]) -> dict:
    count = len(rows)
    returned = sum(row["payout"] for row in rows)
    return {
        "bets": count,
        "hits": sum(row["payout"] > 0 for row in rows),
        "roi_pct": returned / (count * 100) * 100 if count else None,
    }


def read_win_payouts(db_path: Path, race_ids: set[str]) -> dict[tuple[str, int], float]:
    years = sorted({int(race_id.split("-")[0]) for race_id in race_ids})
    if not years:
        return {}
    keys = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
    payout_columns = [
        f"PayTansyo{i}{suffix}"
        for i in range(3)
        for suffix in ("Umaban", "Pay")
    ]
    query = (
        f"SELECT {', '.join(keys + payout_columns)} FROM NL_HR_PAY "
        "WHERE idYear >= ? AND idYear <= ?"
    )
    payouts = {}
    with sqlite3.connect(db_path) as connection:
        for row in connection.execute(query, (str(years[0]), str(years[-1]))):
            race_id = "-".join(str(value).strip() for value in row[:6])
            if race_id not in race_ids:
                continue
            for index in range(3):
                try:
                    horse_number = int(float(row[6 + index * 2] or 0))
                    amount = float(row[7 + index * 2] or 0)
                except (TypeError, ValueError):
                    continue
                if horse_number:
                    payouts[(race_id, horse_number)] = amount
    return payouts


def build_payload(input_dir: Path, db_path: Path | None = None) -> dict:
    race_rows = read_csv(input_dir / "race_level.csv")
    race_info = {}
    for row in race_rows:
        race_id = row["race_id"]
        if race_id in race_info:
            raise ValueError(f"Duplicate race metadata: {race_id}")
        race_info[race_id] = {
            "track": str(row["track"]).zfill(2),
            "date": row["date"],
        }

    predictions = [
        row for row in read_csv(input_dir / "predictions.csv")
        if row.get("level") == "formation"
    ]
    by_race: dict[str, list[dict]] = defaultdict(list)
    for row in predictions:
        by_race[row["race_id"]].append(row)

    payouts = (
        read_win_payouts(db_path, set(by_race))
        if db_path is not None
        else None
    )
    selected_by_track: dict[str, list[dict]] = {code: [] for code in TRACKS}
    for race_id, runners in by_race.items():
        metadata = race_info.get(race_id)
        if metadata is None:
            raise ValueError(f"Missing race metadata: {race_id}")
        track = metadata["track"]
        if track not in TRACKS:
            continue
        ranked = sorted(
            runners,
            key=lambda row: (-number(row, "p_cal"), int(row["umaban"])),
        )
        chosen = ranked[0]
        odds = number(chosen, "win_odds_reference")
        if odds <= 0:
            raise ValueError(f"Invalid win odds for {race_id}: {odds}")
        probability = number(chosen, "p_cal")
        if not 0 <= probability <= 1:
            raise ValueError(f"Invalid calibrated win probability for {race_id}: {probability}")
        target = int(number(chosen, "target"))
        if target not in (0, 1):
            raise ValueError(f"Invalid winner target for {race_id}: {target}")
        is_winner = target == 1
        if is_winner and payouts is not None:
            payout_key = (race_id, int(chosen["umaban"]))
            if payout_key not in payouts or payouts[payout_key] <= 0:
                raise ValueError(f"Missing official win payout for {race_id}/{chosen['umaban']}")
            payout = payouts[payout_key]
        else:
            payout = odds * 100 if is_winner else 0.0
        selected_by_track[track].append({
            "date": metadata["date"],
            "year": int(metadata["date"][:4]),
            "odds": odds,
            "ev": probability * odds,
            "payout": payout,
        })

    combinations = read_csv(input_dir / "condition_analysis/roi_by_combination.csv")
    tracks = []
    for code, name in TRACKS.items():
        bets = sorted(selected_by_track[code], key=lambda row: row["date"])
        yearly_groups: dict[int, list[dict]] = defaultdict(list)
        odds_groups: list[list[dict]] = [[] for _ in ODDS_BANDS]
        ev_groups: dict[int, list[dict]] = defaultdict(list)
        for bet in bets:
            yearly_groups[bet["year"]].append(bet)
            for index, (lower, upper, _) in enumerate(ODDS_BANDS):
                if lower <= bet["odds"] < upper:
                    odds_groups[index].append(bet)
                    break
            ev_bucket = math.floor((bet["ev"] + 1e-10) * 10)
            ev_groups[ev_bucket].append(bet)

        conditions = []
        for row in combinations:
            if row["model"] != "formation" or row["競馬場"] != name:
                continue
            conditions.append({
                "class": row["クラス"],
                "surface": row["芝ダート"],
                "distance": row["距離"],
                "going": row["馬場"],
                "bets": int(row["bets"]),
                "win_hits": int(row["win_hits"]),
                "win_hit_rate_pct": number(row, "win_hit_rate_pct"),
                "win_roi_pct": number(row, "win_roi_pct"),
                "place_roi_pct": number(row, "place_roi_pct"),
            })
        conditions.sort(key=lambda row: (
            row["class"], row["surface"], row["distance"], row["going"]
        ))

        ev_bands = []
        for bucket in range(20):
            lower = bucket / 10
            upper = (bucket + 1) / 10
            group = ev_groups.get(bucket, [])
            summary = summarize(group)
            ev_bands.append({
                "label": f"{lower:.1f}以上{upper:.1f}未満",
                **summary,
                "mean_ev": sum(row["ev"] for row in group) / len(group) if group else None,
            })
        high_ev = [
            row for bucket, group in ev_groups.items() if bucket >= 20 for row in group
        ]
        if high_ev:
            ev_bands.append({
                "label": "2.0以上",
                **summarize(high_ev),
                "mean_ev": sum(row["ev"] for row in high_ev) / len(high_ev),
            })

        tracks.append({
            "code": code,
            "name": name,
            "overall": summarize(bets),
            "conditions": conditions,
            "yearly": [
                {"year": year, **summarize(group)}
                for year, group in sorted(yearly_groups.items())
            ],
            "odds_bands": [
                {"label": label, **summarize(group)}
                for (_, _, label), group in zip(ODDS_BANDS, odds_groups)
            ],
            "ev_bands": ev_bands,
        })

    dates = [row["date"] for rows in selected_by_track.values() for row in rows]
    return {
        "evaluation_period": f"{min(dates)}〜{max(dates)}" if dates else "",
        "model": "formation",
        "tracks": tracks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.db.is_file():
        raise FileNotFoundError(f"Official payout database not found: {args.db}")
    payload = build_payload(args.input_dir, args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote AI performance data to {args.output}")


if __name__ == "__main__":
    main()

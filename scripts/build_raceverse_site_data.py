#!/usr/bin/env python3
"""Build static-site JSON from the latest RACEVERSE per-race reports."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "reports" / "raceverse"
DEFAULT_DB = PROJECT_ROOT / "data" / "raw" / "race.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "data" / "raceverse" / "latest.json"
TRACK_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
PACE_LABELS = {
    "VERY_FAST": "超ハイ", "FAST": "ハイ", "MIDDLE": "ミドル",
    "SLOW": "スロー", "VERY_SLOW": "超スロー",
}
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def parse_race_id(race_id: str) -> tuple[str, str, int]:
    parts = race_id.split("-")
    if len(parts) != 6 or len(parts[1]) != 4:
        raise ValueError(f"Unexpected RACEVERSE race_id: {race_id}")
    date = f"{parts[0]}-{parts[1][:2]}-{parts[1][2:]}"
    track = parts[2].zfill(2)
    return date, track, int(parts[5])


def date_label(date_text: str) -> str:
    day = datetime.strptime(date_text, "%Y-%m-%d")
    return f"{day.year}/{day.month:02d}/{day.day:02d}({WEEKDAYS[day.weekday()]})"


def read_reports(report_dir: Path) -> list[dict]:
    paths = sorted(report_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No RACEVERSE reports found in {report_dir}")

    reports = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        race = payload.get("race", {})
        if race.get("engine") != "RACEVERSE" or race.get("version") != "0.6":
            raise ValueError(f"Unexpected model metadata in {path}")
        if not payload.get("horses"):
            raise ValueError(f"No predicted horses in {path}")
        reports.append(payload)
    return reports


def race_metadata(db_path: Path, dates: set[str]) -> tuple[int, dict[str, dict]]:
    date_keys = sorted(date.replace("-", "") for date in dates)
    placeholders = ",".join("?" for _ in date_keys)
    track_placeholders = ",".join("?" for _ in TRACK_NAMES)
    query = f"""
        SELECT DISTINCT ra.idYear, ra.idMonthDay, ra.idJyoCD, ra.idKaiji,
               ra.idNichiji, ra.idRaceNum, ra.headDataKubun, ra.headMakeDate,
               ra.Kyori, ra.TrackCD
        FROM NL_RA_RACE AS ra
        JOIN NL_SE_RACE_UMA AS se
          ON ra.idYear = se.idYear
         AND ra.idMonthDay = se.idMonthDay
         AND ra.idJyoCD = se.idJyoCD
         AND ra.idKaiji = se.idKaiji
         AND ra.idNichiji = se.idNichiji
         AND ra.idRaceNum = se.idRaceNum
        WHERE ra.idYear || ra.idMonthDay IN ({placeholders})
          AND ra.idJyoCD IN ({track_placeholders})
          AND CAST(se.KakuteiJyuni AS INTEGER) = 0
          AND CAST(se.Umaban AS INTEGER) > 0
        ORDER BY ra.headMakeDate DESC
    """
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(query, [*date_keys, *TRACK_NAMES]).fetchall()

    race_keys: set[str] = set()
    confirmed_keys: set[str] = set()
    metadata: dict[str, dict] = {}
    for year, month_day, track, kaiji, nichiji, race_num, status, _, distance, track_code in rows:
        code = int(track_code or 0)
        if not 10 <= code <= 29:
            continue
        race_id = "-".join(map(str, (year, month_day, track, kaiji, nichiji, race_num)))
        race_keys.add(race_id)
        if str(status).strip() == "7":
            confirmed_keys.add(race_id)
        if race_id not in metadata:
            surface = "芝" if 10 <= code <= 22 else "ダート" if 23 <= code <= 29 else "障害"
            metadata[race_id] = {
                "distance_m": int(distance) if distance else None,
                "surface": surface,
            }

    scheduled_count = len(race_keys - confirmed_keys)
    return scheduled_count, metadata


def build_payload(report_dir: Path, db_path: Path) -> dict:
    reports = read_reports(report_dir)
    dates = {parse_race_id(r["race"]["race_id"])[0] for r in reports}
    scheduled_count, metadata = race_metadata(db_path, dates)
    grouped: dict[str, dict[str, dict[int, dict]]] = {}

    for payload in reports:
        race = payload["race"]
        race_id = race["race_id"]
        date, track, race_num = parse_race_id(race_id)
        if race_id not in metadata:
            raise ValueError(f"Race missing from the local race DB: {race_id}")
        pace = race.get("pace_display_probabilities") or {}
        likely_pace = max(pace, key=pace.get) if pace else None
        horses = []
        for horse in payload["horses"]:
            probability = horse.get("win_probability_calibrated")
            if probability is None:
                probability = horse.get("win_probability_raw")
            probability = float(probability)
            if not 0 <= probability <= 1:
                raise ValueError(f"Invalid win probability for {race_id}/{horse.get('umaban')}")
            name = str(horse.get("horse_name") or "").strip()
            if not name:
                raise ValueError(f"Missing horse name for {race_id}/{horse.get('umaban')}")
            horses.append({
                "umaban": int(horse["umaban"]),
                "name": name,
                "win_probability": probability,
                "top3_probability": float(horse["top3_probability"]),
            })
        horses.sort(key=lambda horse: (-horse["win_probability"], horse["umaban"]))
        if len({horse["umaban"] for horse in horses}) != len(horses):
            raise ValueError(f"Duplicate horse numbers in {race_id}")

        race_entry = {
            "race_num": race_num,
            **metadata[race_id],
            "simulations": int(race["simulations"]),
            "pace_label": PACE_LABELS.get(likely_pace, "未推定"),
            "pace_probability": float(pace.get(likely_pace, 0)) if likely_pace else None,
            "expected_winning_time_sec": race.get("expected_winning_time_sec"),
            "predicted_early_split_mean_sec": race.get("predicted_early_split_mean_sec"),
            "early_section_m": race.get("early_section_m"),
            "horses": horses,
        }
        grouped.setdefault(date, {}).setdefault(track, {})[race_num] = race_entry

    date_entries = []
    for date in sorted(grouped):
        tracks = []
        for track in sorted(grouped[date]):
            races = [
                grouped[date][track][race_num]
                for race_num in sorted(grouped[date][track])
            ]
            tracks.append({
                "code": track,
                "name": TRACK_NAMES[track],
                "races": races,
            })
        date_entries.append({
            "date": date,
            "label": date_label(date),
            "tracks": tracks,
        })

    prediction_count = sum(
        len(track["races"])
        for date in date_entries
        for track in date["tracks"]
    )
    return {
        "engine": "RACEVERSE",
        "version": "0.6",
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="minutes"),
        "model_as_of": max(report["race"]["model_as_of"] for report in reports),
        "simulations_per_race": min(report["race"]["simulations"] for report in reports),
        "scheduled_race_count": scheduled_count,
        "predicted_race_count": prediction_count,
        "not_predicted_race_count": max(0, scheduled_count - prediction_count),
        "dates": date_entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=None)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report_dir = args.reports_dir
    if report_dir is None:
        candidates = sorted(REPORT_ROOT.glob("predict_*"))
        if not candidates:
            raise FileNotFoundError(f"No prediction report directory under {REPORT_ROOT}")
        report_dir = candidates[-1]

    payload = build_payload(report_dir, args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"RACEVERSE site data: {payload['predicted_race_count']}/"
        f"{payload['scheduled_race_count']} races -> {args.output}"
    )


if __name__ == "__main__":
    main()

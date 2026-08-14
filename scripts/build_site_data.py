#!/usr/bin/env python3
"""
predictions.csv から GitHub Pages 用の Web サイトデータ (JSON) を生成する。

出力:
  docs/data/latest.json               ... 最新の predictions.csv 全体（複数日程を含む）
  docs/data/archive/{date}.json       ... 開催日ごとの予測結果（蓄積）
  docs/data/archive/index.json        ... archive の日付一覧（蓄積）

使い方:
  python3 scripts/build_site_data.py
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PREDICTIONS_CSV = PROJECT_ROOT / "output" / "predictions.csv"
DOCS_DATA_DIR = PROJECT_ROOT / "docs" / "data"
ARCHIVE_DIR = DOCS_DATA_DIR / "archive"
LATEST_JSON = DOCS_DATA_DIR / "latest.json"
ARCHIVE_INDEX_JSON = ARCHIVE_DIR / "index.json"

JRA_COURSE_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def date_label(date_str):
    """'2026-08-15' -> '2026/08/15(土)'"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.year}/{d.month:02d}/{d.day:02d}({WEEKDAY_JP[d.weekday()]})"


def parse_float_or_none(value):
    """空文字・NaN・0 を「未取得」として None を返す（Odds/expected_valueの安全変換）"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    try:
        num = float(text)
    except (TypeError, ValueError):
        return None
    if num == 0.0:
        return None
    return num


def load_predictions(csv_path):
    if not csv_path.exists():
        raise FileNotFoundError(f"predictions.csv が見つかりません: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("predictions.csv にデータがありません")

    return rows


def build_horse_entry(row):
    try:
        umaban = int(str(row.get("Umaban", "0")).strip())
    except (TypeError, ValueError):
        umaban = 0

    try:
        ai_rank = int(str(row.get("ai_rank", "0")).strip())
    except (TypeError, ValueError):
        ai_rank = 0

    try:
        score = float(row.get("predicted_win_probability", 0) or 0)
    except (TypeError, ValueError):
        score = 0.0

    odds = parse_float_or_none(row.get("Odds"))
    expected_value = parse_float_or_none(row.get("expected_value")) if odds is not None else None

    return {
        "umaban": umaban,
        "bamei": row.get("Bamei", ""),
        "kisyu_code": row.get("KisyuCode", ""),
        "score": round(score, 4),
        "rank": ai_rank,
        "odds": odds,
        "expected_value": expected_value,
    }


def build_date_structure(date_str, date_rows):
    """1開催日分のデータを { recommendation, tracks } 構造に変換"""
    tracks = {}
    for row in date_rows:
        jyo_cd = str(row.get("idJyoCD", "")).strip().zfill(2)
        jyo_name = row.get("競馬場名") or JRA_COURSE_NAMES.get(jyo_cd, jyo_cd)
        race_num = str(int(str(row.get("idRaceNum", "0")).strip()))

        track = tracks.setdefault(jyo_cd, {"name": jyo_name, "races": {}})
        race_list = track["races"].setdefault(race_num, [])
        race_list.append(build_horse_entry(row))

    # 各レースを AI順位順にソート
    for track in tracks.values():
        for race_num, horses in track["races"].items():
            horses.sort(key=lambda h: (h["rank"] if h["rank"] else 999))

    # 推奨馬 = AIスコア最大の馬
    best_row = max(date_rows, key=lambda r: float(r.get("predicted_win_probability", 0) or 0))
    best_jyo_cd = str(best_row.get("idJyoCD", "")).strip().zfill(2)
    best_jyo_name = best_row.get("競馬場名") or JRA_COURSE_NAMES.get(best_jyo_cd, best_jyo_cd)
    recommendation = {
        "jyo_cd": best_jyo_cd,
        "jyo_name": best_jyo_name,
        "race_num": str(int(str(best_row.get("idRaceNum", "0")).strip())),
        **build_horse_entry(best_row),
    }

    return {
        "label": date_label(date_str),
        "recommendation": recommendation,
        "tracks": tracks,
    }


def main():
    rows = load_predictions(PREDICTIONS_CSV)

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # 日付ごとにグループ化
    rows_by_date = {}
    for row in rows:
        date_str = row.get("race_date", "").strip()
        if not date_str:
            continue
        rows_by_date.setdefault(date_str, []).append(row)

    if not rows_by_date:
        raise ValueError("predictions.csv に有効な race_date が見つかりません")

    updated_at = datetime.now().strftime("%Y/%m/%d %H:%M")

    latest_dates = {}
    for date_str in sorted(rows_by_date.keys()):
        date_structure = build_date_structure(date_str, rows_by_date[date_str])
        latest_dates[date_str] = date_structure

        # archive/{date}.json を保存（同日は上書き、既存の他日は残す）
        archive_payload = {
            "updated_at": updated_at,
            "date": date_str,
            **date_structure,
        }
        archive_path = ARCHIVE_DIR / f"{date_str}.json"
        with archive_path.open("w", encoding="utf-8") as f:
            json.dump(archive_payload, f, ensure_ascii=False, indent=2)

    # latest.json 保存（今回の全開催日を含む）
    latest_payload = {
        "updated_at": updated_at,
        "dates": latest_dates,
    }
    with LATEST_JSON.open("w", encoding="utf-8") as f:
        json.dump(latest_payload, f, ensure_ascii=False, indent=2)

    # archive/index.json をマージ更新（過去の日付を消さない）
    existing_index = {}
    if ARCHIVE_INDEX_JSON.exists():
        try:
            with ARCHIVE_INDEX_JSON.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
            for entry in existing_data.get("dates", []):
                existing_index[entry["date"]] = entry
        except (json.JSONDecodeError, KeyError):
            existing_index = {}

    for date_str, date_structure in latest_dates.items():
        race_count = sum(len(t["races"]) for t in date_structure["tracks"].values())
        horse_count = sum(
            len(horses) for t in date_structure["tracks"].values() for horses in t["races"].values()
        )
        existing_index[date_str] = {
            "date": date_str,
            "label": date_structure["label"],
            "race_count": race_count,
            "horse_count": horse_count,
        }

    sorted_index_dates = sorted(existing_index.keys(), reverse=True)
    index_payload = {
        "updated_at": updated_at,
        "dates": [existing_index[d] for d in sorted_index_dates],
    }
    with ARCHIVE_INDEX_JSON.open("w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False, indent=2)

    # 検証ログ
    print("=" * 60)
    print("サイトデータ生成 完了")
    print("=" * 60)
    print(f"対象日: {', '.join(sorted(rows_by_date.keys()))}")
    for date_str in sorted(rows_by_date.keys()):
        tracks = latest_dates[date_str]["tracks"]
        venue_names = [t["name"] for t in tracks.values()]
        race_count = sum(len(t["races"]) for t in tracks.values())
        horse_count = len(rows_by_date[date_str])
        print(f"  {date_str}: 競馬場={venue_names} レース数={race_count} 出走馬数={horse_count}")
    print(f"archiveに生成された日付: {sorted_index_dates}")
    print(f"latest.json: {LATEST_JSON}")
    print(f"archive dir: {ARCHIVE_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

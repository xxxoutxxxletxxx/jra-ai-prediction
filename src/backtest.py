#!/usr/bin/env python3
"""独立した時系列バックテスト実行器。

現行の統計モデル（馬ごとの過去勝率）を再学習しながら評価する。
本番の race_predict.py は import せず、評価対象と予測時点をこのモジュールで管理する。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean

try:
    from sklearn.metrics import log_loss, roc_auc_score
except ImportError:  # pragma: no cover - requirements.txt installs scikit-learn
    log_loss = roc_auc_score = None

plt = None
if os.environ.get("BACKTEST_ENABLE_PLOTS") == "1":
    try:
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        plt = None


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "raw" / "race.db"
DEFAULT_OUT = ROOT / "reports" / "backtest"
JYO_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
RACE_KEY = ("idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum")
OUTPUT_FIELDS = [
    "date", "race_id", "racecourse", "race_number", "surface", "distance", "horse_id",
    "horse_name", "actual_rank", "predicted_probability", "prediction_rank", "odds",
    "popularity", "win_payout", "place_payout", "sex", "age", "jockey", "trainer",
    "weight", "gate", "field_size", "is_win", "is_place", "ai_vs_favorite",
]
LEAK_COLUMNS = [
    "KakuteiJyuni", "NyusenJyuni", "Time", "TimeDiff", "HaronTimeL3", "HaronTimeL4",
    "Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c", "Honsyokin", "Fukasyokin", "IJyoCD",
    "ChakusaCD", "headDataKubun",
]
V1_FEATURES = [
    "career_races", "career_wins", "career_win_rate", "career_places", "career_place_rate",
    "recent3_win_rate", "recent3_place_rate", "recent5_win_rate", "recent5_place_rate",
    "races_last_180d", "races_last_365d", "last1_finish", "last2_finish", "last3_finish",
    "last1_margin", "last2_margin", "last3_margin", "best_margin_last3", "mean_margin_last3",
    "weighted_margin_last3", "last1_winner_strength", "last2_winner_strength", "last3_winner_strength",
    "last1_field_strength", "last2_field_strength", "last3_field_strength",
    "margin_x_winner_strength", "margin_x_field_strength", "last1_distance", "last2_distance", "last3_distance",
    "current_distance", "field_size",
]


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def number(value: object, default: float = 0.0) -> float:
    try:
        return float(text(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def integer(value: object, default: int = 0) -> int:
    try:
        return int(float(text(value)))
    except (TypeError, ValueError):
        return default


def race_key(row: dict) -> tuple[str, ...]:
    return tuple(text(row.get(column)) for column in RACE_KEY)


def race_id(row: dict) -> str:
    return "-".join(race_key(row))


def race_date(row: dict) -> date | None:
    year, month_day = integer(row.get("idYear")), text(row.get("idMonthDay")).zfill(4)
    try:
        return date(year, int(month_day[:2]), int(month_day[2:]))
    except (ValueError, TypeError):
        return None


def month_start(value: date) -> date:
    return value.replace(day=1)


def shift_month(value: date, offset: int) -> date:
    index = value.year * 12 + value.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def get_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def read_table(connection: sqlite3.Connection, table: str, wanted: list[str], min_year: int | None = None) -> list[dict]:
    available = get_columns(connection, table)
    columns = [column for column in wanted if column in available]
    if not columns:
        return []
    where = f" WHERE idYear >= {int(min_year)}" if min_year is not None and "idYear" in available else ""
    query = f"SELECT {', '.join(columns)} FROM {table}{where}"
    return [dict(zip(columns, row)) for row in connection.execute(query)]


def load_data(db_path: Path, min_year: int = 2012) -> tuple[list[dict], dict[tuple[str, ...], dict], dict]:
    """結果・レース・払戻を読み込む。列追加のあるDBにも対応する。"""
    connection = sqlite3.connect(db_path)
    se_columns = list(RACE_KEY) + [
        "Wakuban", "Umaban", "KettoNum", "Bamei", "SexCD", "Barei", "KisyuCode",
        "ChokyoCode", "TozaiCD", "Futan", "BaTaijyu", "Odds", "Ninki", "KakuteiJyuni",
        "NyusenJyuni", "headDataKubun",
    ] + LEAK_COLUMNS
    ra_columns = list(RACE_KEY) + [
        "Kyori", "TrackCD", "CourseKubunCD", "GradeCD", "JyokenInfoSyubetuCD",
        "SyussoTosu", "NyusenTosu",
    ]
    se_rows = read_table(connection, "NL_SE_RACE_UMA", se_columns, min_year)
    ra_rows = read_table(connection, "NL_RA_RACE", ra_columns, min_year)
    pay_columns = list(RACE_KEY) + [
        f"PayTansyo{i}{suffix}" for i in range(3) for suffix in ("Umaban", "Pay")
    ] + [f"PayFukusyo{i}{suffix}" for i in range(5) for suffix in ("Umaban", "Pay")]
    pay_rows = read_table(connection, "NL_HR_PAY", pay_columns, min_year)
    connection.close()
    races = {race_key(row): row for row in ra_rows}
    pays = {race_key(row): row for row in pay_rows}
    merged = []
    for row in se_rows:
        row = dict(row)
        row.update({f"race_{key}": value for key, value in races.get(race_key(row), {}).items()})
        row["date"] = race_date(row)
        if row["date"] is not None:
            merged.append(row)
    return merged, pays, {"se_columns": set(se_rows[0]) if se_rows else set(), "pay_rows": len(pay_rows)}


def valid_result(row: dict) -> bool:
    rank = integer(row.get("KakuteiJyuni"))
    return text(row.get("headDataKubun")) == "7" and 1 <= rank <= 99


def payout(pay_row: dict | None, kind: str, umaban: int) -> float:
    if not pay_row or not umaban:
        return 0.0
    prefix = "PayTansyo" if kind == "win" else "PayFukusyo"
    count = 3 if kind == "win" else 5
    for index in range(count):
        if integer(pay_row.get(f"{prefix}{index}Umaban")) == umaban:
            return number(pay_row.get(f"{prefix}{index}Pay"))
    return 0.0


def surface(row: dict) -> str:
    track = text(row.get("race_TrackCD") or row.get("TrackCD"))
    if track[:1] in {"1", "2", "3", "4", "5", "6", "7", "8"}:
        return "芝"
    if track[:1] in {"9", "0"}:
        return "ダート"
    value = text(row.get("CourseKubunCD") or row.get("race_CourseKubunCD"))
    return {"1": "芝", "2": "ダート", "3": "障害"}.get(value, "不明")


def distance_band(distance: int) -> str:
    if distance <= 1200:
        return "～1200m"
    if distance <= 1600:
        return "1300～1600m"
    if distance <= 2000:
        return "1700～2000m"
    if distance <= 2400:
        return "2100～2400m"
    return "2500m～"


def bin_label(probability: float) -> str:
    if probability < 0.05:
        return "0～5%"
    if probability < 0.10:
        return "5～10%"
    if probability < 0.20:
        return "10～20%"
    if probability < 0.30:
        return "20～30%"
    if probability < 0.40:
        return "30～40%"
    return "40%以上"


def popularity_band(popularity: int) -> str:
    if popularity == 1:
        return "1番人気"
    if popularity <= 3:
        return "2～3番人気"
    if popularity <= 6:
        return "4～6番人気"
    return "7番人気以下"


def odds_band(odds: float) -> str:
    if odds < 3:
        return "～2.9"
    if odds < 5:
        return "3.0～4.9"
    if odds < 10:
        return "5.0～9.9"
    if odds < 20:
        return "10.0～19.9"
    return "20.0～"


def train_scores(training: list[dict]) -> dict[str, tuple[int, int]]:
    scores = defaultdict(lambda: [0, 0])
    for row in training:
        if valid_result(row):
            horse = text(row.get("KettoNum"))
            if horse:
                scores[horse][0] += integer(row.get("KakuteiJyuni")) == 1
                scores[horse][1] += 1
    return dict(scores)


def probability(row: dict, scores: dict[str, tuple[int, int]], field_size: int) -> float:
    wins, races = scores.get(text(row.get("KettoNum")), (0, 0))
    value = wins / races if races else 1 / max(field_size, 1)
    return min(0.99, max(0.001, value))


def prediction_reason(row: dict, scores: dict[str, tuple[int, int]], field_size: int,
                      favorite_row: dict | None, ai_probability: float) -> tuple[str, str]:
    wins, races = scores.get(text(row.get("KettoNum")), (0, 0))
    if races == 0:
        return "NO_HISTORY", "過去の確定出走履歴がないため、出走頭数による基準確率"
    if favorite_row and row is favorite_row:
        return "FAVORITE", "1番人気馬と同じ馬"
    favorite_probability = probability(favorite_row, scores, field_size) if favorite_row else 0.0
    if ai_probability > favorite_probability:
        return "HIGHER_HISTORY_WIN_RATE", "1番人気馬より過去勝率が高い"
    if ai_probability == favorite_probability:
        return "TIE_BREAK_UMABAN", "過去勝率が同率のため馬番の小さい順"
    return "MODEL_SCORE", "過去勝率を主スコアとして評価"


def evaluate(data: list[dict], pays: dict, start: date, end: date) -> list[dict]:
    confirmed = [row for row in data if valid_result(row) and start <= row["date"] < end]
    months = sorted({month_start(row["date"]) for row in confirmed})
    output = []
    for evaluation_month in months:
        training = [row for row in data if valid_result(row) and row["date"] < evaluation_month]
        scores = train_scores(training)
        month_rows = [row for row in confirmed if month_start(row["date"]) == evaluation_month]
        grouped = defaultdict(list)
        for row in month_rows:
            grouped[race_key(row)].append(row)
        for horses in grouped.values():
            field_size = len(horses)
            ranked = sorted(horses, key=lambda item: (-probability(item, scores, field_size), integer(item.get("Umaban"))))
            favorite_candidates = [item for item in horses if integer(item.get("Ninki")) == 1]
            favorite_row = favorite_candidates[0] if favorite_candidates else None
            favorite_ai_rank = next((index for index, item in enumerate(ranked, 1) if item is favorite_row), 0)
            favorite_probability = probability(favorite_row, scores, field_size) if favorite_row else 0.0
            for rank, row in enumerate(ranked, 1):
                actual = integer(row.get("KakuteiJyuni"))
                umaban = integer(row.get("Umaban"))
                odds = number(row.get("Odds"))
                popularity = integer(row.get("Ninki"))
                wins, races = scores.get(text(row.get("KettoNum")), (0, 0))
                predicted = probability(row, scores, field_size)
                reason_code, reason = prediction_reason(row, scores, field_size, favorite_row, predicted)
                output.append({
                    "date": row["date"].isoformat(), "race_id": race_id(row),
                    "racecourse": JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD"))),
                    "race_number": integer(row.get("idRaceNum")), "surface": surface(row),
                    "distance": integer(row.get("race_Kyori") or row.get("Kyori")),
                    "horse_id": text(row.get("KettoNum")), "horse_name": text(row.get("Bamei")),
                    "actual_rank": actual, "predicted_probability": predicted,
                    "prediction_rank": rank, "odds": odds, "popularity": popularity,
                    "historical_wins": wins, "historical_races": races,
                    "historical_win_rate": wins / races if races else None,
                    "favorite_ai_rank": favorite_ai_rank,
                    "favorite_probability": favorite_probability if favorite_row else None,
                    "probability_margin_vs_favorite": predicted - favorite_probability if favorite_row else None,
                    "reason_code": reason_code, "prediction_reason": reason,
                    "win_payout": payout(pays.get(race_key(row)), "win", umaban),
                    "place_payout": payout(pays.get(race_key(row)), "place", umaban),
                    "sex": text(row.get("SexCD")), "age": integer(row.get("Barei")),
                    "jockey": text(row.get("KisyuCode")), "trainer": text(row.get("ChokyoCode")),
                    "weight": number(row.get("Futan")), "gate": integer(row.get("Wakuban")),
                    "field_size": field_size, "is_win": int(actual == 1), "is_place": int(1 <= actual <= 3),
                    "ai_vs_favorite": int(popularity > 1 and rank == 1),
                })
    return output


def margin_value(row: dict) -> float | None:
    """着差はDBのTimeDiffを優先。ChakusaCDの意味は資料不足のため数値化しない。"""
    value = text(row.get("TimeDiff"))
    if value == "":
        return None
    parsed = number(value, float("nan"))
    return None if math.isnan(parsed) else max(0.0, parsed)


def class_code(row: dict) -> str:
    grade = text(row.get("race_GradeCD"))
    condition = text(row.get("race_JyokenInfoSyubetuCD"))
    return f"grade:{grade or 'unknown'}|condition:{condition or 'unknown'}"


def build_v1_features(data: list[dict]) -> list[dict]:
    """日付順に一度だけ走査し、各行のas_of_date時点特徴量を作る。"""
    ordered = sorted((row for row in data if valid_result(row)), key=lambda row: (row["date"], race_key(row), integer(row.get("Umaban"))))
    histories = defaultdict(list)
    stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})
    features = []
    races = defaultdict(list)
    for row in ordered:
        races[race_key(row)].append(row)
    for key in sorted(races, key=lambda item: (race_date(races[item][0]), item)):
        horses = races[key]
        date_value = horses[0]["date"]
        prior_stats = {text(row.get("KettoNum")): dict(stats[text(row.get("KettoNum"))]) for row in horses}
        field_values = []
        for row in horses:
            current = prior_stats.get(text(row.get("KettoNum")), {"races": 0, "wins": 0, "places": 0})
            field_values.append(current["wins"] / current["races"] if current["races"] else 0.0)
        field_strength = mean(field_values) if field_values else 0.0
        winner = next((row for row in horses if integer(row.get("KakuteiJyuni")) == 1), None)
        winner_stat = prior_stats.get(text(winner.get("KettoNum")), {"races": 0, "wins": 0, "places": 0}) if winner else {"races": 0, "wins": 0, "places": 0}
        winner_strength = winner_stat["wins"] / winner_stat["races"] if winner_stat["races"] else 0.0
        for row in horses:
            horse = text(row.get("KettoNum"))
            current = prior_stats.get(horse, {"races": 0, "wins": 0, "places": 0})
            past = histories[horse][-5:][::-1]
            recent3 = past[:3]
            recent5 = past[:5]
            margins = [item["margin"] for item in past if item["margin"] is not None]
            values = {
                "as_of_date": date_value.isoformat(), "race_id": race_id(row), "horse_id": horse,
                "target": int(integer(row.get("KakuteiJyuni")) == 1), "date": date_value,
                "racecourse": JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD"))),
                "surface": surface(row), "distance": integer(row.get("race_Kyori") or row.get("Kyori")),
                "class_code": class_code(row), "grade_code": text(row.get("race_GradeCD")) or "unknown",
                "condition_code": text(row.get("race_JyokenInfoSyubetuCD")) or "unknown",
                "popularity": integer(row.get("Ninki")), "odds": number(row.get("Odds")),
                "actual_rank": integer(row.get("KakuteiJyuni")), "umaban": integer(row.get("Umaban")),
                "horse_name": text(row.get("Bamei")), "field_size": len(horses),
                "career_races": current["races"], "career_wins": current["wins"],
                "career_win_rate": current["wins"] / current["races"] if current["races"] else 0.0,
                "career_places": current["places"], "career_place_rate": current["places"] / current["races"] if current["races"] else 0.0,
                "recent3_win_rate": mean(item["win"] for item in recent3) if recent3 else 0.0,
                "recent3_place_rate": mean(item["place"] for item in recent3) if recent3 else 0.0,
                "recent5_win_rate": mean(item["win"] for item in recent5) if recent5 else 0.0,
                "recent5_place_rate": mean(item["place"] for item in recent5) if recent5 else 0.0,
                "races_last_180d": sum((date_value - item["date"]).days <= 180 for item in histories[horse]),
                "races_last_365d": sum((date_value - item["date"]).days <= 365 for item in histories[horse]),
                "last1_finish": recent3[0]["finish"] if len(recent3) > 0 else 0,
                "last2_finish": recent3[1]["finish"] if len(recent3) > 1 else 0,
                "last3_finish": recent3[2]["finish"] if len(recent3) > 2 else 0,
                "last1_margin": recent3[0]["margin"] if len(recent3) > 0 and recent3[0]["margin"] is not None else 0.0,
                "last2_margin": recent3[1]["margin"] if len(recent3) > 1 and recent3[1]["margin"] is not None else 0.0,
                "last3_margin": recent3[2]["margin"] if len(recent3) > 2 and recent3[2]["margin"] is not None else 0.0,
                "best_margin_last3": min(margins[:3]) if margins[:3] else 0.0,
                "mean_margin_last3": mean(margins[:3]) if margins[:3] else 0.0,
                "weighted_margin_last3": sum(item["margin"] * weight for item, weight in zip(recent3, (0.5, 0.3, 0.2)) if item["margin"] is not None),
                "last1_winner_strength": recent3[0]["winner_strength"] if len(recent3) > 0 else 0.0,
                "last2_winner_strength": recent3[1]["winner_strength"] if len(recent3) > 1 else 0.0,
                "last3_winner_strength": recent3[2]["winner_strength"] if len(recent3) > 2 else 0.0,
                "last1_field_strength": recent3[0]["field_strength"] if len(recent3) > 0 else 0.0,
                "last2_field_strength": recent3[1]["field_strength"] if len(recent3) > 1 else 0.0,
                "last3_field_strength": recent3[2]["field_strength"] if len(recent3) > 2 else 0.0,
                "margin_x_winner_strength": (recent3[0]["margin"] * recent3[0]["winner_strength"] if recent3 and recent3[0]["margin"] is not None else 0.0),
                "margin_x_field_strength": (recent3[0]["margin"] * recent3[0]["field_strength"] if recent3 and recent3[0]["margin"] is not None else 0.0),
                "last1_distance": recent3[0]["distance"] if len(recent3) > 0 else 0,
                "last2_distance": recent3[1]["distance"] if len(recent3) > 1 else 0,
                "last3_distance": recent3[2]["distance"] if len(recent3) > 2 else 0,
                "last1_class": recent3[0]["class_code"] if len(recent3) > 0 else "unknown",
                "last2_class": recent3[1]["class_code"] if len(recent3) > 1 else "unknown",
                "last3_class": recent3[2]["class_code"] if len(recent3) > 2 else "unknown",
                "current_distance": integer(row.get("race_Kyori") or row.get("Kyori")),
            }
            features.append(values)
        for row in horses:
            horse = text(row.get("KettoNum"))
            stats[horse]["races"] += 1
            stats[horse]["wins"] += int(integer(row.get("KakuteiJyuni")) == 1)
            stats[horse]["places"] += int(1 <= integer(row.get("KakuteiJyuni")) <= 3)
            histories[horse].append({"date": date_value, "finish": integer(row.get("KakuteiJyuni")), "margin": margin_value(row),
                                     "win": int(integer(row.get("KakuteiJyuni")) == 1), "place": int(1 <= integer(row.get("KakuteiJyuni")) <= 3),
                                     "winner_strength": winner_strength, "field_strength": field_strength,
                                     "distance": integer(row.get("race_Kyori") or row.get("Kyori")), "class_code": class_code(row)})
    return features


def evaluate_v1(data: list[dict], pays: dict, start: date, end: date) -> tuple[list[dict], list[dict]]:
    try:
        import lightgbm as lgb
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("v1にはLightGBMが必要です。.venv/bin/python -m src.backtest ... を使用してください。") from exc
    feature_rows = build_v1_features(data)
    trainable = [row for row in feature_rows if row["date"] < start]
    evaluation = [row for row in feature_rows if start <= row["date"] < end]
    months = sorted({month_start(row["date"]) for row in evaluation})
    output, importance = [], defaultdict(lambda: {"gain": 0.0, "split": 0.0})
    for month in months:
        train = [row for row in trainable if row["date"] < month]
        test = [row for row in evaluation if month_start(row["date"]) == month]
        if not train or not test or len({row["target"] for row in train}) < 2:
            continue
        categorical = ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"]
        columns = V1_FEATURES + categorical
        train_df = pd.DataFrame(train)[columns]
        test_df = pd.DataFrame(test)[columns]
        combined = pd.concat([train_df, test_df], ignore_index=True)
        combined = pd.get_dummies(combined, columns=categorical, dummy_na=True)
        train_matrix = combined.iloc[:len(train)].astype(float)
        test_matrix = combined.iloc[len(train):].astype(float)
        original_columns = list(train_matrix.columns)
        safe_columns = [f"f_{index}" for index in range(len(original_columns))]
        train_matrix.columns = safe_columns
        test_matrix.columns = safe_columns
        model = lgb.LGBMClassifier(n_estimators=180, learning_rate=0.04, num_leaves=15, max_depth=5,
                                   min_child_samples=80, reg_lambda=2.0, verbosity=-1, random_state=42)
        model.fit(train_matrix, [row["target"] for row in train])
        for name, gain, split in zip(original_columns, model.booster_.feature_importance("gain"), model.booster_.feature_importance("split")):
            importance[name]["gain"] += float(gain); importance[name]["split"] += float(split)
        probabilities = model.predict_proba(test_matrix)[:, 1]
        grouped = defaultdict(list)
        for row, prob in zip(test, probabilities):
            grouped[row["race_id"]].append((row, float(min(0.999, max(0.001, prob)))))
        for race_rows in grouped.values():
            ranked = sorted(race_rows, key=lambda item: (-item[1], item[0]["umaban"]))
            for rank, (row, prob) in enumerate(ranked, 1):
                umaban = row["umaban"]
                pay_row = pays.get(tuple(row["race_id"].split("-")))
                output.append({**row, "predicted_probability": prob, "prediction_rank": rank,
                               "race_number": integer(row["race_id"].split("-")[-1]), "win_payout": payout(pay_row, "win", umaban),
                               "place_payout": payout(pay_row, "place", umaban), "is_win": row["target"],
                               "is_place": int(1 <= row["actual_rank"] <= 3), "ai_vs_favorite": int(row["popularity"] > 1 and rank == 1),
                               "odds": row["odds"], "reason_code": "V1_LIGHTGBM",
                               "prediction_reason": "LightGBM v1:近走着差・レース格コード・相手強度・基礎能力"})
    return output, [{"feature": name, **values} for name, values in sorted(importance.items(), key=lambda item: item[1]["gain"], reverse=True)]


def betting(rows: list[dict], predicate=lambda row: row["prediction_rank"] == 1) -> dict:
    selected = [row for row in rows if predicate(row)]
    def one(kind: str) -> dict:
        hit_key, payout_key = ("is_win", "win_payout") if kind == "win" else ("is_place", "place_payout")
        investment = len(selected) * 100
        returned = sum(row[payout_key] for row in selected)
        return {"races": len(selected), "wins": sum(row[hit_key] for row in selected),
                "hit_rate": sum(row[hit_key] for row in selected) / len(selected) if selected else None,
                "investment": investment, "payout": returned,
                "roi": returned / investment * 100 if investment else None, "profit": returned - investment}
    return {"win": one("win"), "place": one("place")}


def metrics(rows: list[dict]) -> dict:
    if not rows:
        return {"races": 0, "logloss": None, "brier_score": None, "roc_auc": None, "top1_hit_rate": None, "top3_hit_rate": None}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)
    top1 = sum(any(r["prediction_rank"] == 1 and r["is_win"] for r in values) for values in grouped.values())
    top3 = sum(any(r["prediction_rank"] <= 3 and r["is_win"] for r in values) for values in grouped.values())
    y = [row["is_win"] for row in rows]
    p = [row["predicted_probability"] for row in rows]
    clipped = [min(1 - 1e-15, max(1e-15, value)) for value in p]
    logloss_value = -mean(actual * math.log(predicted) + (1 - actual) * math.log(1 - predicted)
                           for actual, predicted in zip(y, clipped))
    positives = sum(y)
    negatives = len(y) - positives
    ordered = sorted(zip(p, y), key=lambda item: item[0])
    positive_rank_sum = sum(index for index, (_, actual) in enumerate(ordered, 1) if actual)
    auc_value = ((positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
                 if positives and negatives else None)
    return {"races": len(grouped), "horses": len(rows),
            "logloss": logloss_value,
            "brier_score": mean((actual - predicted) ** 2 for actual, predicted in zip(y, p)),
            "roc_auc": auc_value,
            "top1_hit_rate": top1 / len(grouped), "top3_hit_rate": top3 / len(grouped)}


def aggregate(rows: list[dict], key_fields: list[str]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        if row["prediction_rank"] == 1:
            groups[tuple(row[field] for field in key_fields)].append(row)
    result = []
    for key, values in sorted(groups.items(), key=lambda item: tuple(str(x) for x in item[0])):
        bets = betting(values, lambda row: True)
        result.append({**dict(zip(key_fields, key)), "races": len(values), "wins": sum(row["is_win"] for row in values),
                       "win_rate": mean(row["is_win"] for row in values), "win_ROI": bets["win"]["roi"],
                       "place_hit_rate": mean(row["is_place"] for row in values), "place_ROI": bets["place"]["roi"],
                       "sample_warning": "LOW SAMPLE" if len(values) < 30 else ""})
    return result


def calibration(rows: list[dict]) -> list[dict]:
    labels = ["0～5%", "5～10%", "10～20%", "20～30%", "30～40%", "40%以上"]
    result = []
    for label in labels:
        values = [row for row in rows if bin_label(row["predicted_probability"]) == label]
        result.append({"bin": label, "predictions": len(values),
                       "mean_predicted_probability": mean(row["predicted_probability"] for row in values) if values else None,
                       "actual_win_rate": mean(row["is_win"] for row in values) if values else None})
    return result


def max_drawdown(rows: list[dict]) -> dict:
    result = {}
    ordered = sorted((row for row in rows if row["prediction_rank"] == 1), key=lambda row: (row["date"], row["race_id"]))
    for kind, payout_key in (("win", "win_payout"), ("place", "place_payout")):
        balance = peak = 0.0
        drawdown = 0.0
        losing = longest = 0
        for row in ordered:
            balance += row[payout_key] - 100
            peak = max(peak, balance)
            drawdown = max(drawdown, peak - balance)
            hit = row["is_win"] if kind == "win" else row["is_place"]
            losing = 0 if hit else losing + 1
            longest = max(longest, losing)
        result[kind] = {"final_profit": balance, "max_drawdown": drawdown, "max_losing_streak": longest}
    return result


def spearman(rows: list[dict]) -> float | None:
    values = [(row["prediction_rank"], row["popularity"]) for row in rows if row["prediction_rank"] and row["popularity"]]
    if len(values) < 2:
        return None
    def ranks(items):
        ordered = sorted(items)
        return {value: index + 1 for index, value in enumerate(ordered)}
    ai, fav = zip(*values)
    ar, fr = ranks(ai), ranks(fav)
    n = len(values)
    return 1 - 6 * sum((ar[a] - fr[f]) ** 2 for a, f in values) / (n * (n * n - 1))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict], output: Path, metadata: dict, feature_importance: list[dict] | None = None) -> None:
    rows = [{**row, "date": row["date"].isoformat() if isinstance(row.get("date"), date) else row["date"]} for row in rows]
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "predictions.csv", rows)
    monthly = []
    for month in sorted({row["date"][:7] for row in rows}):
        month_rows = [row for row in rows if row["date"].startswith(month)]
        bets = betting(month_rows)
        monthly.append({"month": month, "races": bets["win"]["races"], "top1_win_rate": bets["win"]["hit_rate"],
                        "win_ROI": bets["win"]["roi"], "place_ROI": bets["place"]["roi"]})
    total_bets = betting(rows)
    monthly.append({"month": "TOTAL", "races": total_bets["win"]["races"],
                    "top1_win_rate": total_bets["win"]["hit_rate"], "win_ROI": total_bets["win"]["roi"],
                    "place_ROI": total_bets["place"]["roi"]})
    write_csv(output / "monthly.csv", monthly)
    for name, keys in (("by_racecourse", ["racecourse"]), ("by_surface", ["surface"]),
                       ("by_distance", ["distance"]), ("by_popularity", ["popularity"]), ("by_odds", ["odds"]),
                       ("by_condition", ["racecourse", "surface", "distance"])):
        values = rows
        if name == "by_distance":
            values = [{**row, "distance": distance_band(row["distance"])} for row in rows]
        elif name == "by_popularity":
            values = [{**row, "popularity": popularity_band(row["popularity"])} for row in rows]
        elif name == "by_odds":
            values = [{**row, "odds": odds_band(row["odds"])} for row in rows]
        elif name == "by_condition":
            values = [{**row, "distance": distance_band(row["distance"])} for row in rows]
        write_csv(output / f"{name}.csv", aggregate(values, keys))
    calibration_rows = calibration(rows)
    write_csv(output / "calibration.csv", calibration_rows)
    if feature_importance is not None:
        write_csv(output / "feature_importance.csv", feature_importance)
    class_values = [{**row, "class": row.get("class_code", "unknown")} for row in rows]
    write_csv(output / "by_class.csv", aggregate(class_values, ["class"]))
    margin_values = [{**row, "margin_bin": ("0" if row.get("best_margin_last3", 0) == 0 else "0.01-0.3" if row.get("best_margin_last3", 0) <= 0.3 else "0.31-0.8" if row.get("best_margin_last3", 0) <= 0.8 else "0.81+")} for row in rows]
    write_csv(output / "by_recent_margin.csv", aggregate(margin_values, ["margin_bin"]))
    strength_values = [{**row, "winner_strength_bin": "low" if row.get("last1_winner_strength", 0) < 0.1 else "high",
                        "field_strength_bin": "low" if row.get("last1_field_strength", 0) < 0.1 else "high"} for row in rows]
    write_csv(output / "by_strength.csv", aggregate(strength_values, ["winner_strength_bin", "field_strength_bin"]))
    overall = metrics(rows)
    bets = betting(rows)
    favorite = betting(rows, lambda row: row["popularity"] == 1)
    ai_not_favorite = betting(rows, lambda row: row["prediction_rank"] == 1 and row["popularity"] >= 2)
    risk = max_drawdown(rows)
    condition_rows = aggregate([{**row, "distance": distance_band(row["distance"])} for row in rows],
                               ["racecourse", "surface", "distance"])
    sufficient = [row for row in condition_rows if row["races"] >= 30]
    strong = sorted(sufficient, key=lambda row: (row["win_rate"], row["races"]), reverse=True)[:10]
    weak = sorted(sufficient, key=lambda row: (row["win_rate"], -row["races"]))[:10]
    reason_counts = defaultdict(int)
    for row in rows:
        if row["prediction_rank"] == 1 and row["popularity"] >= 2:
            reason_counts[row["reason_code"]] += 1
    reason_examples = [row for row in rows if row["prediction_rank"] == 1 and row["popularity"] >= 2][:10]
    summary = {"metadata": metadata, "overall": overall, "betting": bets, "favorite": favorite,
               "ai_rank_1_not_favorite": ai_not_favorite, "risk": risk, "calibration": calibration_rows,
               "spearman_ai_popularity": spearman(rows), "monthly": monthly,
               "strong_conditions": strong, "weak_conditions": weak,
               "ai_not_favorite_reasons": {"counts": dict(reason_counts), "examples": reason_examples,
                                           "model_rule": "historical_wins / historical_races; no-history uses 1 / field_size; ties use smaller Umaban"},
               "plots": {"available": bool(plt), "calibration": bool(plt and rows),
                         "cumulative_profit": bool(plt and rows),
                         "note": "matplotlibが利用できる場合のみPNGを生成"},
               "leakage_review": {"excluded_result_columns": LEAK_COLUMNS,
                                  "features": "過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。",
                                  "odds_popularity": "DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。",
                                  "class_codes": "GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。",
                                  "margin": "TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。"}}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary_md(output / "summary.md", summary)
    if plt and rows:
        calibration_plot(output / "calibration.png", calibration_rows)
        profit_plot(output / "cumulative_profit.png", rows)


def write_summary_md(path: Path, summary: dict) -> None:
    overall, bets = summary["overall"], summary["betting"]
    def pct(value): return "N/A" if value is None else f"{value:.2%}"
    def roi(value): return "N/A" if value is None else f"{value:.1f}%"
    lines = ["# Backtest Report", "", "## Overall Performance", f"- Races: {overall['races']}",
             f"- LogLoss: {overall['logloss']}", f"- Brier Score: {overall['brier_score']}", f"- ROC-AUC: {overall['roc_auc']}",
             f"- Top1 hit rate: {pct(overall['top1_hit_rate'])}", f"- Top3 hit rate: {pct(overall['top3_hit_rate'])}", "",
             "## Betting Performance", f"- Win: {bets['win']['races']} races, hit {pct(bets['win']['hit_rate'])}, ROI {roi(bets['win']['roi'])}, profit {bets['win']['profit']:.0f} yen",
             f"- Place: {bets['place']['races']} races, hit {pct(bets['place']['hit_rate'])}, ROI {roi(bets['place']['roi'])}, profit {bets['place']['profit']:.0f} yen", "",
             "## Monthly Performance", "| Month | Races | Top1 Win Rate | Win ROI | Place ROI |", "|---|---:|---:|---:|---:|"]
    if summary["metadata"].get("features"):
        lines += ["", "## v1 Features", "- " + ", ".join(summary["metadata"]["features"]),
                  "- " + summary["metadata"].get("categorical_handling", ""),
                  "- " + summary["metadata"].get("class_method", "")]
    for row in summary["monthly"]:
        lines.append(f"| {row['month']} | {row['races']} | {pct(row['top1_win_rate'])} | {roi(row['win_ROI'])} | {roi(row['place_ROI'])} |")
    lines += ["", "## Strong Conditions", "- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。"]
    for row in summary["strong_conditions"]:
        lines.append(f"- {row['racecourse']} / {row['surface']} / {row['distance']}: {row['races']} races, win rate {pct(row['win_rate'])}, win ROI {roi(row['win_ROI'])}")
    lines += ["", "## Weak Conditions", "- 30レース以上の条件から、予測1位の勝率下位。"]
    for row in summary["weak_conditions"]:
        lines.append(f"- {row['racecourse']} / {row['surface']} / {row['distance']}: {row['races']} races, win rate {pct(row['win_rate'])}, win ROI {roi(row['win_ROI'])}")
    lines += ["", "## AI vs Favorite", f"- Spearman correlation: {summary['spearman_ai_popularity']}",
              f"- AI rank 1, not favorite: {summary['ai_rank_1_not_favorite']['win']['races']} bets, win ROI {roi(summary['ai_rank_1_not_favorite']['win']['roi'])}, place ROI {roi(summary['ai_rank_1_not_favorite']['place']['roi'])}",
              "- 理由分類（AI rank 1 かつ popularity >= 2）:"]
    for reason_code, count in summary["ai_not_favorite_reasons"]["counts"].items():
        lines.append(f"  - {reason_code}: {count}件")
    lines += ["- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。", "- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。",
              "", "## Risk", f"- Win: final profit {summary['risk']['win']['final_profit']:.0f} yen, max drawdown {summary['risk']['win']['max_drawdown']:.0f} yen, max losing streak {summary['risk']['win']['max_losing_streak']}",
              f"- Place: final profit {summary['risk']['place']['final_profit']:.0f} yen, max drawdown {summary['risk']['place']['max_drawdown']:.0f} yen, max losing streak {summary['risk']['place']['max_losing_streak']}",
              "", "## Calibration", "| Bin | Predictions | Mean Probability | Actual Win Rate |", "|---|---:|---:|---:|"]
    for row in summary["calibration"]:
        lines.append(f"| {row['bin']} | {row['predictions']} | {row['mean_predicted_probability']} | {row['actual_win_rate']} |")
    lines += ["", "## Leakage Review", "- " + summary["leakage_review"]["features"], "- " + summary["leakage_review"]["odds_popularity"],
              "- " + summary["leakage_review"]["class_codes"], "- " + summary["leakage_review"]["margin"],
              "- 除外した結果・レース後確定列: " + ", ".join(LEAK_COLUMNS), "- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。"]
    lines += ["", "## Output Notes", f"- Calibration/cumulative profit PNG: {'generated' if summary['plots']['available'] else 'not generated (matplotlib unavailable)'}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_model_comparison(v0_rows: list[dict], v1_rows: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for label, rows in (("v0", v0_rows), ("v1", v1_rows)):
        for subset, predicate in (("all", lambda row: True), ("1plus_code_available", lambda row: row.get("grade_code") not in (None, "unknown")),):
            selected = [row for row in rows if predicate(row)]
            values = metrics(selected)
            bets = betting(selected)
            records.append({"model": label, "subset": subset, "races": values["races"], "auc": values["roc_auc"],
                            "logloss": values["logloss"], "brier": values["brier_score"], "top1": values["top1_hit_rate"],
                            "top3": values["top3_hit_rate"], "win_roi": bets["win"]["roi"], "place_roi": bets["place"]["roi"]})
    write_csv(output / "comparison.csv", records)
    (output / "summary.md").write_text(
        "# v0 vs v1\n\n"
        "| Model | Subset | AUC | LogLoss | Brier | Top1 | Top3 | Win ROI | Place ROI |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|\n" +
        "\n".join(f"| {r['model']} | {r['subset']} | {r['auc']} | {r['logloss']} | {r['brier']} | {r['top1']} | {r['top3']} | {r['win_roi']} | {r['place_roi']} |" for r in records) +
        "\n\nクラスコードの公式対応表がないため、1勝/2勝/3勝/OP/L/重賞の意味付き比較は未実施です。`1plus_code_available` はGradeCDが空でない行の参考比較であり、クラス階層を意味しません。\n",
        encoding="utf-8")


def calibration_plot(path: Path, values: list[dict]) -> None:
    plt.figure(figsize=(7, 4))
    valid = [row for row in values if row["mean_predicted_probability"] is not None]
    plt.plot([row["mean_predicted_probability"] for row in valid], [row["actual_win_rate"] for row in valid], "o-")
    plt.plot([0, 1], [0, 1], "--", color="gray")
    plt.xlabel("Mean predicted probability"); plt.ylabel("Actual win rate"); plt.tight_layout(); plt.savefig(path); plt.close()


def profit_plot(path: Path, rows: list[dict]) -> None:
    ordered = sorted((row for row in rows if row["prediction_rank"] == 1), key=lambda row: (row["date"], row["race_id"]))
    plt.figure(figsize=(9, 4))
    for key, label in (("win_payout", "Win"), ("place_payout", "Place")):
        balance, values = 0, []
        for row in ordered:
            balance += row[key] - 100; values.append(balance)
        plt.plot(values, label=label)
    plt.axhline(0, color="gray", linewidth=0.8); plt.legend(); plt.ylabel("Cumulative profit (yen)"); plt.tight_layout(); plt.savefig(path); plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run monthly walk-forward backtest")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--months", type=int, default=12, help="評価月数。24などに拡張可能")
    parser.add_argument("--start-month", help="評価開始月 YYYY-MM")
    parser.add_argument("--end-month", help="評価終了月 YYYY-MM")
    parser.add_argument("--model", choices=("v0", "v1", "all"), default="v0")
    args = parser.parse_args()
    data, pays, source = load_data(args.db)
    dates = [row["date"] for row in data if valid_result(row)]
    if not dates:
        raise SystemExit("確定済みレースがありません。DBと headDataKubun/KakuteiJyuni を確認してください。")
    end = date.fromisoformat(args.end_month + "-01") if args.end_month else shift_month(month_start(max(dates)), 1)
    start = date.fromisoformat(args.start_month + "-01") if args.start_month else shift_month(end, -args.months)
    if start >= end:
        raise SystemExit("評価期間が不正です。start-month は end-month より前にしてください。")
    metadata = {"start_month": start.strftime("%Y-%m"), "end_month_exclusive": end.strftime("%Y-%m"),
                "months": args.months, "source_rows": len(data), "payout_rows": source["pay_rows"],
                "walk_forward": "各評価月の月初より前に確定したレースだけで特徴量生成・学習", "model": args.model}
    results = {}
    v0_rows = []
    if args.model in ("v0", "all"):
        rows = evaluate(data, pays, start, end)
        v0_rows = rows
        v0_out = args.out if args.model == "v0" else ROOT / "reports" / "backtest_v0"
        write_report(rows, v0_out, {**metadata, "model": "v0 historical win rate"})
        results["v0"] = len(rows)
    if args.model in ("v1", "all"):
        rows, importance = evaluate_v1(data, pays, start, end)
        v1_out = args.out if args.model == "v1" else ROOT / "reports" / "backtest_v1"
        write_report(rows, v1_out, {**metadata, "model": "v1 LightGBM recent performance and opponent strength",
                                    "features": V1_FEATURES + ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"],
                                    "categorical_handling": "pandas get_dummies; unknown category retained; internal LightGBM names sanitized",
                                    "class_method": "GradeCD and JyokenInfoSyubetuCD raw codes; official mapping unavailable"}, importance)
        results["v1"] = len(rows)
    if args.model == "all":
        write_model_comparison(v0_rows, rows, ROOT / "reports" / "model_comparison")
    print(json.dumps({"output": str(args.out), "predictions": results, "metadata": metadata}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
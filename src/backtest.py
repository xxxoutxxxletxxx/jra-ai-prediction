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
import time
import pickle
import hashlib
import unicodedata
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev

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
V2_FEATURES = V1_FEATURES + [
    "last1_winner_strength_v2", "last2_winner_strength_v2", "last3_winner_strength_v2",
    "last1_field_strength_v2", "last2_field_strength_v2", "last3_field_strength_v2",
    "last1_margin_x_winner_strength_v2", "last2_margin_x_winner_strength_v2",
    "last3_margin_x_winner_strength_v2", "max_winner_strength_last3",
    "mean_winner_strength_last3", "weighted_winner_strength_last3",
    "best_strong_opponent_performance_last3", "last1_field_max_strength_v2",
    "last2_field_max_strength_v2", "last3_field_max_strength_v2",
    "last1_field_top3_mean_strength_v2", "last2_field_top3_mean_strength_v2",
    "last3_field_top3_mean_strength_v2", "opponent_history_missing_last3",
    "last1_winner_max_race_class_before_target", "last2_winner_max_race_class_before_target", 
    "last3_winner_max_race_class_before_target", "last1_winner_best_win_class_before_target", 
    "last2_winner_best_win_class_before_target", "last3_winner_best_win_class_before_target", 
]
PRIZE_FEATURES = [
    "race_first_prize", "race_second_prize", "race_third_prize", "race_total_top5_prize",
    "race_first_prize_log", "race_total_top5_prize_log",
    "last1_race_first_prize", "last2_race_first_prize", "last3_race_first_prize",
    "last1_race_first_prize_log", "last2_race_first_prize_log", "last3_race_first_prize_log",
    "max_race_prize_last3", "mean_race_prize_last3", "weighted_race_prize_last3",
    "prize_change_from_last1", "prize_change_from_last3_mean", "prize_ratio_vs_last1", "prize_ratio_vs_last3_mean",
    "last1_margin_x_prize_strength", "last2_margin_x_prize_strength", "last3_margin_x_prize_strength",
]
PRIZE_V2_FEATURES = V2_FEATURES + [
    "last1_winner_max_prize_before_target", "last2_winner_max_prize_before_target",
    "last3_winner_max_prize_before_target", "last1_winner_mean_prize_before_target",
    "last2_winner_mean_prize_before_target", "last3_winner_mean_prize_before_target",
]
PHASE4_FEATURES = [
    "last1_raw_performance", "last2_raw_performance", "last3_raw_performance",
    "last1_position_advantage", "last2_position_advantage", "last3_position_advantage",
    "last1_adjusted_performance", "last2_adjusted_performance", "last3_adjusted_performance",
    "best_adjusted_performance_last3", "mean_adjusted_performance_last3", "weighted_adjusted_performance_last3",
    "hidden_strength_last1", "hidden_strength_last2", "hidden_strength_last3",
    "max_hidden_strength_last3", "max_strong_against_bias_last3",
    "strong_against_bias_last1", "strong_against_bias_last2", "strong_against_bias_last3",
    "race_position_bias_last1", "race_position_bias_last2", "race_position_bias_last3",
    "setup_improvement", "hidden_strength_x_race_strength",
]
PHASE4_FEATURES_E = PRIZE_V2_FEATURES + PHASE4_FEATURES
COURSE_GEOMETRY_FEATURES = [
    "course_first_corner_distance_m", "course_elevation_difference_m", "course_final_straight_m",
    "course_start_uphill", "course_start_downhill", "course_final_uphill", "course_final_downhill",
    "course_final_steep_hill", "course_rolling_terrain", "course_mostly_flat", "course_gentle_corners",
    "course_tight_corners", "course_up_down_transition_sentence_count",
    "course_geometry_fit", "horse_expected_position", "position_stability", "frontness_mean", "frontness_std",
    "front_density", "forward_density", "mid_density", "rear_density", "expected_front_count",
    "expected_position_mean", "expected_position_std", "gate_position_pct", "gate_x_expected_position",
]
PHASE5_FEATURES = PHASE4_FEATURES_E + COURSE_GEOMETRY_FEATURES
REMOVED_CLEANUP_FEATURES = {"career_place_rate", "recent5_place_rate", "jockey_added_value", "jockey_top2_rate", "jockey_form_trend", "jockey_change_added_value"}
REVIEW_FEATURES = {"jockey_change_added_value"}
CLEANUP_A_FEATURES = [feature for feature in PHASE4_FEATURES_E + PRIZE_FEATURES if feature not in REMOVED_CLEANUP_FEATURES and not feature.startswith("race_position_bias")]
for _feature in ("racecourse", "front_density", "forward_density", "mid_density", "rear_density", "expected_front_count", "expected_position_mean", "expected_position_std"):
    if _feature in CLEANUP_A_FEATURES:
        CLEANUP_A_FEATURES.remove(_feature)
    CLEANUP_B_FEATURES = [feature for feature in CLEANUP_A_FEATURES if feature not in {"last1_finish", "last2_finish", "last3_finish"}]
# raw margin/raw_performance duplicate adjusted_performance (corr ~0.999); margin interactions re-inject the same signal.
DEDUP_MARGIN_FEATURES = {
    "last1_margin", "last2_margin", "last3_margin", "best_margin_last3", "mean_margin_last3", "weighted_margin_last3",
    "last1_raw_performance", "last2_raw_performance", "last3_raw_performance",
    "margin_x_winner_strength", "margin_x_field_strength",
    "last1_margin_x_winner_strength_v2", "last2_margin_x_winner_strength_v2", "last3_margin_x_winner_strength_v2",
    "last1_margin_x_prize_strength", "last2_margin_x_prize_strength", "last3_margin_x_prize_strength",
}
CLEANUP_C_FEATURES = [feature for feature in CLEANUP_B_FEATURES if feature not in DEDUP_MARGIN_FEATURES]
# career win rate/race count dropped per design review: prize-based class score already carries experience signal.
CAREER_COUNT_FEATURES = {"career_win_rate", "career_races"}
CLEANUP_D_FEATURES = [feature for feature in CLEANUP_C_FEATURES if feature not in CAREER_COUNT_FEATURES]
# winning margin (how decisively last1-3 was won) and class-tier-banded recent form, on top of CLEANUP_D.
WINNING_MARGIN_FEATURES = ["last1_winning_margin", "last2_winning_margin", "last3_winning_margin"]
CLASS_MATCHED_FORM_FEATURES = [
    "last1_class_matched_adjusted_performance", "last2_class_matched_adjusted_performance",
    "last3_class_matched_adjusted_performance", "mean_class_matched_adjusted_performance_last3",
    "class_matched_sample_count",
]
CLEANUP_E_FEATURES = CLEANUP_D_FEATURES + WINNING_MARGIN_FEATURES + CLASS_MATCHED_FORM_FEATURES
# v2: adds winning_margin/class_matched_* columns; forces cache regeneration.
PHASE5_CACHE_VERSION = "phase5-feature-cache-v2"
PHASE6_CACHE_VERSION = "phase6-feature-cache-v1"
PACE_BIAS_V2_FEATURES = [
    "strong_against_bias_v2_last1", "strong_against_bias_v2_last2",
    "strong_against_bias_v2_last3", "setup_benefit_last1", "setup_benefit_last2", "setup_benefit_last3",
    "adjusted_performance_v2_last1", "adjusted_performance_v2_last2", "adjusted_performance_v2_last3",
    "mean_adjusted_performance_v2_last3", "best_adjusted_performance_v2_last3",
    "weighted_adjusted_performance_v2_last3", "max_strong_against_bias_v2_last3",
]
JOCKEY_FEATURES = [
    "jockey_rides", "jockey_win_rate", "jockey_top2_rate", "jockey_place_rate",
    "jockey_added_value", "recent_jockey_added_value", "jockey_change_added_value",
]
FIT_FEATURES = [
    "distance_change_fit", "course_shape_fit", "pace_fit", "race_interval_fit",
    "racecourse_fit", "track_condition_fit", "draw_bias", "rail_course_bias_fit",
    "carried_weight_fit", "season_fit",
]
FIT_SAMPLE_FEATURES = [f"{feature}_sample_count" for feature in FIT_FEATURES]
FIT_MODEL_FEATURES = [
    "career_races", "career_win_rate", "recent3_win_rate", "recent3_place_rate",
    "last1_adjusted_performance", "last2_adjusted_performance", "last3_adjusted_performance",
    "mean_adjusted_performance_last3", "best_adjusted_performance_last3",
    "current_race_class_score", "class_change_last1", "class_change_last3_mean",
] + FIT_FEATURES
REBUILD_BASE_FEATURES = [
    "career_races", "career_win_rate", "recent3_win_rate", "recent3_place_rate",
    "last1_adjusted_performance", "last2_adjusted_performance", "last3_adjusted_performance",
    "mean_adjusted_performance_last3", "best_adjusted_performance_last3",
]
REBUILD_POLICY_FEATURES = {
    "B": REBUILD_BASE_FEATURES,
    "C": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean"],
    "D": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean", "distance_change_fit", "course_shape_fit"],
    "E": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean", "distance_change_fit", "course_shape_fit", "pace_fit"],
    "F": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean", "distance_change_fit", "course_shape_fit", "pace_fit", "race_interval_fit", "racecourse_fit", "track_condition_fit", "season_fit"],
    "G": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean", "distance_change_fit", "course_shape_fit", "pace_fit", "race_interval_fit", "racecourse_fit", "track_condition_fit", "season_fit", "draw_bias", "rail_course_bias_fit"],
    "H": REBUILD_BASE_FEATURES + ["current_race_class_score", "class_change_last1", "class_change_last3_mean", "distance_change_fit", "course_shape_fit", "pace_fit", "race_interval_fit", "racecourse_fit", "track_condition_fit", "season_fit", "draw_bias", "rail_course_bias_fit", "carried_weight_fit"],
    "I": FIT_MODEL_FEATURES,
}
FEATURE_STATUS = {
    "jockey_form_trend": "NO_CALC",
    "jockey_change_added_value": "REVIEW",
    "course_geometry_fit": "DROP",
    **{feature: "KEEP" for feature in FIT_FEATURES},
    **{feature: "REVIEW" for feature in FIT_SAMPLE_FEATURES},
}
# categorical class_label/last1-3_race_class dropped: prize-based class_score is sufficient (see race_conditions()).
RACE_CLASS_FEATURES = [
    "race_class_score", "current_race_class_score", "last1_race_class_score", "last2_race_class_score", "last3_race_class_score",
    "max_race_class_last3", "mean_race_class_last3", "weighted_race_class_last3",
    "class_change_last1", "class_change_last3_mean",
    "last1_margin_x_race_class", "last2_margin_x_race_class", "last3_margin_x_race_class",
]
RACE_CONDITION_FEATURES = RACE_CLASS_FEATURES + [
    "race_sex_condition", "race_age_condition", "is_filly_mare_only", "is_2yo_only", "is_3yo_only",
    "last1_sex_condition", "last2_sex_condition", "last3_sex_condition",
    "last1_is_filly_mare_only", "last2_is_filly_mare_only", "last3_is_filly_mare_only",
    "last1_age_condition", "last2_age_condition", "last3_age_condition",
    "race_class_change", "female_only_to_open", "open_to_female_only", "age_condition_change",
]


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def phase5_profile(message: str) -> None:
    if os.environ.get("PHASE5_PROFILE") == "1":
        print(f"[Phase5] {message}", flush=True)


def memory_mb() -> float:
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024 * 1024) if os.uname().sysname == "Darwin" else value / 1024
    except (ImportError, AttributeError):
        return 0.0


def cache_paths(model_label: str) -> tuple[Path, Path]:
    cache_dir = ROOT / "data" / "cache"
    prefix = "phase6" if model_label == "G" else "phase5"
    return cache_dir / f"{prefix}_{model_label.lower()}_features.parquet", cache_dir / f"{prefix}_{model_label.lower()}_features_metadata.json"


def model_cache_key(model_label: str, feature_columns: list[str], start: date, end: date) -> str:
    payload = json.dumps({"model": model_label, "version": PHASE6_CACHE_VERSION if model_label == "G" else PHASE5_CACHE_VERSION, "features": feature_columns,
                          "start": start.isoformat(), "end": end.isoformat(), "target": "KakuteiJyuni==1",
                          "params": {"n_estimators": 180, "learning_rate": 0.04, "num_leaves": 15, "max_depth": 5}}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def prediction_cache_path(model_label: str, key: str) -> Path:
    return ROOT / "data" / "cache" / "predictions" / f"{model_label}_{key}.parquet"


def optimize_feature_frame(frame):
    import pandas as pd
    for column in frame.columns:
        if column in {"race_id", "horse_id", "horse_name", "date", "as_of_date"}:
            continue
        if frame[column].dtype == "object":
            frame[column] = frame[column].fillna("UNKNOWN").astype("category")
        elif pd.api.types.is_float_dtype(frame[column]):
            frame[column] = frame[column].astype("float32")
        elif pd.api.types.is_integer_dtype(frame[column]):
            frame[column] = pd.to_numeric(frame[column], downcast="integer")
    return frame


def write_feature_cache(rows: list[dict], source_rows: int, model_label: str) -> None:
    import pandas as pd
    parquet_path, metadata_path = cache_paths(model_label)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    frame = optimize_feature_frame(pd.DataFrame(rows))
    frame.to_parquet(parquet_path, index=False, compression="zstd")
    cache_version = PHASE6_CACHE_VERSION if model_label == "G" else PHASE5_CACHE_VERSION
    metadata = {"cache_version": cache_version, "model": model_label, "source_rows": source_rows,
                "rows": len(frame), "columns": len(frame.columns), "generated_at": datetime.now().isoformat(),
                "date_min": str(frame["date"].min()) if "date" in frame else None,
                "date_max": str(frame["date"].max()) if "date" in frame else None,
                "file_size_bytes": parquet_path.stat().st_size}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    phase5_profile(f"Parquet cache written: rows={len(frame)}, columns={len(frame.columns)}, size={metadata['file_size_bytes'] / 1024 / 1024:.1f}MB")


def read_feature_cache(source_rows: int, model_label: str) -> list[dict] | None:
    import pandas as pd
    parquet_path, metadata_path = cache_paths(model_label)
    if not parquet_path.exists() and model_label in {"E", "F", "CA", "CB"}:
        parquet_path, metadata_path = cache_paths("F")
    if not parquet_path.exists() or not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_version = PHASE6_CACHE_VERSION if model_label == "G" else PHASE5_CACHE_VERSION
    if metadata.get("cache_version") != expected_version or metadata.get("source_rows", 0) < source_rows:
        return None
    started = time.perf_counter()
    frame = pd.read_parquet(parquet_path)
    rows = frame.to_dict("records")
    for row in rows:
        if isinstance(row.get("date"), datetime):
            row["date"] = row["date"].date()
    phase5_profile(f"Parquet cache loaded: {time.perf_counter() - started:.2f}s, rows={len(rows)}, columns={len(frame.columns)}, memory={memory_mb():.1f}MB")
    return rows


def read_feature_cache_frame(source_rows: int, model_label: str, columns: list[str]):
    import pandas as pd
    import pyarrow.parquet as pq
    parquet_path, metadata_path = cache_paths(model_label)
    if not parquet_path.exists() and model_label in {"E", "F", "CA", "CB"}:
        parquet_path, metadata_path = cache_paths("F")
    if not parquet_path.exists() or not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_version = PHASE6_CACHE_VERSION if model_label == "G" else PHASE5_CACHE_VERSION
    if metadata.get("cache_version") != expected_version or metadata.get("source_rows", 0) < source_rows:
        return None
    started = time.perf_counter()
    available = set(pq.ParquetFile(parquet_path).schema.names)
    required = list(dict.fromkeys(column for column in columns if column in available))
    frame = pd.read_parquet(parquet_path, columns=required)
    for column in columns:
        if column not in frame:
            frame[column] = 0.0 if column not in {"race_id", "horse_id", "horse_name", "date"} else ""
    if "date" in frame:
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
    phase5_profile(f"DataFrame cache loaded: {time.perf_counter() - started:.2f}s, rows={len(frame)}, columns={len(frame.columns)}, memory={frame.memory_usage(deep=True).sum() / 1024 / 1024:.1f}MB, list_dict_conversion=0")
    return frame


def evaluate_cached_dataframe(data: list[dict], pays: dict, start: date, end: date,
                              feature_columns: list[str], model_label: str,
                              target_ids: set[str] | None = None,
                              training_ids: set[str] | None = None):
    import lightgbm as lgb
    import pandas as pd
    base_columns = ["race_id", "horse_id", "horse_name", "date", "target", "actual_rank", "umaban", "popularity", "odds",
                    "racecourse", "surface", "distance", "field_size", "win_payout", "place_payout"]
    categories = [column for column in ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"] if column in feature_columns]
    if "race_sex_condition" in feature_columns:
        categories += ["race_sex_condition", "race_age_condition", "last1_sex_condition", "last2_sex_condition", "last3_sex_condition",
                       "last1_age_condition", "last2_age_condition", "last3_age_condition"]
    needed = base_columns + feature_columns + categories
    frame = read_feature_cache_frame(len(data), model_label, needed)
    if frame is None:
        return None
    key = model_cache_key(model_label, feature_columns, start, end)
    prediction_path = prediction_cache_path(model_label, key)
    metadata_path = prediction_path.with_suffix(".json")
    if os.environ.get("PHASE5_USE_PREDICTION_CACHE") == "1" and prediction_path.exists() and metadata_path.exists():
        phase5_profile(f"Prediction Cache HIT: {prediction_path}")
        cached_frame = pd.read_parquet(prediction_path)
        return cached_frame.to_dict("records"), []
    phase5_profile(f"Prediction Cache MISS: key={key}")
    eval_ids = sorted(target_ids) if target_ids else sorted(frame.loc[(frame["date"] >= start) & (frame["date"] < end), "race_id"].drop_duplicates())
    eval_set = set(eval_ids)
    evaluation = frame[frame["race_id"].isin(eval_set) & (frame["date"] >= start) & (frame["date"] < end)].copy()
    months = sorted(evaluation["date"].map(lambda value: value.replace(day=1)).unique())
    output = []
    importance = defaultdict(lambda: {"gain": 0.0, "split": 0.0})
    for month in months:
        train = frame[frame["date"] < month]
        if training_ids is not None:
            train = train[train["race_id"].isin(training_ids)]
        test = evaluation[evaluation["date"].map(lambda value: value.replace(day=1)) == month]
        columns = list(dict.fromkeys(feature_columns + categories))
        combined = pd.concat([train[columns], test[columns]], ignore_index=True)
        combined = pd.get_dummies(combined, columns=[column for column in categories if column in combined], dummy_na=True)
        train_matrix = combined.iloc[:len(train)].astype("float32")
        test_matrix = combined.iloc[len(train):].astype("float32")
        original_columns = list(train_matrix.columns)
        safe_columns = [f"f_{index}" for index in range(len(original_columns))]
        train_matrix.columns = safe_columns
        test_matrix.columns = safe_columns
        phase5_profile(f"DataFrame split {model_label} {month}: train={len(train)}, eval={len(test)}, Xtrain={train_matrix.shape}, memory={train_matrix.memory_usage(deep=True).sum() / 1024 / 1024:.1f}MB")
        fit_started = time.perf_counter()
        model = lgb.LGBMClassifier(n_estimators=180, learning_rate=0.04, num_leaves=15, max_depth=5,
                                   min_child_samples=80, reg_lambda=2.0, verbosity=-1, random_state=42)
        model.fit(train_matrix, train["target"].astype("int8"))
        phase5_profile(f"DataFrame LightGBM {model_label} {month}: {time.perf_counter() - fit_started:.2f}s, memory={memory_mb():.1f}MB")
        names = original_columns
        for name, gain, split in zip(names, model.booster_.feature_importance("gain"), model.booster_.feature_importance("split")):
            importance[name]["gain"] += float(gain); importance[name]["split"] += float(split)
        probs = model.predict_proba(test_matrix)[:, 1]
        test = test.copy()
        test["predicted_probability"] = probs
        test["prediction_rank"] = test.groupby("race_id")["predicted_probability"].rank(method="first", ascending=False).astype(int)
        output.extend(test.to_dict("records"))
    rows = []
    for row in output:
        key = tuple(str(row.get("race_id", "")).split("-"))
        pay_row = pays.get(key)
        umaban = integer(row.get("umaban"))
        row["win_payout"] = payout(pay_row, "win", umaban)
        row["place_payout"] = payout(pay_row, "place", umaban)
        rows.append({**row, "date": row["date"].isoformat(), "prediction_reason": f"DataFrame cached LightGBM {model_label}",
                     "reason_code": f"{model_label}_CACHED", "is_win": int(row["actual_rank"] == 1),
                     "is_place": int(1 <= row["actual_rank"] <= 3), "ai_vs_favorite": int(row["popularity"] > 1 and row["prediction_rank"] == 1)})
    if os.environ.get("PHASE5_WRITE_PREDICTION_CACHE") == "1":
        prediction_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(prediction_path, index=False, compression="zstd")
        metadata_path.write_text(json.dumps({"cache_version": PHASE5_CACHE_VERSION, "model": model_label, "key": key,
                                              "rows": len(rows), "feature_count": len(feature_columns), "generated_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
        phase5_profile(f"Prediction Cache written: {prediction_path}")
    return rows, [{"feature": name, **values} for name, values in sorted(importance.items(), key=lambda item: item[1]["gain"], reverse=True)]


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


def prize_amount(value: object) -> float:
    """NL_RA_RACEの本賞金を円へ変換。値はJV形式の100円単位として確認済み。"""
    return integer(value) * 100.0


def prize_log(value: float) -> float:
    return math.log1p(max(0.0, value))


def first_corner_position(row: dict) -> int:
    value = integer(row.get("Jyuni1c"))
    return value if value > 0 else 0


def last_corner_position(row: dict) -> int:
    """直線に最も近い、取得可能な最終コーナー通過順。過去走の集計にのみ使用する。"""
    for column in ("Jyuni4c", "Jyuni3c", "Jyuni2c", "Jyuni1c"):
        value = integer(row.get(column))
        if value > 0:
            return value
    return 0


def closing_time_value(row: dict) -> float | None:
    """過去走の上がり3F(HaronTimeL3)。対象レース自身の値は特徴量に使用しない。"""
    value = number(row.get("HaronTimeL3"), default=float("nan"))
    return None if math.isnan(value) or value <= 0 else value


def geometry_value(row: dict, name: str, default: float = 0.0) -> float:
    return number(row.get(f"course_{name}"), default)


def geometry_signature(row: dict) -> tuple:
    return (geometry_value(row, "first_corner_distance_m"), geometry_value(row, "final_straight_m"),
            geometry_value(row, "elevation_difference_m"), integer(row.get("race_Kyori")))


def prize_class_score(row: dict) -> float:
    """賞金を内部クラス基準として連続値化する。1着賞金そのものをモデル入力に使うのではなく、ここで作ったスコアを学習に使う。"""
    prize = prize_amount(row.get("race_Honsyokin0"))
    if prize > 0:
        return math.log1p(prize) / math.log1p(500_000_000.0)
    grade = text(row.get("race_GradeCD")).upper()
    grade_map = {"A": 0.95, "B": 0.8, "C": 0.65, "L": 0.5}
    return grade_map.get(grade, 0.0)


def performance_from_result(result: dict) -> tuple[float, float, float]:
    """raw performance は margin のみで構成し、着順やレース強度を混ぜない。高い値＝良いperformance。"""
    margin = max(0.0, float(result.get("margin") or 0.0))
    raw = -margin
    class_delta = float(result.get("class_delta", 0.0))
    pace_delta = float(result.get("pace_delta", 0.0))
    opponent_delta = float(result.get("opponent_delta", 0.0))
    adjusted = raw + 0.55 * class_delta + 0.35 * pace_delta + 0.25 * opponent_delta
    return raw, adjusted, (class_delta + pace_delta + opponent_delta)


def shrink_mean(values: list[float], global_mean: float = 0.0, prior: float = 5.0) -> float:
    """少標本の履歴を global mean へ縮約する。値の符号は performance と同じ。"""
    if not values:
        return global_mean
    return (sum(values) + prior * global_mean) / (len(values) + prior)


def fit_from_history(values: list[tuple[float, float]], target: float | None = None,
                     global_mean: float = 0.0) -> tuple[float, int]:
    """(条件距離, adjusted performance) の近傍を重み付きで集約する。"""
    if not values:
        return 0.0, 0
    if target is None:
        selected = values
    else:
        selected = sorted(values, key=lambda item: abs(item[0] - target))[: min(5, len(values))]
    weights = [1.0 / (1.0 + abs(item[0] - target)) if target is not None else 1.0 for item in selected]
    estimate = sum(weight * item[1] for weight, item in zip(weights, selected)) / sum(weights)
    return shrink_mean([estimate], global_mean, prior=max(2.0, 8.0 - len(values))) - global_mean, len(values)


def historical_value(history: list[dict], key: str, value: object,
                     global_mean: float, min_match: int = 1) -> tuple[float, int]:
    values = [float(item["adjusted_performance"]) for item in history if item.get(key) == value]
    if len(values) < min_match:
        return shrink_mean(values, global_mean) - global_mean, len(values)
    return shrink_mean(values, global_mean) - global_mean, len(values)


def normalized_interval(days: int | float) -> float:
    return max(0.0, float(days)) / 90.0


def condition_value(row: dict) -> str:
    """JV の馬場コードを内部カテゴリへ変換。未提供時は UNKNOWN。"""
    value = text(row.get("race_TenkoBabaSibaBabaCD") or row.get("race_TenkoBabaDirtBabaCD"))
    return {"1": "GOOD", "2": "YIELDING", "3": "HEAVY", "4": "SOFT"}.get(value, value or "UNKNOWN")


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


def limit_evaluation_races(data: list[dict], start: date, end: date, max_races: int | None) -> list[dict]:
    if not max_races:
        return [row for row in data if row["date"] < end]
    target_keys = []
    seen = set()
    for row in sorted(data, key=lambda item: (item["date"], race_key(item))):
        key = race_key(row)
        if start <= row["date"] < end and key not in seen:
            seen.add(key)
            target_keys.append(key)
            if len(target_keys) >= max_races:
                break
    target_set = set(target_keys)
    limited = [row for row in data if row["date"] < start or (row["date"] < end and race_key(row) in target_set)]
    phase5_profile(f"evaluation limited: target_races={len(target_set)}, rows={len(limited)}, history_rows={sum(row['date'] < start for row in limited)}")
    return limited


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
    started = time.perf_counter()
    phase5_profile("DB load started")
    connection = sqlite3.connect(db_path)
    se_columns = list(RACE_KEY) + [
        "Wakuban", "Umaban", "KettoNum", "Bamei", "SexCD", "Barei", "KisyuCode",
        "KisyuCodeBefore", "ChokyoCode", "TozaiCD", "Futan", "FutanBefore", "BaTaijyu", "Odds", "Ninki", "KakuteiJyuni",
        "NyusenJyuni", "Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c", "headDataKubun",
    ] + LEAK_COLUMNS
    ra_columns = list(RACE_KEY) + [
        "Kyori", "KyoriBefore", "TrackCD", "TrackCDBefore", "CourseKubunCD", "CourseKubunCDBefore", "GradeCD", "JyokenInfoSyubetuCD",
        "JyokenInfoJyokenCD0", "JyokenInfoJyokenCD1", "JyokenInfoJyokenCD2", "JyokenInfoJyokenCD3", "JyokenInfoJyokenCD4",
        "JyokenName", "RaceInfoHondai", "RaceInfoFukudai", "Honsyokin0", "Honsyokin1", "Honsyokin2", "Honsyokin3", "Honsyokin4", "Honsyokin5", "Honsyokin6",
        "Fukasyokin0", "Fukasyokin1", "Fukasyokin2", "Fukasyokin3", "Fukasyokin4", "SyussoTosu", "NyusenTosu",
        "TenkoBabaTenkoCD", "TenkoBabaSibaBabaCD", "TenkoBabaDirtBabaCD",
        "HaronTimeS3", "HaronTimeS4", "HaronTimeL3", "HaronTimeL4",
    ]
    se_rows = read_table(connection, "NL_SE_RACE_UMA", se_columns, min_year)
    ra_rows = read_table(connection, "NL_RA_RACE", ra_columns, min_year)
    pay_columns = list(RACE_KEY) + [
        f"PayTansyo{i}{suffix}" for i in range(3) for suffix in ("Umaban", "Pay")
    ] + [f"PayFukusyo{i}{suffix}" for i in range(5) for suffix in ("Umaban", "Pay")]
    pay_rows = read_table(connection, "NL_HR_PAY", pay_columns, min_year)
    connection.close()
    course_path = ROOT / "data" / "output" / "course_features_ver6.csv"
    course_map = {}
    if course_path.exists():
        course_started = time.perf_counter()
        with course_path.open(encoding="utf-8-sig", newline="") as handle:
            for course in csv.DictReader(handle):
                key = (text(course.get("JyoCD")).zfill(2), integer(course.get("Kyori_m")), text(course.get("TrackCD")))
                course_map[key] = course
            phase5_profile(f"course features loaded: {time.perf_counter() - course_started:.2f}s, rows={len(course_map)}, memory={memory_mb():.1f}MB")
    races = {race_key(row): row for row in ra_rows}
    pays = {race_key(row): row for row in pay_rows}
    merged = []
    join_started = time.perf_counter()
    for row in se_rows:
        row = dict(row)
        row.update({f"race_{key}": value for key, value in races.get(race_key(row), {}).items()})
        course = course_map.get((text(row.get("race_idJyoCD")).zfill(2), integer(row.get("race_Kyori")), text(row.get("race_TrackCD"))), {})
        for key, value in course.items():
            row[f"course_{key}"] = value
        row["date"] = race_date(row)
        if row["date"] is not None:
            merged.append(row)
    phase5_profile(f"course feature join: {time.perf_counter() - join_started:.2f}s, rows={len(merged)}, memory={memory_mb():.1f}MB")
    phase5_profile(f"DB load finished: {time.perf_counter() - started:.2f}s, se_rows={len(se_rows)}, ra_rows={len(ra_rows)}, memory={memory_mb():.1f}MB")
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


def eligible_target_race_ids(data: list[dict], min_race_first_prize: float | None) -> set[str] | None:
    if min_race_first_prize is None:
        return None
    return {race_id(row) for row in data if prize_amount(row.get("race_Honsyokin0")) > min_race_first_prize}


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


def gate_band(gate: int, field_size: int) -> str:
    """枠適性用の内/中/外バンド。過去走・対象走とも同じ関数で計算する。"""
    if not gate or not field_size:
        return "UNKNOWN"
    third = field_size / 3.0
    if gate <= third:
        return "内"
    if gate <= 2 * third:
        return "中"
    return "外"


def rest_band(days: int | float | None) -> str:
    """休養間隔適性用のバンド。前走からの日数(取得不能ならUNKNOWN)。"""
    if days is None:
        return "UNKNOWN"
    if days <= 14:
        return "0-14"
    if days <= 30:
        return "15-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "91+"


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


def race_conditions(row: dict) -> dict:
    """旧classロジックは一旦残すが、学習用のclass_scoreは賞金ベースの連続値へ切り替える。"""
    name = unicodedata.normalize("NFKC", text(row.get("race_JyokenName"))).lower()
    grade = text(row.get("race_GradeCD")).upper()
    race_name = unicodedata.normalize("NFKC", text(row.get("race_RaceInfoHondai")))
    combined_name = f"{name} {race_name.lower()}"
    grade_map = {"A": ("G1", 8), "B": ("G2", 7), "C": ("G3", 6), "L": ("LISTED", 5)}
    if grade in grade_map:
        label, legacy_score = grade_map[grade]
    elif "新馬" in combined_name:
        label, legacy_score = "NEWCOMER", 0
    elif "未勝利" in combined_name:
        label, legacy_score = "MAIDEN", 0
    elif "1勝" in combined_name or "500万" in combined_name:
        label, legacy_score = "CLASS_1", 1
    elif "2勝" in combined_name or "1000万" in combined_name:
        label, legacy_score = "CLASS_2", 2
    elif "3勝" in combined_name or "1600万" in combined_name:
        label, legacy_score = "CLASS_3", 3
    elif "オープン" in combined_name or "open" in combined_name or "ｏｐ" in combined_name:
        label, legacy_score = "OPEN", 4
    else:
        label, legacy_score = "UNKNOWN", 0
    age = "UNKNOWN"
    if "2歳" in combined_name:
        age = "TWO_YEAR_OLD_ONLY"
    elif "3歳上" in combined_name or "3歳以上" in combined_name:
        age = "THREE_AND_OLDER"
    elif "3歳" in combined_name:
        age = "THREE_YEAR_OLD_ONLY"
    elif "4歳上" in combined_name or "4歳以上" in combined_name:
        age = "FOUR_AND_OLDER"
    female_only = "牝馬" in combined_name or "牝" in combined_name
    prize_score = prize_class_score(row)
    return {"class_label": label, "class_score": prize_score, "legacy_class_label": label, "legacy_class_score": legacy_score,
            "age": age, "sex": "FEMALE_ONLY" if female_only else "OPEN_SEX",
            "filly_only": int(female_only), "grade_raw": grade or "UNKNOWN"}


def history_class_score(row: dict) -> int | None:
    """Experimental source-race tier. Explicit class/grade wins; prize is a fallback."""
    condition = race_conditions(row)
    if condition["class_label"] != "UNKNOWN":
        return int(condition["class_score"])
    prize = prize_amount(row.get("race_Honsyokin0"))
    if prize <= 0:
        return None
    # These are deliberately isolated experimental bands; they are not used by production.
    if prize < 7_000_000:
        return 0
    if prize < 11_000_000:
        return 1
    if prize < 22_000_000:
        return 2
    if prize < 32_000_000:
        return 3
    return 4


def history_policy_allows(row: dict, policy: str) -> bool:
    if policy == "baseline":
        return True
    score = history_class_score(row)
    return score is not None and score >= (1 if policy == "filter-a" else 2)


def smoothed_strength(stat: dict) -> float:
    """対象日以前の情報だけで、少標本を縮約した連続的な能力値を返す。"""
    races = stat.get("races", 0)
    wins = stat.get("wins", 0)
    places = stat.get("places", 0)
    win_rate = (wins + 1.0) / (races + 5.0)
    place_rate = (places + 1.0) / (races + 5.0)
    confidence = min(1.0, races / 10.0)
    return (0.6 * win_rate + 0.4 * place_rate) * (0.5 + 0.5 * confidence)


def build_v1_features(data: list[dict], history_policy: str = "baseline", feature_target_ids: set[str] | None = None,
                      history_trace: dict | None = None) -> list[dict]:
    """日付順に一度だけ走査し、各行のas_of_date時点特徴量を作る。"""
    started = time.perf_counter()
    phase5_profile(f"history construction started: rows={len(data)}, memory={memory_mb():.1f}MB")
    ordered = sorted((row for row in data if valid_result(row)), key=lambda row: (row["date"], race_key(row), integer(row.get("Umaban"))))
    histories = defaultdict(lambda: deque(maxlen=5))
    race_dates = defaultdict(deque)
    stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0, "max_class": 0, "best_win_class": 0,
                                 "max_prize": 0.0, "mean_prize": 0.0, "prize_count": 0,
                                 "adjusted_sum": 0.0, "adjusted_count": 0,
                                 "finish_sum": 0.0, "normalized_finish_sum": 0.0})
    jockey_state = defaultdict(lambda: {"rides": 0, "wins": 0, "top2": 0, "places": 0, "added_sum": 0.0, "recent": deque(maxlen=30)})
    features = []
    # Aggregation maps for course x gate and bloodline stats (updated after race results are applied)
    course_gate_stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})
    sire_stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})
    damsire_stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})
    races = defaultdict(list)
    for row in ordered:
        races[race_key(row)].append(row)
    pending_updates = []
    current_date = None
    sorted_races = sorted(races, key=lambda item: (race_date(races[item][0]), item))
    for race_index, key in enumerate(sorted_races, 1):
        horses = races[key]
        date_value = horses[0]["date"]
        if current_date is not None and date_value != current_date:
            for update in pending_updates:
                horse, result = update
                if history_trace is not None and horse == history_trace.get("horse_id"):
                    history_trace.setdefault("source", []).append({"source_race_id": result["source_race_id"],
                        "history_allowed": result.get("history_allowed", True), "event": "state_update_skipped" if not result.get("history_allowed", True) else "state_update"})
                if not result.get("history_allowed", True):
                    continue
                stats[horse]["races"] += 1
                stats[horse]["wins"] += result["win"]
                stats[horse]["places"] += result["place"]
                stats[horse]["adjusted_sum"] += result.get("adjusted_performance", 0.0)
                stats[horse]["adjusted_count"] += 1
                stats[horse]["max_class"] = max(stats[horse]["max_class"], result.get("class_score", 0))
                if result["win"]:
                    stats[horse]["best_win_class"] = max(stats[horse]["best_win_class"], result.get("class_score", 0))
                prize = result.get("first_prize", 0.0)
                stats[horse]["max_prize"] = max(stats[horse]["max_prize"], prize)
                stats[horse]["mean_prize"] = (stats[horse]["mean_prize"] * stats[horse]["prize_count"] + prize) / (stats[horse]["prize_count"] + 1)
                stats[horse]["prize_count"] += 1
                stats[horse]["finish_sum"] += result["finish"]
                stats[horse]["normalized_finish_sum"] += (result["finish"] - 1) / max(1, result["field_size"] - 1)
                histories[horse].append(result)
                if history_trace is not None and horse == history_trace.get("horse_id"):
                    history_trace.setdefault("appended", []).append(result["source_race_id"])
                race_dates[horse].append(current_date)
                # post-race updates: update course x gate and bloodline aggregates
                try:
                    ckey = (result.get("racecourse"), result.get("surface"), result.get("distance_band"), result.get("gate_band"))
                    cg = course_gate_stats[ckey]
                    cg["races"] = cg.get("races", 0) + 1
                    cg["wins"] = cg.get("wins", 0) + int(result.get("win", 0))
                    cg["places"] = cg.get("places", 0) + int(result.get("place", 0))
                except Exception:
                    pass
                try:
                    sid = result.get("sire") or ""
                    sd = sire_stats[sid]
                    sd["races"] = sd.get("races", 0) + 1
                    sd["wins"] = sd.get("wins", 0) + int(result.get("win", 0))
                    sd["places"] = sd.get("places", 0) + int(result.get("place", 0))
                except Exception:
                    pass
                try:
                    did = result.get("damsire") or ""
                    dd = damsire_stats[did]
                    dd["races"] = dd.get("races", 0) + 1
                    dd["wins"] = dd.get("wins", 0) + int(result.get("win", 0))
                    dd["places"] = dd.get("places", 0) + 1 if int(result.get("place", 0)) else dd.get("places", 0)
                except Exception:
                    pass
                cutoff = current_date - timedelta(days=365)
                while race_dates[horse] and race_dates[horse][0] < cutoff:
                    race_dates[horse].popleft()
            pending_updates = []
        current_date = date_value
        if race_index % 5000 == 0:
            phase5_profile(f"history races processed: {race_index}/{len(sorted_races)}, elapsed={time.perf_counter() - started:.2f}s, memory={memory_mb():.1f}MB")
        current_condition = race_conditions(horses[0])
        current_prizes = [prize_amount(horses[0].get(f"race_Honsyokin{i}")) for i in range(5)]
        current_first_prize = current_prizes[0]
        current_total_prize = sum(current_prizes)
        current_geometry = geometry_signature(horses[0])
        positions = [first_corner_position(item) for item in horses]
        late_positions = [last_corner_position(item) for item in horses]
        field_count = len(horses)
        observed_frontness = [(1.0 - (value - 1) / max(1, field_count - 1)) if value > 0 else 0.5 for value in positions]
        observed_late_frontness = [(1.0 - (value - 1) / max(1, field_count - 1)) if value > 0 else 0.5 for value in late_positions]
        closing_times = [closing_time_value(item) for item in horses]
        valid_closing = sorted({value for value in closing_times if value is not None})
        closing_rank = {value: index for index, value in enumerate(valid_closing)}
        observed_closing_speed = [(1.0 - closing_rank[value] / max(1, len(valid_closing) - 1)) if value is not None else 0.5
                                  for value in closing_times]
        # Target race results must not contribute to any model feature.
        position_bias = 0.0
        prior_ability = {text(item.get("KettoNum")): stats[text(item.get("KettoNum"))]["wins"] / max(1, stats[text(item.get("KettoNum"))]["races"]) for item in horses}
        expected_order = {horse: rank for rank, (horse, _) in enumerate(sorted(prior_ability.items(), key=lambda pair: pair[1], reverse=True), 1)}
        weighted_bias = 0.0
        residual_bias = 0.0
        prior_stats = {text(row.get("KettoNum")): dict(stats[text(row.get("KettoNum"))]) for row in horses}
        field_values = []
        for row in horses:
            current = prior_stats.get(text(row.get("KettoNum")), {"races": 0, "wins": 0, "places": 0})
            field_values.append(current["wins"] / current["races"] if current["races"] else 0.0)
        field_strength = mean(field_values) if field_values else 0.0
        winner = next((row for row in horses if integer(row.get("KakuteiJyuni")) == 1), None)
        runner_up = next((row for row in horses if integer(row.get("KakuteiJyuni")) == 2), None)
        # how far the winner beat the runner-up by; None when no runner-up is resolvable.
        winning_margin_value = margin_value(runner_up) if runner_up is not None else None
        winner_stat = prior_stats.get(text(winner.get("KettoNum")), {"races": 0, "wins": 0, "places": 0}) if winner else {"races": 0, "wins": 0, "places": 0}
        winner_strength = winner_stat["wins"] / winner_stat["races"] if winner_stat["races"] else 0.0
        expected_positions = {text(item.get("KettoNum")): mean([entry.get("frontness", 0.5) for entry in histories[text(item.get("KettoNum"))]])
                    if histories[text(item.get("KettoNum"))] else 0.5 for item in horses}
        expected_position_values = list(expected_positions.values())
        front_density = sum(value >= 0.67 for value in expected_position_values) / max(1, field_count)
        forward_density = sum(value >= 0.5 for value in expected_position_values) / max(1, field_count)
        mid_density = sum(0.33 <= value < 0.67 for value in expected_position_values) / max(1, field_count)
        rear_density = sum(value < 0.33 for value in expected_position_values) / max(1, field_count)
        adjusted_sum = sum(stat["adjusted_sum"] for stat in stats.values())
        adjusted_count = sum(stat["adjusted_count"] for stat in stats.values())
        global_adjusted = adjusted_sum / adjusted_count if adjusted_count else 0.0
        current_condition_value = condition_value(horses[0])
        current_distance = integer(horses[0].get("race_Kyori") or horses[0].get("Kyori"))
        current_pace = mean(expected_position_values) if expected_position_values else 0.5
        for row in horses:
            horse = text(row.get("KettoNum"))
            current = prior_stats.get(horse, {"races": 0, "wins": 0, "places": 0})
            past = list(histories[horse])[::-1]
            recent3 = past[:3]
            recent5 = past[:5]
            # class-tier-banded recent form: young-only conditions keep plain recency (trajectory is too
            # volatile, e.g. newcomer straight into a graded race); aged/open conditions match within +/-1
            # legacy class tier, and a horse's first aged-company start also pulls in any prior graded runs.
            current_legacy_class = current_condition["legacy_class_score"]
            current_age = current_condition["age"]
            young_limited = current_age in {"TWO_YEAR_OLD_ONLY", "THREE_YEAR_OLD_ONLY"}
            if young_limited:
                class_matched_recent3 = recent3
            else:
                band_matched = [item for item in past if abs(item["condition"]["legacy_class_score"] - current_legacy_class) <= 1]
                first_time_aged = current_age == "THREE_AND_OLDER" and bool(past) and all(item["condition"]["age"] in {"TWO_YEAR_OLD_ONLY", "THREE_YEAR_OLD_ONLY"} for item in past)
                if first_time_aged:
                    stakes_runs = [item for item in past if item["condition"]["legacy_class_score"] >= 5]
                    combined = {item["source_race_id"]: item for item in band_matched + stakes_runs}
                    band_matched = sorted(combined.values(), key=lambda item: item["date"], reverse=True)
                class_matched_recent3 = band_matched[:3] if band_matched else recent3
            class_matched_adjusted = [item.get("adjusted_performance", 0.0) for item in class_matched_recent3]
            raw_recent = [item.get("raw_performance", performance_from_result(item)[0]) for item in recent3]
            adjusted_recent = [item.get("adjusted_performance", performance_from_result(item)[1]) for item in recent3]
            hidden_recent = [adjusted - raw for adjusted, raw in zip(adjusted_recent, raw_recent)]
            against_recent = [performance_from_result(item)[2] for item in recent3]
            recent_closing_speed = [item.get("closing_speed", 0.5) for item in recent3]
            recent_late_frontness = [item.get("late_frontness", 0.5) for item in recent3]
            recent_position_closing_power = [item.get("frontness", 0.5) * item.get("closing_speed", 0.5) for item in recent3]
            same_geometry = [item.get("adjusted_performance", performance_from_result(item)[1]) for item in histories[horse]
                             if item.get("geometry_signature") == current_geometry]
            recent_class_scores = [float(item.get("class_score", 0.0)) for item in recent3]
            class_change_last1 = current_condition["class_score"] - (recent_class_scores[0] if recent_class_scores else 0.0)
            class_change_last3_mean = current_condition["class_score"] - mean(recent_class_scores) if recent_class_scores else 0.0
            last_distance = recent3[0].get("distance", current_distance) if recent3 else current_distance
            distance_change = (current_distance - last_distance) / 1000.0
            recent_distance_changes = [float(item.get("distance_change", 0.0)) for item in recent3]
            distance_fit_values = [(float(item.get("distance_change", 0.0)), float(item["adjusted_performance"])) for item in past]
            distance_change_fit, distance_sample_count = fit_from_history(distance_fit_values, distance_change, global_adjusted)
            shape_values = []
            for item in past:
                shape = item.get("geometry_signature")
                if shape:
                    shape_distance = abs(float(shape[0]) - float(current_geometry[0])) / 1000.0
                    shape_distance += abs(float(shape[1]) - float(current_geometry[1])) / 1000.0
                    shape_distance += abs(float(shape[2]) - float(current_geometry[2])) / 100.0
                    shape_values.append((shape_distance, float(item["adjusted_performance"])))
            course_shape_fit, course_shape_sample_count = fit_from_history(shape_values, 0.0, global_adjusted)
            pace_values = [(float(item.get("pace_score", 0.5)), float(item["adjusted_performance"])) for item in past]
            pace_fit, pace_sample_count = fit_from_history(pace_values, current_pace, global_adjusted)
            intervals = [(float(item.get("interval_norm", 0.0)), float(item["adjusted_performance"])) for item in past if item.get("interval_norm") is not None]
            current_interval = normalized_interval((date_value - recent3[0]["date"]).days) if recent3 else 0.0
            race_interval_fit, interval_sample_count = fit_from_history(intervals, current_interval, global_adjusted)
            racecourse_fit, racecourse_sample_count = historical_value(past, "racecourse", JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD"))), global_adjusted)
            track_fit, track_sample_count = historical_value(past, "track_condition", current_condition_value, global_adjusted)
            season_fit, season_sample_count = historical_value(past, "season", (date_value.month - 1) // 3, global_adjusted)
            current_distance_band = distance_band(current_distance)
            current_surface = surface(row)
            current_gate_band = gate_band(integer(row.get("Wakuban")), field_count)
            current_rest_band = rest_band((date_value - recent3[0]["date"]).days if recent3 else None)
            horse_distance_aptitude, distance_aptitude_sample_count = historical_value(past, "distance_band", current_distance_band, global_adjusted)
            horse_surface_aptitude, surface_aptitude_sample_count = historical_value(past, "surface", current_surface, global_adjusted)
            horse_rest_aptitude, rest_aptitude_sample_count = historical_value(past, "rest_band", current_rest_band, global_adjusted)
            horse_gate_aptitude, gate_aptitude_sample_count = historical_value(past, "gate_band", current_gate_band, global_adjusted)
            weight = number(row.get("Futan"))
            weight_values = [(abs(weight - number(item.get("weight"))) / 10.0, float(item["adjusted_performance"])) for item in past if number(item.get("weight")) > 0 and weight > 0]
            carried_weight_fit, weight_sample_count = fit_from_history(weight_values, 0.0, global_adjusted)
            position_history = [item.get("frontness", 0.5) for item in histories[horse]]
            draw = integer(row.get("Wakuban"))
            draw_values = [(abs(draw - integer(item.get("gate"))), float(item["adjusted_performance"])) for item in past if draw and integer(item.get("gate"))]
            draw_bias, draw_sample_count = fit_from_history(draw_values, 0.0, global_adjusted)
            rail_values = [(float(item.get("frontness", 0.5)) * (1.0 if integer(item.get("gate")) <= max(1, int(field_count / 3)) else -0.25), float(item["adjusted_performance"])) for item in past]
            rail_fit, rail_sample_count = fit_from_history(rail_values, mean(position_history) if position_history else 0.5, global_adjusted) if surface(row) == "芝" else (0.0, 0)
            margins = [item["margin"] for item in past if item["margin"] is not None]
            v2_recent = []
            for item in recent3:
                winner_stat = stats.get(item.get("winner_id", ""), {"races": 0, "wins": 0, "places": 0, "max_class": 0, "best_win_class": 0})
                participant_strengths = [smoothed_strength(stats.get(participant, {"races": 0, "wins": 0, "places": 0}))
                                         for participant in item.get("participants", [])]
                participant_strengths.sort(reverse=True)
                v2_recent.append({
                    "winner": smoothed_strength(winner_stat),
                    "field": mean(participant_strengths) if participant_strengths else 0.0,
                    "field_max": max(participant_strengths) if participant_strengths else 0.0,
                    "field_top3": mean(participant_strengths[:3]) if participant_strengths else 0.0,
                    "margin": item.get("margin"),
                    "max_class": winner_stat.get("max_class", 0),
                    "best_win_class": winner_stat.get("best_win_class", 0),
                    "max_prize": winner_stat.get("max_prize", 0.0),
                    "mean_prize": winner_stat.get("mean_prize", 0.0),
                })
            v2_winner = [item["winner"] for item in v2_recent]
            v2_field = [item["field"] for item in v2_recent]
            v2_missing = sum(1 for item in v2_recent if not item.get("winner") and not item.get("field"))
            # pre-race lookups for course x gate and bloodline aggregates (no leakage: use current maps BEFORE race updates)
            racecourse_name = JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD")))
            surface_name = surface(row)
            current_distance = integer(row.get("race_Kyori") or row.get("Kyori"))
            distance_band_value = distance_band(current_distance)
            gate_band_value = gate_band(integer(row.get("Wakuban")), field_count)
            course_key = (racecourse_name, surface_name, distance_band_value, gate_band_value)
            cg = course_gate_stats[course_key]
            cg_races = cg.get("races", 0)
            cg_wins = cg.get("wins", 0)
            cg_places = cg.get("places", 0)
            cg_win_rate = cg_wins / cg_races if cg_races else 0.0
            cg_place_rate = cg_places / cg_races if cg_races else 0.0
            # simple shrink toward prior similar to other stats (prior: +1 win, +5 races)
            cg_win_rate_shrink = (cg_wins + 1.0) / (cg_races + 5.0) if cg_races else 0.0
            sire_id = text(row.get("Sire") or row.get("race_Sire") or row.get("SIRE_ID") or row.get("sire") or "")
            damsire_id = text(row.get("Damsire") or row.get("DamSire") or row.get("DAM_SIRE_ID") or row.get("damsire") or "")
            s_stats = sire_stats[sire_id]
            d_stats = damsire_stats[damsire_id]
            sire_races = s_stats.get("races", 0)
            sire_wins = s_stats.get("wins", 0)
            sire_places = s_stats.get("places", 0)
            damsire_races = d_stats.get("races", 0)
            damsire_wins = d_stats.get("wins", 0)
            damsire_places = d_stats.get("places", 0)
            sire_win_rate = sire_wins / sire_races if sire_races else 0.0
            sire_place_rate = sire_places / sire_races if sire_races else 0.0
            damsire_win_rate = damsire_wins / damsire_races if damsire_races else 0.0
            damsire_place_rate = damsire_places / damsire_races if damsire_races else 0.0
            sire_win_rate_shrink = (sire_wins + 1.0) / (sire_races + 5.0) if sire_races else 0.0
            damsire_win_rate_shrink = (damsire_wins + 1.0) / (damsire_races + 5.0) if damsire_races else 0.0

            values = {
                "as_of_date": date_value.isoformat(), "race_id": race_id(row), "horse_id": horse,
                "target": int(integer(row.get("KakuteiJyuni")) == 1), "date": date_value,
                "racecourse": JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD"))),
                "surface": surface(row), "distance": integer(row.get("race_Kyori") or row.get("Kyori")),
                "class_code": class_code(row), "grade_code": text(row.get("race_GradeCD")) or "unknown",
                "condition_code": text(row.get("race_JyokenInfoSyubetuCD")) or "unknown",
                "race_class_score": current_condition["class_score"],
                "last1_winning_margin": (recent3[0].get("winning_margin") or 0.0) if len(recent3) > 0 else 0.0,
                "last2_winning_margin": (recent3[1].get("winning_margin") or 0.0) if len(recent3) > 1 else 0.0,
                "last3_winning_margin": (recent3[2].get("winning_margin") or 0.0) if len(recent3) > 2 else 0.0,
                "last1_class_matched_adjusted_performance": class_matched_adjusted[0] if len(class_matched_adjusted) > 0 else 0.0,
                "last2_class_matched_adjusted_performance": class_matched_adjusted[1] if len(class_matched_adjusted) > 1 else 0.0,
                "last3_class_matched_adjusted_performance": class_matched_adjusted[2] if len(class_matched_adjusted) > 2 else 0.0,
                "mean_class_matched_adjusted_performance_last3": mean(class_matched_adjusted) if class_matched_adjusted else 0.0,
                "class_matched_sample_count": len(class_matched_recent3),
                "race_sex_condition": current_condition["sex"], "race_age_condition": current_condition["age"],
                "is_filly_mare_only": current_condition["filly_only"],
                "is_2yo_only": int(current_condition["age"] == "TWO_YEAR_OLD_ONLY"),
                "is_3yo_only": int(current_condition["age"] == "THREE_YEAR_OLD_ONLY"),
                "race_first_prize": current_first_prize, "race_second_prize": current_prizes[1],
                "race_third_prize": current_prizes[2], "race_total_top5_prize": current_total_prize,
                "race_first_prize_log": prize_log(current_first_prize), "race_total_top5_prize_log": prize_log(current_total_prize),
                "distance_change_fit": distance_change_fit, "distance_change_fit_sample_count": distance_sample_count,
                "course_shape_fit": course_shape_fit, "course_shape_fit_sample_count": course_shape_sample_count,
                "pace_fit": pace_fit, "pace_fit_sample_count": pace_sample_count,
                "race_interval_fit": race_interval_fit, "race_interval_fit_sample_count": interval_sample_count,
                "racecourse_fit": racecourse_fit, "racecourse_fit_sample_count": racecourse_sample_count,
                "track_condition_fit": track_fit, "track_condition_fit_sample_count": track_sample_count,
                "draw_bias": draw_bias, "draw_bias_sample_count": draw_sample_count,
                "rail_course_bias_fit": rail_fit, "rail_course_bias_fit_sample_count": rail_sample_count,
                "carried_weight_fit": carried_weight_fit, "carried_weight_fit_sample_count": weight_sample_count,
                "season_fit": season_fit, "season_fit_sample_count": season_sample_count,
                "first_corner_position": 0,
                "race_position_bias": position_bias,
                "course_first_corner_distance_m": geometry_value(row, "first_corner_distance_m"),
                "course_elevation_difference_m": geometry_value(row, "elevation_difference_m"),
                "course_final_straight_m": geometry_value(row, "final_straight_m"),
                "course_start_uphill": integer(row.get("course_start_uphill")),
                "course_start_downhill": integer(row.get("course_start_downhill")),
                "course_final_uphill": integer(row.get("course_final_uphill")),
                "course_final_downhill": integer(row.get("course_final_downhill")),
                "course_final_steep_hill": integer(row.get("course_final_steep_hill")),
                "course_rolling_terrain": integer(row.get("course_rolling_terrain")),
                "course_mostly_flat": integer(row.get("course_mostly_flat")),
                "course_gentle_corners": integer(row.get("course_gentle_corners")),
                "course_tight_corners": integer(row.get("course_tight_corners")),
                "course_up_down_transition_sentence_count": integer(row.get("course_up_down_transition_sentence_count")),
                "course_geometry_fit": mean(same_geometry) if same_geometry else 0.0,
                "horse_expected_position": mean(position_history) if position_history else 0.5,
                "position_stability": pstdev(position_history) if len(position_history) > 1 else 0.0,
                "frontness_mean": mean(position_history) if position_history else 0.5,
                "frontness_std": pstdev(position_history) if len(position_history) > 1 else 0.0,
                "gate_position_pct": integer(row.get("Umaban")) / max(1, field_count),
                "gate_x_expected_position": (integer(row.get("Umaban")) / max(1, field_count)) * (mean(position_history) if position_history else 0.5),
                "front_density": front_density, "forward_density": forward_density,
                "mid_density": mid_density, "rear_density": rear_density,
                "expected_front_count": sum(value >= 0.67 for value in expected_position_values),
                "expected_position_mean": mean(expected_position_values),
                "expected_position_std": pstdev(expected_position_values) if len(expected_position_values) > 1 else 0.0,
                "popularity": integer(row.get("Ninki")), "odds": number(row.get("Odds")),
                "actual_rank": integer(row.get("KakuteiJyuni")), "umaban": integer(row.get("Umaban")),
                "horse_name": text(row.get("Bamei")), "field_size": len(horses),
                "career_races": current["races"], "career_wins": current["wins"],
                "career_win_rate": current["wins"] / current["races"] if current["races"] else 0.0,
                "career_places": current["places"], "career_place_rate": current["places"] / current["races"] if current["races"] else 0.0,
                "horse_win_rate": current["wins"] / current["races"] if current["races"] else 0.0,
                "horse_place_rate": current["places"] / current["races"] if current["races"] else 0.0,
                "horse_race_count": current["races"],
                "horse_mean_finish": current.get("finish_sum", 0.0) / current["races"] if current["races"] else 0.0,
                "horse_normalized_mean_finish": current.get("normalized_finish_sum", 0.0) / current["races"] if current["races"] else 0.5,
                "age": integer(row.get("Barei")), "carried_weight": weight,
                "last1_closing_speed": recent_closing_speed[0] if len(recent_closing_speed) > 0 else 0.5,
                "last2_closing_speed": recent_closing_speed[1] if len(recent_closing_speed) > 1 else 0.5,
                "last3_closing_speed": recent_closing_speed[2] if len(recent_closing_speed) > 2 else 0.5,
                "mean_closing_speed_last3": mean(recent_closing_speed) if recent_closing_speed else 0.5,
                "best_closing_speed_last3": max(recent_closing_speed) if recent_closing_speed else 0.5,
                "last1_late_frontness": recent_late_frontness[0] if len(recent_late_frontness) > 0 else 0.5,
                "last2_late_frontness": recent_late_frontness[1] if len(recent_late_frontness) > 1 else 0.5,
                "last3_late_frontness": recent_late_frontness[2] if len(recent_late_frontness) > 2 else 0.5,
                "mean_late_frontness_last3": mean(recent_late_frontness) if recent_late_frontness else 0.5,
                "position_closing_power_last1": recent_position_closing_power[0] if len(recent_position_closing_power) > 0 else 0.25,
                "position_closing_power_last2_mean": mean(recent_position_closing_power[:2]) if recent_position_closing_power else 0.25,
                "position_closing_power_last3_mean": mean(recent_position_closing_power) if recent_position_closing_power else 0.25,
                "best_position_closing_power_last3": max(recent_position_closing_power) if recent_position_closing_power else 0.25,
                "horse_distance_aptitude": horse_distance_aptitude, "distance_aptitude_sample_count": distance_aptitude_sample_count,
                "horse_surface_aptitude": horse_surface_aptitude, "surface_aptitude_sample_count": surface_aptitude_sample_count,
                "horse_rest_aptitude": horse_rest_aptitude, "rest_aptitude_sample_count": rest_aptitude_sample_count,
                "horse_gate_aptitude": horse_gate_aptitude, "gate_aptitude_sample_count": gate_aptitude_sample_count,
                "recent3_win_rate": mean(item["win"] for item in recent3) if recent3 else 0.0,
                "recent3_place_rate": mean(item["place"] for item in recent3) if recent3 else 0.0,
                "recent5_win_rate": mean(item["win"] for item in recent5) if recent5 else 0.0,
                "recent5_place_rate": mean(item["place"] for item in recent5) if recent5 else 0.0,
                "races_last_180d": sum((date_value - item_date).days <= 180 for item_date in race_dates[horse]),
                "races_last_365d": len(race_dates[horse]),
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
                "last1_winner_strength_v2": v2_winner[0] if len(v2_winner) > 0 else 0.0,
                "last2_winner_strength_v2": v2_winner[1] if len(v2_winner) > 1 else 0.0,
                "last3_winner_strength_v2": v2_winner[2] if len(v2_winner) > 2 else 0.0,
                "last1_field_strength_v2": v2_field[0] if len(v2_field) > 0 else 0.0,
                "last2_field_strength_v2": v2_field[1] if len(v2_field) > 1 else 0.0,
                "last3_field_strength_v2": v2_field[2] if len(v2_field) > 2 else 0.0,
                "last1_margin_x_winner_strength_v2": v2_recent[0]["margin"] * v2_winner[0] if v2_recent and v2_recent[0]["margin"] is not None else 0.0,
                "last2_margin_x_winner_strength_v2": v2_recent[1]["margin"] * v2_winner[1] if len(v2_recent) > 1 and v2_recent[1]["margin"] is not None else 0.0,
                "last3_margin_x_winner_strength_v2": v2_recent[2]["margin"] * v2_winner[2] if len(v2_recent) > 2 and v2_recent[2]["margin"] is not None else 0.0,
                "max_winner_strength_last3": max(v2_winner) if v2_winner else 0.0,
                "mean_winner_strength_last3": mean(v2_winner) if v2_winner else 0.0,
                "weighted_winner_strength_last3": sum(value * weight for value, weight in zip(v2_winner, (0.5, 0.3, 0.2))),
                "best_strong_opponent_performance_last3": max((item["winner"] - (item["margin"] or 0.0) for item in v2_recent), default=0.0),
                "last1_field_max_strength_v2": v2_recent[0]["field_max"] if len(v2_recent) > 0 else 0.0,
                "last2_field_max_strength_v2": v2_recent[1]["field_max"] if len(v2_recent) > 1 else 0.0,
                "last3_field_max_strength_v2": v2_recent[2]["field_max"] if len(v2_recent) > 2 else 0.0,
                "last1_field_top3_mean_strength_v2": v2_recent[0]["field_top3"] if len(v2_recent) > 0 else 0.0,
                "last2_field_top3_mean_strength_v2": v2_recent[1]["field_top3"] if len(v2_recent) > 1 else 0.0,
                "last3_field_top3_mean_strength_v2": v2_recent[2]["field_top3"] if len(v2_recent) > 2 else 0.0,
                "opponent_history_missing_last3": v2_missing,
                "last1_winner_max_prize_before_target": v2_recent[0]["max_prize"] if len(v2_recent) > 0 else 0.0,
                "last2_winner_max_prize_before_target": v2_recent[1]["max_prize"] if len(v2_recent) > 1 else 0.0,
                "last3_winner_max_prize_before_target": v2_recent[2]["max_prize"] if len(v2_recent) > 2 else 0.0,
                "last1_winner_mean_prize_before_target": v2_recent[0]["mean_prize"] if len(v2_recent) > 0 else 0.0,
                "last2_winner_mean_prize_before_target": v2_recent[1]["mean_prize"] if len(v2_recent) > 1 else 0.0,
                "last3_winner_mean_prize_before_target": v2_recent[2]["mean_prize"] if len(v2_recent) > 2 else 0.0,
                "last1_winner_max_race_class_before_target": v2_recent[0]["max_class"] if len(v2_recent) > 0 else 0,
                "last2_winner_max_race_class_before_target": v2_recent[1]["max_class"] if len(v2_recent) > 1 else 0,
                "last3_winner_max_race_class_before_target": v2_recent[2]["max_class"] if len(v2_recent) > 2 else 0,
                "last1_winner_best_win_class_before_target": v2_recent[0]["best_win_class"] if len(v2_recent) > 0 else 0,
                "last2_winner_best_win_class_before_target": v2_recent[1]["best_win_class"] if len(v2_recent) > 1 else 0,
                "last3_winner_best_win_class_before_target": v2_recent[2]["best_win_class"] if len(v2_recent) > 2 else 0,
                "last1_raw_performance": raw_recent[0] if len(raw_recent) > 0 else 0.0,
                "last2_raw_performance": raw_recent[1] if len(raw_recent) > 1 else 0.0,
                "last3_raw_performance": raw_recent[2] if len(raw_recent) > 2 else 0.0,
                "last1_adjusted_performance": adjusted_recent[0] if len(adjusted_recent) > 0 else 0.0,
                "last2_adjusted_performance": adjusted_recent[1] if len(adjusted_recent) > 1 else 0.0,
                "last3_adjusted_performance": adjusted_recent[2] if len(adjusted_recent) > 2 else 0.0,
                "last1_position_advantage": recent3[0].get("position_advantage", 0.0) if len(recent3) > 0 else 0.0,
                "last2_position_advantage": recent3[1].get("position_advantage", 0.0) if len(recent3) > 1 else 0.0,
                "last3_position_advantage": recent3[2].get("position_advantage", 0.0) if len(recent3) > 2 else 0.0,
                "last1_race_position_bias": recent3[0].get("position_bias", 0.0) if len(recent3) > 0 else 0.0,
                "last2_race_position_bias": recent3[1].get("position_bias", 0.0) if len(recent3) > 1 else 0.0,
                "last3_race_position_bias": recent3[2].get("position_bias", 0.0) if len(recent3) > 2 else 0.0,
                "best_adjusted_performance_last3": max(adjusted_recent) if adjusted_recent else 0.0,
                "mean_adjusted_performance_last3": mean(adjusted_recent) if adjusted_recent else 0.0,
                "weighted_adjusted_performance_last3": sum(value * weight for value, weight in zip(adjusted_recent, (0.5, 0.3, 0.2))),
                "class_change_last1": class_change_last1,
                "class_change_last3_mean": class_change_last3_mean,
                "hidden_strength_last1": hidden_recent[0] if len(hidden_recent) > 0 else 0.0,
                "hidden_strength_last2": hidden_recent[1] if len(hidden_recent) > 1 else 0.0,
                "hidden_strength_last3": hidden_recent[2] if len(hidden_recent) > 2 else 0.0,
                "max_hidden_strength_last3": max(hidden_recent) if hidden_recent else 0.0,
                "max_strong_against_bias_last3": max(against_recent) if against_recent else 0.0,
                "strong_against_bias_last1": against_recent[0] if len(against_recent) > 0 else 0.0,
                "strong_against_bias_last2": against_recent[1] if len(against_recent) > 1 else 0.0,
                "strong_against_bias_last3": against_recent[2] if len(against_recent) > 2 else 0.0,
                "strong_against_bias_v2_last1": against_recent[0] if len(against_recent) > 0 else 0.0,
                "strong_against_bias_v2_last2": against_recent[1] if len(against_recent) > 1 else 0.0,
                "strong_against_bias_v2_last3": against_recent[2] if len(against_recent) > 2 else 0.0,
                "setup_benefit_last1": recent3[0].get("setup_benefit", 0.0) if len(recent3) > 0 else 0.0,
                "setup_benefit_last2": recent3[1].get("setup_benefit", 0.0) if len(recent3) > 1 else 0.0,
                "setup_benefit_last3": recent3[2].get("setup_benefit", 0.0) if len(recent3) > 2 else 0.0,
                "adjusted_performance_v2_last1": adjusted_recent[0] if len(adjusted_recent) > 0 else 0.0,
                "adjusted_performance_v2_last2": adjusted_recent[1] if len(adjusted_recent) > 1 else 0.0,
                "adjusted_performance_v2_last3": adjusted_recent[2] if len(adjusted_recent) > 2 else 0.0,
                "mean_adjusted_performance_v2_last3": mean(adjusted_recent) if adjusted_recent else 0.0,
                "best_adjusted_performance_v2_last3": max(adjusted_recent) if adjusted_recent else 0.0,
                "weighted_adjusted_performance_v2_last3": sum(value * weight for value, weight in zip(adjusted_recent, (0.5, 0.3, 0.2))),
                "max_strong_against_bias_v2_last3": max(against_recent) if against_recent else 0.0,
                "race_position_bias_last1": recent3[0].get("position_bias", 0.0) if len(recent3) > 0 else 0.0,
                "race_position_bias_last2": recent3[1].get("position_bias", 0.0) if len(recent3) > 1 else 0.0,
                "race_position_bias_last3": recent3[2].get("position_bias", 0.0) if len(recent3) > 2 else 0.0,
                "setup_improvement": -recent3[0].get("position_advantage", 0.0) if recent3 else 0.0,
                "hidden_strength_x_race_strength": (hidden_recent[0] * (v2_winner[0] + prize_log(current_first_prize) / 20.0)) if hidden_recent else 0.0,
                "jockey_rides": jockey_state[text(row.get("KisyuCode"))]["rides"],
                "jockey_win_rate": (jockey_state[text(row.get("KisyuCode"))]["wins"] + 1) / (jockey_state[text(row.get("KisyuCode"))]["rides"] + 5),
                "jockey_top2_rate": (jockey_state[text(row.get("KisyuCode"))]["top2"] + 1) / (jockey_state[text(row.get("KisyuCode"))]["rides"] + 5),
                "jockey_place_rate": (jockey_state[text(row.get("KisyuCode"))]["places"] + 1) / (jockey_state[text(row.get("KisyuCode"))]["rides"] + 5),
                "jockey_added_value": (jockey_state[text(row.get("KisyuCode"))]["added_sum"] / max(1, jockey_state[text(row.get("KisyuCode"))]["rides"])),
                "recent_jockey_added_value": mean(jockey_state[text(row.get("KisyuCode"))]["recent"]) if jockey_state[text(row.get("KisyuCode"))]["recent"] else 0.0,
                "jockey_change_added_value": 0.0,
                "usable_history_count": len(histories[horse]),
                "usable_position_history_count": len(position_history),
                "usable_performance_history_count": len(raw_recent),
            }
            # inject course x gate and bloodline features into values
            values.update({
                "course_gate_sample_count": cg_races,
                "course_gate_win_rate": cg_win_rate,
                "course_gate_place_rate": cg_place_rate,
                "course_gate_win_rate_shrink": cg_win_rate_shrink,
                "sire_id": sire_id,
                "sire_race_count": sire_races,
                "sire_win_rate": sire_win_rate,
                "sire_place_rate": sire_place_rate,
                "sire_win_rate_shrink": sire_win_rate_shrink,
                "damsire_id": damsire_id,
                "damsire_race_count": damsire_races,
                "damsire_win_rate": damsire_win_rate,
                "damsire_place_rate": damsire_place_rate,
                "damsire_win_rate_shrink": damsire_win_rate_shrink,
            })
            if history_trace is not None and horse == history_trace.get("horse_id") and race_id(horses[0]) == history_trace.get("target_race_id"):
                history_trace["performance_used"] = [item["source_race_id"] for item in recent3]
                history_trace["position_used"] = [item["source_race_id"] for item in histories[horse]]
                history_trace["last_used"] = [item["source_race_id"] for item in recent3]
                history_trace["final_features"] = {name: values.get(name) for name in ("usable_history_count", "usable_position_history_count", "usable_performance_history_count", "last1_margin", "last1_raw_performance", "last1_adjusted_performance", "horse_expected_position", "position_stability")}
            recent_conditions = [item.get("condition", {}) for item in recent3]
            recent_scores = [item.get("class_score", 0) for item in recent_conditions]
            recent_margins = [item.get("margin") or 0 for item in recent3]
            recent_prizes = [item.get("first_prize", 0.0) for item in recent3]
            recent_prize_logs = [prize_log(value) for value in recent_prizes]
            values.update({
                "last1_race_first_prize": recent_prizes[0] if len(recent_prizes) > 0 else 0.0,
                "last2_race_first_prize": recent_prizes[1] if len(recent_prizes) > 1 else 0.0,
                "last3_race_first_prize": recent_prizes[2] if len(recent_prizes) > 2 else 0.0,
                "last1_race_first_prize_log": recent_prize_logs[0] if len(recent_prize_logs) > 0 else 0.0,
                "last2_race_first_prize_log": recent_prize_logs[1] if len(recent_prize_logs) > 1 else 0.0,
                "last3_race_first_prize_log": recent_prize_logs[2] if len(recent_prize_logs) > 2 else 0.0,
                "max_race_prize_last3": max(recent_prizes) if recent_prizes else 0.0,
                "mean_race_prize_last3": mean(recent_prizes) if recent_prizes else 0.0,
                "weighted_race_prize_last3": sum(value * weight for value, weight in zip(recent_prizes, (0.5, 0.3, 0.2))),
                "prize_change_from_last1": current_first_prize - recent_prizes[0] if recent_prizes else 0.0,
                "prize_change_from_last3_mean": current_first_prize - mean(recent_prizes) if recent_prizes else 0.0,
                "prize_ratio_vs_last1": current_first_prize / recent_prizes[0] if recent_prizes and recent_prizes[0] > 0 else 1.0,
                "prize_ratio_vs_last3_mean": current_first_prize / mean(recent_prizes) if recent_prizes and mean(recent_prizes) > 0 else 1.0,
                "last1_margin_x_prize_strength": recent_margins[0] * recent_prize_logs[0] if recent_margins else 0.0,
                "last2_margin_x_prize_strength": recent_margins[1] * recent_prize_logs[1] if len(recent_margins) > 1 else 0.0,
                "last3_margin_x_prize_strength": recent_margins[2] * recent_prize_logs[2] if len(recent_margins) > 2 else 0.0,
                "current_race_class_score": current_condition["class_score"],
                "last1_race_class_score": recent_scores[0] if len(recent_scores) > 0 else 0,
                "last2_race_class_score": recent_scores[1] if len(recent_scores) > 1 else 0,
                "last3_race_class_score": recent_scores[2] if len(recent_scores) > 2 else 0,
                "max_race_class_last3": max(recent_scores) if recent_scores else 0,
                "mean_race_class_last3": mean(recent_scores) if recent_scores else 0,
                "weighted_race_class_last3": sum(value * weight for value, weight in zip(recent_scores, (0.5, 0.3, 0.2))),
                "last1_margin_x_race_class": (recent_margins[0] if len(recent_margins) > 0 else 0) * (recent_scores[0] if len(recent_scores) > 0 else 0),
                "last2_margin_x_race_class": (recent_margins[1] if len(recent_margins) > 1 else 0) * (recent_scores[1] if len(recent_scores) > 1 else 0),
                "last3_margin_x_race_class": (recent_margins[2] if len(recent_margins) > 2 else 0) * (recent_scores[2] if len(recent_scores) > 2 else 0),
                "last1_sex_condition": recent_conditions[0].get("sex", "UNKNOWN") if len(recent_conditions) > 0 else "UNKNOWN",
                "last2_sex_condition": recent_conditions[1].get("sex", "UNKNOWN") if len(recent_conditions) > 1 else "UNKNOWN",
                "last3_sex_condition": recent_conditions[2].get("sex", "UNKNOWN") if len(recent_conditions) > 2 else "UNKNOWN",
                "last1_age_condition": recent_conditions[0].get("age", "UNKNOWN") if len(recent_conditions) > 0 else "UNKNOWN",
                "last2_age_condition": recent_conditions[1].get("age", "UNKNOWN") if len(recent_conditions) > 1 else "UNKNOWN",
                "last3_age_condition": recent_conditions[2].get("age", "UNKNOWN") if len(recent_conditions) > 2 else "UNKNOWN",
                "last1_is_filly_mare_only": recent_conditions[0].get("filly_only", 0) if len(recent_conditions) > 0 else 0,
                "last2_is_filly_mare_only": recent_conditions[1].get("filly_only", 0) if len(recent_conditions) > 1 else 0,
                "last3_is_filly_mare_only": recent_conditions[2].get("filly_only", 0) if len(recent_conditions) > 2 else 0,
                "race_class_change": current_condition["class_score"] - (recent_scores[0] if recent_scores else 0),
                "female_only_to_open": int(bool(recent_conditions) and recent_conditions[0].get("filly_only", 0) == 1 and current_condition["filly_only"] == 0),
                "open_to_female_only": int(bool(recent_conditions) and recent_conditions[0].get("filly_only", 0) == 0 and current_condition["filly_only"] == 1),
                "age_condition_change": int(bool(recent_conditions) and recent_conditions[0].get("age") != current_condition["age"]),
            })
            if feature_target_ids is None or race_id(horses[0]) in feature_target_ids:
                features.append(values)
        for row in horses:
            horse = text(row.get("KettoNum"))
            winner = next((item for item in horses if integer(item.get("KakuteiJyuni")) == 1), None)
            horse_history = list(histories[horse])
            prior_class = mean([float(item.get("class_score", 0.0)) for item in horse_history]) if horse_history else 0.0
            prior_pace = mean([float(item.get("pace_score", 0.5)) for item in horse_history]) if horse_history else 0.5
            raw_performance, adjusted_performance, adjustment_total = performance_from_result({
                "margin": margin_value(row),
                "class_delta": current_condition["class_score"] - prior_class,
                "pace_delta": mean(observed_frontness) - prior_pace,
                "opponent_delta": field_strength - smoothed_strength(stats[horse]),
            })
            previous_date = horse_history[-1]["date"] if horse_history else None
            is_winner = winner is not None and horse == text(winner.get("KettoNum"))
            pending_updates.append((horse, {"date": date_value, "finish": integer(row.get("KakuteiJyuni")), "margin": margin_value(row),
                                     "source_race_id": race_id(row),
                                     "winning_margin": winning_margin_value if is_winner else 0.0,
                                     "history_allowed": history_policy_allows(row, history_policy),
                                     "win": int(integer(row.get("KakuteiJyuni")) == 1), "place": int(1 <= integer(row.get("KakuteiJyuni")) <= 3),
                                     "winner_strength": winner_strength, "field_strength": field_strength,
                                     "distance": integer(row.get("race_Kyori") or row.get("Kyori")), "class_code": class_code(row),
                                     "condition": current_condition, "class_score": current_condition["class_score"],
                                     "raw_performance": raw_performance, "adjusted_performance": adjusted_performance,
                                     "adjustment_total": adjustment_total, "distance_change": (integer(row.get("race_Kyori") or row.get("Kyori")) - (horse_history[-1].get("distance", integer(row.get("race_Kyori") or row.get("Kyori"))) if horse_history else integer(row.get("race_Kyori") or row.get("Kyori")))) / 1000.0,
                                     "pace_score": mean(observed_frontness), "interval_norm": normalized_interval((date_value - previous_date).days) if previous_date else None,
                                     "racecourse": JYO_NAMES.get(text(row.get("idJyoCD")).zfill(2), text(row.get("idJyoCD"))),
                                     "track_condition": condition_value(row), "season": (date_value.month - 1) // 3,
                                     "surface": surface(row), "distance_band": distance_band(integer(row.get("race_Kyori") or row.get("Kyori"))),
                                     "gate_band": gate_band(integer(row.get("Wakuban")), field_count),
                                     "rest_band": rest_band((date_value - previous_date).days if previous_date else None),
                                     "gate": integer(row.get("Wakuban")), "weight": number(row.get("Futan")),
                                     "first_prize": current_first_prize,
                                     "winner_class_score": current_condition["class_score"],
                                     "winner_id": text(winner.get("KettoNum")) if winner else "",
                                     "participants": [text(item.get("KettoNum")) for item in horses],
                                     "field_size": field_count, "position_bias": position_bias,
                                     "position_advantage": observed_frontness[horses.index(row)] - mean(observed_frontness),
                                     "first_corner_position": first_corner_position(row),
                                     "frontness": observed_frontness[horses.index(row)], "geometry_signature": current_geometry,
                                     "late_frontness": observed_late_frontness[horses.index(row)],
                                     "closing_speed": observed_closing_speed[horses.index(row)],
                                     "expected_rank": expected_order.get(horse, field_count), "jockey": text(row.get("KisyuCode")),
                                     "strong_against_bias_v2": -residual_bias * (observed_frontness[horses.index(row)] - mean(observed_frontness)),
                                     "setup_benefit": position_bias * (observed_frontness[horses.index(row)] - mean(observed_frontness))}))
            # attach sire/damsire identifiers for later aggregation if available
            pending_updates[-1][1]["sire"] = text(row.get("Sire") or row.get("race_Sire") or row.get("SIRE_ID") or row.get("sire") or "")
            pending_updates[-1][1]["damsire"] = text(row.get("Damsire") or row.get("DamSire") or row.get("DAM_SIRE_ID") or row.get("damsire") or "")
            jockey = text(row.get("KisyuCode"))
            actual_finish = integer(row.get("KakuteiJyuni"))
            added = (expected_order.get(horse, field_count) - actual_finish) / max(1, field_count)
            jockey_state[jockey]["rides"] += 1
            jockey_state[jockey]["wins"] += int(actual_finish == 1)
            jockey_state[jockey]["top2"] += int(actual_finish <= 2)
            jockey_state[jockey]["places"] += int(actual_finish <= 3)
            jockey_state[jockey]["added_sum"] += added
            jockey_state[jockey]["recent"].append(added)
    for horse, result in pending_updates:
        if history_trace is not None and horse == history_trace.get("horse_id"):
            history_trace.setdefault("source", []).append({"source_race_id": result["source_race_id"],
                "history_allowed": result.get("history_allowed", True), "event": "state_update_skipped" if not result.get("history_allowed", True) else "state_update"})
        if not result.get("history_allowed", True):
            continue
        stats[horse]["races"] += 1
        stats[horse]["wins"] += result["win"]
        stats[horse]["places"] += result["place"]
        stats[horse]["adjusted_sum"] += result.get("adjusted_performance", 0.0)
        stats[horse]["adjusted_count"] += 1
        stats[horse]["max_class"] = max(stats[horse]["max_class"], result.get("class_score", 0))
        if result["win"]:
            stats[horse]["best_win_class"] = max(stats[horse]["best_win_class"], result.get("class_score", 0))
        prize = result.get("first_prize", 0.0)
        stats[horse]["max_prize"] = max(stats[horse]["max_prize"], prize)
        stats[horse]["mean_prize"] = (stats[horse]["mean_prize"] * stats[horse]["prize_count"] + prize) / (stats[horse]["prize_count"] + 1)
        stats[horse]["prize_count"] += 1
        stats[horse]["finish_sum"] += result["finish"]
        stats[horse]["normalized_finish_sum"] += (result["finish"] - 1) / max(1, result["field_size"] - 1)
        histories[horse].append(result)
        if history_trace is not None and horse == history_trace.get("horse_id"):
            history_trace.setdefault("appended", []).append(result["source_race_id"])
        race_dates[horse].append(current_date)
    phase5_profile(f"history built: {time.perf_counter() - started:.2f}s, feature_rows={len(features)}, races={len(sorted_races)}, memory={memory_mb():.1f}MB")
    return features


def evaluate_v1(data: list[dict], pays: dict, start: date, end: date,
                feature_builder=build_v1_features, feature_columns=None,
                model_label="v1", history_policy="baseline",
                min_race_first_prize: float | None = None) -> tuple[list[dict], list[dict]]:
    try:
        import lightgbm as lgb
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("v1にはLightGBMが必要です。.venv/bin/python -m src.backtest ... を使用してください。") from exc
    feature_columns = feature_columns or V1_FEATURES
    started = time.perf_counter()
    eligible_target_ids = eligible_target_race_ids(data, min_race_first_prize)
    if history_policy == "baseline" and os.environ.get("PHASE5_USE_CACHE") == "1" and model_label in {"E", "F", "G", "CA", "CB"}:
        cached_result = evaluate_cached_dataframe(data, pays, start, end, feature_columns, model_label,
                                                  {race_id(row) for row in data if start <= row["date"] < end
                                                   and (eligible_target_ids is None or race_id(row) in eligible_target_ids)},
                                                  eligible_target_ids)
        if cached_result is not None:
            phase5_profile(f"DataFrame cached execution complete: model={model_label}, predictions={len(cached_result[0])}")
            return cached_result
    feature_rows = read_feature_cache(len(data), model_label) if os.environ.get("PHASE5_USE_CACHE") == "1" else None
    if feature_rows is None:
        feature_rows = feature_builder(data, history_policy=history_policy)
        if history_policy == "baseline" and os.environ.get("PHASE5_WRITE_CACHE") == "1":
            write_feature_cache(feature_rows, len(data), model_label)
    target_ids = {race_id(row) for row in data if start <= row["date"] < end and (eligible_target_ids is None or race_id(row) in eligible_target_ids)}
    if target_ids:
        feature_rows = [row for row in feature_rows if row.get("date") < start or row.get("race_id") in target_ids]
        phase5_profile(f"cached feature selection: rows={len(feature_rows)}, target_races={len(target_ids)}")
    phase5_profile(f"feature construction finished: {time.perf_counter() - started:.2f}s, rows={len(feature_rows)}, memory={memory_mb():.1f}MB")
    trainable = [row for row in feature_rows if row["date"] < start and (eligible_target_ids is None or row.get("race_id") in eligible_target_ids)]
    evaluation = [row for row in feature_rows if start <= row["date"] < end and (eligible_target_ids is None or row.get("race_id") in eligible_target_ids)]
    months = sorted({month_start(row["date"]) for row in evaluation})
    output, importance = [], defaultdict(lambda: {"gain": 0.0, "split": 0.0})
    for month in months:
        month_started = time.perf_counter()
        train = [row for row in trainable if row["date"] < month]
        test = [row for row in evaluation if month_start(row["date"]) == month]
        if not train or not test or len({row["target"] for row in train}) < 2:
            continue
        categorical = ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"]
        if "race_sex_condition" in feature_columns:
            categorical += ["race_sex_condition", "race_age_condition", "last1_sex_condition", "last2_sex_condition", "last3_sex_condition",
                            "last1_age_condition", "last2_age_condition", "last3_age_condition"]
        columns = feature_columns + categorical
        train_df = pd.DataFrame(train)[columns]
        test_df = pd.DataFrame(test)[columns]
        combined = pd.concat([train_df, test_df], ignore_index=True)
        combined = pd.get_dummies(combined, columns=categorical, dummy_na=True)
        train_matrix = combined.iloc[:len(train)].astype(float)
        test_matrix = combined.iloc[len(train):].astype(float)
        original_columns = list(train_matrix.columns)
        write_feature_list(ROOT / "reports" / f"features_model_{model_label.lower()}_actual.txt", original_columns)
        safe_columns = [f"f_{index}" for index in range(len(original_columns))]
        train_matrix.columns = safe_columns
        test_matrix.columns = safe_columns
        model = lgb.LGBMClassifier(n_estimators=180, learning_rate=0.04, num_leaves=15, max_depth=5,
                                   min_child_samples=80, reg_lambda=2.0, verbosity=-1, random_state=42)
        model.fit(train_matrix, [row["target"] for row in train])
        phase5_profile(f"LightGBM training {model_label} {month}: {time.perf_counter() - month_started:.2f}s, train={len(train)}, test={len(test)}, memory={memory_mb():.1f}MB")
        for name, gain, split in zip(original_columns, model.booster_.feature_importance("gain"), model.booster_.feature_importance("split")):
            importance[name]["gain"] += float(gain); importance[name]["split"] += float(split)
        probabilities = model.predict_proba(test_matrix)[:, 1]
        phase5_profile(f"prediction {model_label} {month}: {time.perf_counter() - month_started:.2f}s")
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
                               "prediction_reason": f"LightGBM {model_label}:近走着差・勝ち馬強度・フィールド強度・基礎能力"})
    phase5_profile(f"metrics/output rows prepared: {time.perf_counter() - started:.2f}s, predictions={len(output)}, memory={memory_mb():.1f}MB")
    return output, [{"feature": name, **values} for name, values in sorted(importance.items(), key=lambda item: item[1]["gain"], reverse=True)]


def evaluate_v2(data: list[dict], pays: dict, start: date, end: date) -> tuple[list[dict], list[dict]]:
    return evaluate_v1(data, pays, start, end, feature_builder=build_v1_features,
                       feature_columns=V2_FEATURES, model_label="v2")


# Old-netkeiba feature rebuild, Phase A: basic age/weight/career-finish signals absent from G baseline.
NETKEIBA_PHASE_A_FEATURES = ["age", "carried_weight", "horse_win_rate", "horse_place_rate",
                            "horse_race_count", "horse_mean_finish", "horse_normalized_mean_finish"]
# Phase B: HaronTimeL3-normalized closing speed, late-corner frontness, and position x closing power.
NETKEIBA_PHASE_B_FEATURES = [
    "last1_closing_speed", "last2_closing_speed", "last3_closing_speed",
    "mean_closing_speed_last3", "best_closing_speed_last3",
    "last1_late_frontness", "last2_late_frontness", "last3_late_frontness", "mean_late_frontness_last3",
    "position_closing_power_last1", "position_closing_power_last2_mean",
    "position_closing_power_last3_mean", "best_position_closing_power_last3",
]
# Phase C: horse-level distance/surface/rest/gate aptitude. Ground aptitude reuses existing track_condition_fit.
NETKEIBA_PHASE_C_FEATURES = [
    "horse_distance_aptitude", "horse_surface_aptitude", "horse_rest_aptitude", "horse_gate_aptitude",
]

# Phase D: course x gate historical win/place rates
NETKEIBA_PHASE_D_FEATURES = [
    "course_gate_win_rate", "course_gate_place_rate", "course_gate_sample_count", "course_gate_win_rate_shrink",
]

# Phase G: bloodline (sire/damsire) aggregated signals
NETKEIBA_PHASE_G_FEATURES = [
    "sire_win_rate", "sire_place_rate", "sire_race_count",
    "damsire_win_rate", "damsire_place_rate", "damsire_race_count",
]


def evaluate_stage(data: list[dict], pays: dict, start: date, end: date, stage: str, history_policy="baseline",
                  min_race_first_prize: float | None = None):
    if stage in REBUILD_POLICY_FEATURES:
        return evaluate_v1(data, pays, start, end, feature_columns=REBUILD_POLICY_FEATURES[stage], model_label=stage,
                           history_policy=history_policy, min_race_first_prize=min_race_first_prize)
    columns = V1_FEATURES
    if stage == "B":
        columns = V1_FEATURES + RACE_CLASS_FEATURES
    elif stage == "C":
        columns = V1_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES
    elif stage == "D":
        columns = PRIZE_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES
    elif stage == "E":
        columns = PHASE4_FEATURES_E + RACE_CONDITION_FEATURES + PRIZE_FEATURES
    elif stage == "F":
        columns = PHASE5_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES
    elif stage == "G":
        columns = PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES
    elif stage == "RA":
        columns = PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_A_FEATURES
    elif stage == "RB":
        columns = PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_B_FEATURES
    elif stage == "RC":
        columns = PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_C_FEATURES
    elif stage == "CA":
        columns = CLEANUP_A_FEATURES
    elif stage == "CB":
        columns = CLEANUP_B_FEATURES
    cache_label = stage if history_policy == "baseline" else f"{stage}_{history_policy}"
    return evaluate_v1(data, pays, start, end, feature_columns=columns, model_label=cache_label,
                       history_policy=history_policy, min_race_first_prize=min_race_first_prize)


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


def write_feature_list(path: Path, features: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(features) + "\n", encoding="utf-8")


def write_condition_validation(data: list[dict], output: Path) -> None:
    counts = defaultdict(int)
    sex_counts = defaultdict(int)
    age_counts = defaultdict(int)
    examples = []
    for row in data:
        condition = race_conditions(row)
        counts[condition["class_label"]] += 1
        sex_counts[condition["sex"]] += 1
        age_counts[condition["age"]] += 1
        if len(examples) < 40 and condition["class_label"] == "UNKNOWN":
            examples.append({"race_id": race_id(row), "race_name": text(row.get("race_RaceInfoHondai")),
                             "condition_name": text(row.get("race_JyokenName")), "grade_code": text(row.get("race_GradeCD")),
                             "condition_code": text(row.get("race_JyokenInfoSyubetuCD")), "race_class_label": "UNKNOWN"})
    total = sum(counts.values())
    summary = [{"race_class_label": label, "races": count, "ratio": count / total if total else 0,
                "unknown_warning": "INVESTIGATE" if label == "UNKNOWN" and count / total > 0.2 else ""}
               for label, count in sorted(counts.items())]
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "race_class_distribution.csv", summary)
    write_csv(output / "race_sex_condition_distribution.csv",
              [{"race_sex_condition": key, "races": value, "ratio": value / total if total else 0}
               for key, value in sorted(sex_counts.items())])
    write_csv(output / "race_age_condition_distribution.csv",
              [{"race_age_condition": key, "races": value, "ratio": value / total if total else 0}
               for key, value in sorted(age_counts.items())])
    write_csv(output / "race_class_unknown_examples.csv", examples)
    (output / "condition_validation.md").write_text(
        "# Race Condition Validation\n\n" +
        "| Label | Races | Ratio |\n|---|---:|---:|\n" +
        "\n".join(f"| {row['race_class_label']} | {row['races']} | {row['ratio']:.2%} |" for row in summary) +
        "\n\n`GradeCD` validation: A=G1, B=G2, C=G3, L=Listed was checked against known central race names. Other codes remain UNKNOWN.\n"
        "`race_sex_condition` uses race-name evidence containing `牝`/`牝馬`; no SexCD numeric meaning is guessed.\n",
        encoding="utf-8")


def write_prize_validation(data: list[dict], output: Path) -> None:
    rows = []
    for row in data:
        first = prize_amount(row.get("race_Honsyokin0"))
        total = sum(prize_amount(row.get(f"race_Honsyokin{i}")) for i in range(5))
        rows.append({"class": race_conditions(row)["class_label"], "first_prize": first, "total_prize": total})
    available = [row for row in rows if row["first_prize"] > 0]
    known = defaultdict(list)
    for row in available:
        known[row["class"]].append(row["first_prize"])
    distribution = [{"race_class": label, "races": len(values), "median_first_prize": sorted(values)[len(values) // 2],
                    "mean_first_prize": mean(values), "min_first_prize": min(values), "max_first_prize": max(values)}
                   for label, values in sorted(known.items())]
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "prize_summary_by_class.csv", distribution)
    write_csv(output / "prize_availability.csv", [{"total_races": len(rows), "first_prize_available": len(available),
                                                    "availability_rate": len(available) / len(rows) if rows else 0,
                                                    "unknown_class_races": sum(row["class"] == "UNKNOWN" for row in rows),
                                                    "unknown_class_prize_available": sum(row["class"] == "UNKNOWN" and row["first_prize"] > 0 for row in rows)}])


def write_report(rows: list[dict], output: Path, metadata: dict, feature_importance: list[dict] | None = None) -> None:
    report_started = time.perf_counter()
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
    phase5_profile(f"CSV/report output finished: {time.perf_counter() - report_started:.2f}s, output={output}, memory={memory_mb():.1f}MB")


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


def write_model_comparison(models: dict[str, list[dict]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for label, rows in models.items():
        for subset, predicate in (("all", lambda row: True), ("1plus_code_available", lambda row: row.get("grade_code") not in (None, "unknown")),):
            selected = [row for row in rows if predicate(row)]
            values = metrics(selected)
            bets = betting(selected)
            risk = max_drawdown(selected)
            records.append({"model": label, "subset": subset, "races": values["races"], "auc": values["roc_auc"],
                            "logloss": values["logloss"], "brier": values["brier_score"], "top1": values["top1_hit_rate"],
                            "top3": values["top3_hit_rate"], "win_roi": bets["win"]["roi"], "place_roi": bets["place"]["roi"],
                            "win_max_drawdown": risk["win"]["max_drawdown"], "place_max_drawdown": risk["place"]["max_drawdown"],
                            "win_max_losing_streak": risk["win"]["max_losing_streak"], "place_max_losing_streak": risk["place"]["max_losing_streak"]})
    write_csv(output / "comparison.csv", records)
    nonfavorite = []
    for label, rows in models.items():
        selected = [row for row in rows if row["prediction_rank"] == 1 and row.get("popularity", 0) > 1]
        bets = betting(selected, lambda row: True)
        nonfavorite.append({"model": label, "bets": len(selected), "win_rate": bets["win"]["hit_rate"],
                            "win_roi": bets["win"]["roi"], "place_roi": bets["place"]["roi"]})
    write_csv(output / "nonfavorite_comparison.csv", nonfavorite)
    if "A" in models and "D" in models:
        a_map = {(row["race_id"], row["horse_id"]): row for row in models["A"]}
        changes = []
        for row in models["D"]:
            before = a_map.get((row["race_id"], row["horse_id"]))
            if before:
                changes.append({"horse_name": row.get("horse_name", ""), "race_id": row["race_id"],
                                "A_rank": before.get("prediction_rank"), "D_rank": row.get("prediction_rank"),
                                "A_probability": before.get("predicted_probability"), "D_probability": row.get("predicted_probability"),
                                "actual_rank": row.get("actual_rank"), "popularity": row.get("popularity"),
                                "last1_race_class": row.get("last1_race_class", "UNKNOWN"),
                                "last1_age_condition": row.get("last1_age_condition", "UNKNOWN"),
                                "last1_is_filly_mare_only": row.get("last1_is_filly_mare_only", 0),
                                "last1_winner_strength": row.get("last1_winner_strength_v2", 0)})
        changes.sort(key=lambda row: abs((row["D_probability"] or 0) - (row["A_probability"] or 0)), reverse=True)
        write_csv(output / "prediction_changes_A_to_D.csv", changes[:100])
    (output / "summary.md").write_text(
        "# v0 / v1 / v2 Model Comparison\n\n"
        "| Model | Subset | AUC | LogLoss | Brier | Top1 | Top3 | Win ROI | Place ROI | Win DD | Place DD |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n" +
        "\n".join(f"| {r['model']} | {r['subset']} | {r['auc']} | {r['logloss']} | {r['brier']} | {r['top1']} | {r['top3']} | {r['win_roi']} | {r['place_roi']} | {r['win_max_drawdown']} | {r['place_max_drawdown']} |" for r in records) +
        "\n\n## v1 vs v2\n"
        "v2は対象日以前の勝ち馬・出走馬の平滑化strengthと着差interactionを追加したモデルです。"
        "AUC、LogLoss、Top1/Top3、ROI、ドローダウンは同一レース集合で比較してください。\n\n"
        "クラスコードの公式対応表がないため、1勝/2勝/3勝/OP/L/重賞の意味付き比較は未実施です。"
        "`1plus_code_available` はGradeCDが空でない行の参考比較であり、クラス階層を意味しません。\n",
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
    parser.add_argument("--max-eval-races", type=int, help="評価対象レース数。過去履歴は維持")
    parser.add_argument("--prediction-cache-only", action="store_true", help="Prediction Cacheだけを読み込み、学習・DBロードを省略")
    parser.add_argument("--model", choices=("v0", "v1", "v2", "A", "B", "C", "D", "E", "F", "G", "RA", "RB", "RC", "H", "I", "CA", "CB", "stages", "all"), default="v0")
    parser.add_argument("--min-race-first-prize", type=float, help="対象レースの最低1着本賞金。例: 8000000 or 11400000")
    args = parser.parse_args()
    if args.prediction_cache_only:
        import pandas as pd
        base_categories = ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"]
        cache_feature_map = {
            "E": PHASE4_FEATURES_E + RACE_CONDITION_FEATURES + PRIZE_FEATURES,
            "F": PHASE5_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES,
            **REBUILD_POLICY_FEATURES,
        }
        cache_features = cache_feature_map.get(args.model, [])
        cache_key = model_cache_key(args.model, cache_features, date.fromisoformat(args.start_month + "-01"), date.fromisoformat(args.end_month + "-01"))
        path = prediction_cache_path(args.model, cache_key)
        if not path.exists():
            raise SystemExit(f"Prediction Cache MISS: {path}")
        frame = pd.read_parquet(path)
        phase5_profile(f"Prediction Cache HIT: rows={len(frame)}, columns={len(frame.columns)}")
        print(json.dumps({"cache": str(path), "rows": len(frame), "analysis_ready": True}, ensure_ascii=False))
        return
    data, pays, source = load_data(args.db)
    data = [row for row in data if text(row.get("idJyoCD")).zfill(2) in JYO_NAMES]
    dates = [row["date"] for row in data if valid_result(row)]
    if not dates:
        raise SystemExit("確定済みレースがありません。DBと headDataKubun/KakuteiJyuni を確認してください。")
    end = date.fromisoformat(args.end_month + "-01") if args.end_month else shift_month(month_start(max(dates)), 1)
    start = date.fromisoformat(args.start_month + "-01") if args.start_month else shift_month(end, -args.months)
    if start >= end:
        raise SystemExit("評価期間が不正です。start-month は end-month より前にしてください。")
    data = limit_evaluation_races(data, start, end, args.max_eval_races)
    metadata = {"start_month": start.strftime("%Y-%m"), "end_month_exclusive": end.strftime("%Y-%m"),
                "months": args.months, "source_rows": len(data), "payout_rows": source["pay_rows"],
                "walk_forward": "各評価月の月初より前に確定したレースだけで特徴量生成・学習", "model": args.model}
    base_categories = ["racecourse", "surface", "grade_code", "condition_code", "last1_class", "last2_class", "last3_class"]
    feature_lists = {
        "A": V1_FEATURES + base_categories,
        **{stage: REBUILD_POLICY_FEATURES[stage] for stage in REBUILD_POLICY_FEATURES},
        "CA": CLEANUP_A_FEATURES,
        "CB": CLEANUP_B_FEATURES,
        "G": PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES,
        "RA": PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_A_FEATURES,
        "RB": PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_B_FEATURES,
        "RC": PHASE5_FEATURES + PACE_BIAS_V2_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES + NETKEIBA_PHASE_C_FEATURES,
    }
    for model_name, model_features in feature_lists.items():
        write_feature_list(ROOT / "reports" / f"features_model_{model_name.lower()}.txt", model_features)
    write_condition_validation(data, ROOT / "reports" / "condition_validation")
    write_prize_validation(data, ROOT / "reports" / "condition_validation")
    results = {}
    v0_rows = []
    model_rows = {}
    if args.model in ("v0", "all"):
        rows = evaluate(data, pays, start, end)
        v0_rows = rows
        v0_out = args.out if args.model == "v0" else ROOT / "reports" / "backtest_v0"
        write_report(rows, v0_out, {**metadata, "model": "v0 historical win rate"})
        results["v0"] = len(rows)
        model_rows["v0"] = rows
    if args.model in ("v1", "all"):
        rows, importance = evaluate_v1(data, pays, start, end, min_race_first_prize=args.min_race_first_prize)
        v1_out = args.out if args.model == "v1" else ROOT / "reports" / "backtest_v1"
        write_report(rows, v1_out, {**metadata, "model": "v1 LightGBM recent performance and opponent strength",
                        "features": feature_lists["A"],
                                    "categorical_handling": "pandas get_dummies; unknown category retained; internal LightGBM names sanitized",
                                    "class_method": "GradeCD and JyokenInfoSyubetuCD raw codes; official mapping unavailable"}, importance)
        results["v1"] = len(rows)
        model_rows["v1"] = rows
    if args.model in ("v2", "all"):
        rows, importance = evaluate_v2(data, pays, start, end)
        v2_out = args.out if args.model == "v2" else ROOT / "reports" / "backtest_v2"
        write_report(rows, v2_out, {**metadata, "model": "v2 LightGBM as-of opponent strength",
                        "features": feature_lists["D"],
                                    "categorical_handling": "pandas get_dummies; unknown category retained; internal LightGBM names sanitized",
                                    "class_method": "GradeCD/JyokenInfoSyubetuCD are retained as raw categories; official mapping unavailable",
                                    "opponent_strength_method": "target-date-before stats: smoothed win/place rates with (wins+1)/(races+5), aggregated over prior-race winner and field participants"}, importance)
        results["v2"] = len(rows)
        model_rows["v2"] = rows
    if args.model in ("stages", "all"):
        for stage in ("A", "B", "C", "D", "E", "F", "G", "H", "I"):
            stage_rows, stage_importance = evaluate_stage(data, pays, start, end, stage)
            write_report(stage_rows, ROOT / "reports" / f"backtest_stage_{stage}",
                         {**metadata, "model": f"stage {stage}"}, stage_importance)
            model_rows[stage] = stage_rows
    if args.model in ("A", "B", "C", "D", "E", "F", "G", "RA", "RB", "RC", "H", "I", "CA", "CB"):
        rows, importance = evaluate_stage(data, pays, start, end, args.model,
                          min_race_first_prize=args.min_race_first_prize)
        stage_out = args.out
        write_report(rows, stage_out, {**metadata, "model": f"stage {args.model}",
                                       "features": feature_lists[args.model],
                                       "categorical_handling": "pandas get_dummies; unknown category retained",
                                       "class_method": "JyokenName only; raw unknown codes retained"}, importance)
        results[args.model] = len(rows)
    if args.model in ("stages", "all"):
        write_model_comparison(model_rows, ROOT / "reports" / "model_comparison")
    print(json.dumps({"output": str(args.out), "predictions": results, "metadata": metadata}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
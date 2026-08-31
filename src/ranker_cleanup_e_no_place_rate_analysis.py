#!/usr/bin/env python3
"""CLEANUP_E minus `recent3_place_rate`: full walk-forward re-run + feature importance + last-30-days export.

`recent3_place_rate` was the single dominant Gain feature (~19%) in the CLEANUP_E model
(see reports/ranker_cleanup_e_feature_importance/). This reruns the exact same monthly
walk-forward with that one feature removed, to see what the model leans on next and how the
last-month field predictions shift.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker

try:
    from src import ranker_walk_forward_backtest as wf
    from src.backtest import CAREER_COUNT_FEATURES, DEDUP_MARGIN_FEATURES
    from src.ranker_cleanup_e_backtest import load_cleanup_e_frame
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf
    from backtest import CAREER_COUNT_FEATURES, DEDUP_MARGIN_FEATURES
    from ranker_cleanup_e_backtest import load_cleanup_e_frame

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "reports" / "ranker_cleanup_e_no_place_rate"
EXCLUDED_FEATURE = "recent3_place_rate"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fit_and_importance(train: pd.DataFrame, features: list[str]) -> list[dict]:
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)
    train_raw = ordered[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    center, scale = train_raw.mean(), train_raw.std().replace(0.0, 1.0)
    train_x = ((train_raw - center) / scale).to_numpy(dtype=np.float32)
    group_sizes = ordered.groupby("race_id", sort=False).size().tolist()
    relevance = (ordered.groupby("race_id")["actual_rank"].transform("max") - ordered["actual_rank"] + 1).to_numpy()
    model = LGBMRanker(objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3], n_estimators=180,
                       learning_rate=0.04, num_leaves=15, max_depth=5, min_child_samples=80,
                       reg_lambda=2.0, random_state=wf.SEED, verbosity=-1)
    model.fit(train_x, relevance, group=group_sizes)
    gain = model.booster_.feature_importance("gain")
    split = model.booster_.feature_importance("split")
    total_gain = gain.sum() or 1.0
    return sorted(
        [{"feature": name, "gain": float(g), "gain_share": float(g) / total_gain, "split_count": int(s)}
         for name, g, s in zip(features, gain, split)],
        key=lambda row: row["gain"], reverse=True)


def main() -> None:
    _, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    reduced_features = [feature for feature in dedup_features if feature not in CAREER_COUNT_FEATURES]
    frame, cleanup_e_features = load_cleanup_e_frame(reduced_features)
    features = [feature for feature in cleanup_e_features if feature != EXCLUDED_FEATURE]

    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    walk_rows, training_log = wf.monthly_walk_forward(frame, features, months, wf.CALIBRATION_MONTHS)
    overall = wf.metrics(walk_rows)

    last_month = frame["date"].max().replace(day=1)
    train = frame[frame["date"] < last_month]
    importance_rows = fit_and_importance(train, features)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_columns = ["date", "race_id", "horse_id", "horse_name", "actual_rank", "target", "odds", "win_odds",
                      "popularity", "ranker_score", "ranker_win_probability", "prediction_rank", "win_payout",
                      "model_train_end_date", "evaluation_mode"]
    write_csv(OUTPUT / "predictions_no_recent3_place_rate.csv",
              walk_rows[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
    write_csv(OUTPUT / "feature_importance.csv", importance_rows)
    write_csv(OUTPUT / "monthly_training_log.csv", training_log)

    cutoff = walk_rows["date"].max() - pd.Timedelta(days=30)
    recent = walk_rows[walk_rows["date"] > cutoff].sort_values(["date", "race_id", "prediction_rank"])
    recent[output_columns].assign(date=lambda values: values["date"].dt.strftime("%Y-%m-%d")).to_csv(
        OUTPUT / "last_30_days_all_horses.csv", index=False)

    lines = [f"# CLEANUP_E without `{EXCLUDED_FEATURE}`", "",
             f"- 除外特徴量: `{EXCLUDED_FEATURE}`（CLEANUP_EでGain比率トップ 18.95%）",
             f"- 特徴量数: {len(features)}（CLEANUP_Eの{len(cleanup_e_features)}から1本減）",
             f"- 全体成績: Brier {overall['brier']:.6f}, AUC {overall['auc']:.6f}, Top1 {overall['top1_hit_rate']:.2%}, "
             f"Top3 {overall['top3_hit_rate']:.2%}, Top1 Win ROI {overall['top1_win_roi']:.2f}%",
             "", "## Gain上位20特徴量（除外後）", "| 順位 | 特徴量 | Gain比率 | 分岐回数 |", "|---:|---|---:|---:|"]
    for rank, row in enumerate(importance_rows[:20], 1):
        lines.append(f"| {rank} | {row['feature']} | {row['gain_share']:.2%} | {row['split_count']} |")
    lines += ["", "## 直近30日間の全馬予測（除外後モデル）", f"- 期間: {cutoff.date()} 〜 {walk_rows['date'].max().date()}",
             f"- 件数: {len(recent)}（{recent['race_id'].nunique()}レース）",
             "- `last_30_days_all_horses.csv` に全出走馬の予測勝率を出力。"]
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "overall": overall,
                      "top10_features": [row["feature"] for row in importance_rows[:10]],
                      "recent_rows": len(recent), "recent_races": int(recent["race_id"].nunique())},
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Feature importance for the CLEANUP_E Ranker, using the exact model that produced the most
recent month's predictions (trained on all data before that month's start).

Also exports the full field (all horses, not just prediction_rank==1) for the trailing 30 days
of predictions in reports/ranker_cleanup_e_redesign/cleanup_e_predictions.csv, for manual review.
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
PREDICTIONS = ROOT / "reports" / "ranker_cleanup_e_redesign" / "cleanup_e_predictions.csv"
OUTPUT = ROOT / "reports" / "ranker_cleanup_e_feature_importance"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    _, baseline_features = wf.load_frame()
    dedup_features = [feature for feature in baseline_features if feature not in DEDUP_MARGIN_FEATURES]
    reduced_features = [feature for feature in dedup_features if feature not in CAREER_COUNT_FEATURES]
    frame, cleanup_e_features = load_cleanup_e_frame(reduced_features)

    last_month = frame["date"].max().replace(day=1)
    train = frame[frame["date"] < last_month].copy()
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)

    train_raw = ordered[cleanup_e_features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
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
    importance_rows = sorted(
        [{"feature": name, "gain": float(g), "gain_share": float(g) / total_gain, "split_count": int(s)}
         for name, g, s in zip(cleanup_e_features, gain, split)],
        key=lambda row: row["gain"], reverse=True)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "feature_importance.csv", importance_rows)

    predictions = pd.read_csv(PREDICTIONS)
    predictions["date"] = pd.to_datetime(predictions["date"])
    cutoff = predictions["date"].max() - pd.Timedelta(days=30)
    recent = predictions[predictions["date"] > cutoff].sort_values(["date", "race_id", "prediction_rank"])
    recent.to_csv(OUTPUT / "last_30_days_all_horses.csv", index=False)

    lines = ["# CLEANUP_E Feature Importance (model trained on data before " + last_month.strftime("%Y-%m") + ")", "",
             f"- 学習データ: {len(train)}件（{last_month.strftime('%Y-%m-%d')}より前の全レース）",
             f"- 特徴量数: {len(cleanup_e_features)}", "", "## Gain上位20特徴量",
             "| 順位 | 特徴量 | Gain比率 | 分岐回数 |", "|---:|---|---:|---:|"]
    for rank, row in enumerate(importance_rows[:20], 1):
        lines.append(f"| {rank} | {row['feature']} | {row['gain_share']:.2%} | {row['split_count']} |")
    lines += ["", f"## 直近30日間の全馬予測", f"- 期間: {cutoff.date()} 〜 {predictions['date'].max().date()}",
             f"- 件数: {len(recent)}（{recent['race_id'].nunique()}レース）",
             "- 全馬（1位評価だけでなく出走馬すべて）の予測勝率を `last_30_days_all_horses.csv` に出力。"]
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "train_rows": len(train), "last_month": last_month.strftime("%Y-%m"),
                      "top10_features": [row["feature"] for row in importance_rows[:10]],
                      "recent_rows": len(recent), "recent_races": int(recent["race_id"].nunique())},
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

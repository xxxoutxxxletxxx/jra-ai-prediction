"""結果出力(Phase 7): レース単位のJSON/CSV/Markdownとバックテストのサマリー。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from raceverse.config import PACE_BUCKETS
from raceverse.simulator import SimulationResult

PACE_LABEL = {"VERY_FAST": "超ハイ", "FAST": "ハイ", "MIDDLE": "ミドル", "SLOW": "スロー", "VERY_SLOW": "超スロー"}


def _clean(value):
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.ndarray):
        return [_clean(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def result_to_json(result: SimulationResult, horse_names: Optional[Dict[str, str]] = None,
                   calibrated: Optional[pd.Series] = None) -> dict:
    horses = []
    for i, row in result.horses.iterrows():
        entry = {
            "horse_id": row["horse_id"], "umaban": int(row["umaban"]),
            "ability_score": _clean(row["ability_score"]),
            "win_probability_raw": _clean(row["win_probability"]),
            "top2_probability": _clean(row["top2_probability"]), "top3_probability": _clean(row["top3_probability"]),
            "finish_position_distribution": row["finish_position_distribution"],
            "conditional_win_probability_by_display_pace": {n: _clean(row[f"win_prob_{n}"]) for n in PACE_BUCKETS},
            "pace_condition_sample_count": row["pace_condition_sample_count"],
            "mean_early_position": _clean(row["mean_early_position"]), "mean_lateral_slot": _clean(row["mean_lateral_slot"]),
            "lead_probability": _clean(row["lead_probability"]), "cold_start": bool(row["cold_start"]),
            "jockey_change_adjustment_summary": {"adjusted_fraction": _clean(row["jockey_change_adjusted_fraction"]),
                                                  "mean_shift_q": _clean(row["jockey_change_mean_shift"])},
        }
        if horse_names:
            entry["horse_name"] = horse_names.get(row["horse_id"])
        if calibrated is not None:
            entry["win_probability_calibrated"] = _clean(calibrated.iloc[i])
            entry["p_cal"] = _clean(calibrated.iloc[i])
        if "mean_horse_time_sec" in row:
            entry["mean_horse_time_sec"] = _clean(row["mean_horse_time_sec"])
            entry["horse_time_p10_p90_sec"] = [_clean(row["horse_time_p10_sec"]), _clean(row["horse_time_p90_sec"])]
        entry["win_odds_reference"] = _clean(row["win_odds_reference"])
        horses.append(entry)
    return {"race": _clean(result.race), "horses": horses}


def race_markdown(result: SimulationResult, horse_names: Optional[Dict[str, str]] = None,
                  ranker_probability: Optional[Dict[str, float]] = None,
                  calibrated: Optional[pd.Series] = None) -> str:
    r = result.race
    lines = [f"# RACEVERSE {r['race_id']}", ""]
    lines.append(f"- 試行回数 {r['simulations']:,} / seed {r['seed']} / 走破性能レベル {r['perf_level']} / モデル基準日 {r['model_as_of']}")
    if r.get("predicted_early_split_mean_sec") is not None:
        lo, hi = r["predicted_early_split_p10_p90_sec"]
        lines.append(f"- 前半{int(r['early_section_m'])}m予測 {r['predicted_early_split_mean_sec']:.1f}秒 "
                     f"(P10-P90 {lo:.1f}-{hi:.1f}) / 標準 {r['reference_early_split_sec']:.1f}秒 / 偏差平均 {r['pace_delta_mean_sec']:+.2f}秒 (負=速い)")
        probs = " ".join(f"{PACE_LABEL[k]}{v * 100:.0f}%" for k, v in r["pace_display_probabilities"].items())
        lines.append(f"- 表示ペース分布(連続値の事後分類): {probs}")
    if r.get("expected_winning_time_sec") is not None:
        lo, hi = r["winning_time_p10_p90_sec"]
        lines.append(f"- 予測決着時計 {r['expected_winning_time_sec']:.1f}秒 (P10-P90 {lo:.1f}-{hi:.1f}) / 馬場速度補正 {r['track_speed_adjustment_sec']:+.2f}秒")
        src = r["track_reference_sources"]
        lines.append(f"- 馬場参照: {src['counts']} (有効標本 {src['effective_sample_size']:.1f}, 優先窓 {src['fallback_level']})")
    else:
        lines.append("- 決着時計: unavailable")
    for w in r.get("warnings", []):
        lines.append(f"- 警告: {w}")
    lines += ["", "| 馬番 | 馬 | 能力指標 | 勝率(生) | 勝率(校正) | 複勝圏 | 逃げ確率 | 平均序盤位置 | 予測時計 | 既存AI勝率 |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    horses = result.horses.reset_index(drop=True)
    for i, row in horses.sort_values("win_probability", ascending=False).iterrows():
        name = (horse_names or {}).get(row["horse_id"], row["horse_id"])
        cal = f"{calibrated.iloc[i] * 100:.1f}%" if calibrated is not None else "-"
        rk = f"{ranker_probability[row['horse_id']] * 100:.1f}%" if ranker_probability and row["horse_id"] in ranker_probability else "-"
        t = f"{row['mean_horse_time_sec']:.1f}" if "mean_horse_time_sec" in row else "-"
        lines.append(f"| {int(row['umaban'])} | {name} | {row['ability_score']:.2f} | {row['win_probability'] * 100:.1f}% | {cal} | "
                     f"{row['top3_probability'] * 100:.1f}% | {row['lead_probability'] * 100:.1f}% | {row['mean_early_position']:.2f} | {t} | {rk} |")
    lines += ["", "注: 勝率(校正)は直前の実績に基づく温度校正後。能力指標は既存Rankerのraw score。10,000回の試行が確率の正確さを保証するわけではない。"]
    return "\n".join(lines) + "\n"


def write_race_outputs(result: SimulationResult, out_dir: Path, horse_names=None, ranker_probability=None,
                       calibrated: Optional[pd.Series] = None, file_suffix: str = "") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.race_id + file_suffix
    (out_dir / f"{stem}.json").write_text(
        json.dumps(result_to_json(result, horse_names, calibrated), ensure_ascii=False, indent=2), encoding="utf-8")
    horses = result.horses.drop(columns=["finish_position_distribution", "pace_condition_sample_count"]).copy()
    if calibrated is not None:
        horses["win_probability_calibrated"] = calibrated.to_numpy(dtype=float)
        horses["p_cal"] = calibrated.to_numpy(dtype=float)
    horses["going"] = result.race.get("going")
    horses["going_scenario"] = result.race.get("going_scenario", result.race.get("going"))
    horses["model_level"] = result.race.get("perf_level")
    horses["generated_at"] = result.race.get("generated_at")
    horses.to_csv(out_dir / f"{stem}.csv", index=False)
    (out_dir / f"{stem}.md").write_text(race_markdown(result, horse_names, ranker_probability, calibrated), encoding="utf-8")


def _md_table(frame: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    cols = list(frame.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in frame.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append(floatfmt.format(v) if isinstance(v, (float, np.floating)) and np.isfinite(v) else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_backtest_markdown(summary: Dict, out_dir: Path) -> None:
    cfg = summary["config"]
    lines = ["# RACEVERSE v0.6 Walk-Forward バックテスト", "",
             f"- 評価期間: {cfg['test_start']} 〜 {cfg['test_end']} (助走期間 {cfg['burn_in_start']} 〜、校正初期化のみ)",
             f"- 試行回数: {cfg['n_simulations']:,} / seed {cfg['seed']} / 既存Rankerと同一の{summary['common_races']}レースで比較",
             f"- 注意: {cfg['odds_note']}", "", "## 勝率(同一レース・同一馬)", ""]
    metrics = pd.DataFrame(summary["probability_metrics"])
    cols = ["model", "calibrated", "races", "winner_logloss", "logloss_binary", "brier_binary", "top1_hit_rate",
            "top3_recall", "rank_spearman"]
    lines.append(_md_table(metrics[cols]))
    lines += ["", "## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)", ""]
    lines.append(_md_table(pd.DataFrame(summary["roi_reference"])))
    if summary.get("relative_time"):
        lines += ["", "## 相対走破時計(走破時計 - 出走馬平均, 秒)の予測誤差", ""]
        lines.append(_md_table(pd.DataFrame(summary["relative_time"])))
    for pair, dims in summary.get("course_bias_overview", {}).items():
        lines += ["", f"## コースバイアス追加の改善度 ({pair}, 詳細は course_bias_group_gains.csv)", ""]
        lines.append(_md_table(pd.DataFrame(dims).T.reset_index().rename(columns={"index": "dimension"})))
    pace = summary.get("pace", {})
    if pace:
        lines += ["", "## ペース(前半ラップ, 秒)", ""]
        table = pd.DataFrame(pace["early_split"]).T.reset_index().rename(columns={"index": "predictor"})
        lines.append(_md_table(table))
        lines.append(f"\nP10-P90 被覆率: {pace['p10_p90_coverage']:.3f} (理想 0.80)")
        lines += ["", "表示5段階の予測発生率と実測発生率:", "", _md_table(pd.DataFrame(pace["display_bucket_calibration"]))]
    timing = summary.get("timing", {})
    if timing:
        lines += ["", "## 決着時計(勝ち時計, 秒)", "", _md_table(pd.DataFrame(timing["winning_time"]).T.reset_index().rename(columns={"index": "model"}))]
        lines.append(f"\nP10-P90 被覆率: {timing['p10_p90_coverage']:.3f} (理想 0.80)")
    if "formation" in summary:
        f = summary["formation"]
        lines += ["", "## 初期隊列", "",
                  f"- 相対序盤位置のMAE {f['early_position_mae_relative']:.4f} (定数予測 {f['naive_constant_mae']:.4f})",
                  f"- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 {f['leader_in_top3_lead_prob_rate']:.3f}"]
    lines += ["", f"実行時間 {summary['runtime_sec']:.0f}秒"]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

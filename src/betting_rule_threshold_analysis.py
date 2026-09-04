#!/usr/bin/env python3
"""本命単勝の買い目ルール（src/betting_rules.py）の根拠分析。

2つのバックテスト予測エクスポートを読み、
  1. AI本命のオッズ帯別 成績
  2. オッズ3倍未満の本命に対する予測勝率ラインの感度
  3. 最終ルール適用時の合成成績
を reports/betting_rule_analysis/ に出力する。読み取り専用でモデルは変更しない。

使い方:
  python3 -m src.betting_rule_threshold_analysis
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "reports" / "betting_rule_analysis"
V0_PREDICTIONS = ROOT / "reports" / "backtest_12m_v0" / "predictions.csv"
RANKER_PREDICTIONS = ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv"

ODDS_BINS = [0, 1.5, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0, float("inf")]
ODDS_LABELS = ["~1.4", "1.5-1.9", "2.0-2.9", "3.0-4.9", "5.0-7.9", "8.0-9.9",
               "10.0-14.9", "15.0-19.9", "20.0-29.9", "30.0-49.9", "50+"]
PROB_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

# 最終採用ライン（src/betting_rules.py と同期させること）
FINAL_LOW_ODDS_LIMIT = 3.0
FINAL_VOLUME_MIN = 5.0
FINAL_VOLUME_MAX = 20.0
FINAL_LOW_ODDS_MIN_PROB = 0.40


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_top1(path: Path, prob_col: str, hit_col: str, odds_col: str, odds_scale: float) -> pd.DataFrame:
    frame = pd.read_csv(path)
    top1 = frame[frame["prediction_rank"] == 1].copy()
    top1["win_odds"] = top1[odds_col] / odds_scale
    top1["prob"] = top1[prob_col]
    top1["hit"] = top1[hit_col]
    return top1


def summarize(subset: pd.DataFrame) -> dict:
    n = len(subset)
    if n == 0:
        return {"n": 0, "win_rate": None, "roi": None, "profit": 0.0}
    payout = float(subset["win_payout"].sum())
    return {"n": n, "win_rate": float(subset["hit"].mean()),
            "avg_prob": float(subset["prob"].mean()), "payout": payout,
            "roi": payout / (n * 100) * 100, "profit": payout - n * 100}


def odds_band_rows(top1: pd.DataFrame, model: str) -> list[dict]:
    labeled = top1.copy()
    labeled["band"] = pd.cut(labeled["win_odds"], bins=ODDS_BINS, labels=ODDS_LABELS, right=False)
    rows = []
    for band, group in labeled.groupby("band", observed=True):
        rows.append({"model": model, "odds_band": str(band), **summarize(group)})
    return rows


def threshold_rows(top1: pd.DataFrame, model: str) -> list[dict]:
    low = top1[top1["win_odds"] < FINAL_LOW_ODDS_LIMIT]
    rows = [{"model": model, "prob_threshold": "all", **summarize(low)}]
    for threshold in PROB_THRESHOLDS:
        rows.append({"model": model, "prob_threshold": threshold, **summarize(low[low["prob"] >= threshold])})
    return rows


def rule_simulation(top1: pd.DataFrame, model: str) -> dict:
    low = top1[(top1["win_odds"] < FINAL_LOW_ODDS_LIMIT) & (top1["prob"] >= FINAL_LOW_ODDS_MIN_PROB)]
    volume = top1[(top1["win_odds"] >= FINAL_VOLUME_MIN) & (top1["win_odds"] < FINAL_VOLUME_MAX)]
    buy = pd.concat([low, volume])
    result = {"model": model, "all_top1": summarize(top1), "rule_total": summarize(buy),
              "rule_low_odds": summarize(low), "rule_volume_zone": summarize(volume),
              "skipped_low_odds_low_prob": summarize(top1[(top1["win_odds"] < FINAL_LOW_ODDS_LIMIT) & (top1["prob"] < FINAL_LOW_ODDS_MIN_PROB)]),
              "skipped_mid_low_odds": summarize(top1[(top1["win_odds"] >= FINAL_LOW_ODDS_LIMIT) & (top1["win_odds"] < FINAL_VOLUME_MIN)]),
              "skipped_high_odds": summarize(top1[top1["win_odds"] >= FINAL_VOLUME_MAX])}
    monthly = []
    labeled = buy.copy()
    labeled["month"] = labeled["date"].astype(str).str[:7]
    for month, group in labeled.groupby("month"):
        summary = summarize(group)
        monthly.append({"month": month, "bets": summary["n"], "roi": summary["roi"]})
    result["monthly"] = monthly
    return result


def main() -> None:
    models = {
        "v0": load_top1(V0_PREDICTIONS, "predicted_probability", "is_win", "odds", 10.0),
        "ranker": load_top1(RANKER_PREDICTIONS, "ranker_win_probability", "target", "win_odds", 1.0),
    }
    bands, thresholds, simulations = [], [], {}
    for name, top1 in models.items():
        bands.extend(odds_band_rows(top1, name))
        thresholds.extend(threshold_rows(top1, name))
        simulations[name] = rule_simulation(top1, name)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "odds_band_performance.csv", bands)
    write_csv(OUTPUT / "low_odds_threshold_test.csv", thresholds)
    (OUTPUT / "rule_simulation.json").write_text(json.dumps(simulations, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 本命単勝 買い目ルール分析", "",
             "## データ",
             "- v0: 現行統計モデル 12ヶ月 walk-forward（2025-09〜2026-08、全レース）`reports/backtest_12m_v0/predictions.csv`",
             "- ranker: LightGBM Ranker 12ヶ月 walk-forward（同期間、1着賞金800万円超レース）`reports/ranker_walk_forward_12m/walk_forward_predictions.csv`",
             "- いずれもAI本命（prediction_rank=1）の単勝100円買いで評価。",
             "", "## 採用ルール（src/betting_rules.py）",
             f"- オッズ {FINAL_LOW_ODDS_LIMIT} 倍未満: 予測勝率 {FINAL_LOW_ODDS_MIN_PROB:.0%} 以上のみ購入",
             f"- オッズ {FINAL_VOLUME_MIN}〜{FINAL_VOLUME_MAX} 倍: 購入（ボリューム帯）",
             "- 上記以外（3〜5倍・20倍以上・オッズ未取得）: 見送り",
             "", "## ルール適用シミュレーション"]
    for name, sim in simulations.items():
        all_top1, rule = sim["all_top1"], sim["rule_total"]
        lines.append(f"- {name}: 全買い {all_top1['n']}点 ROI {all_top1['roi']:.1f}% → "
                     f"ルール適用 {rule['n']}点 ROI {rule['roi']:.1f}%（損益 {rule['profit']:+,.0f}円）")
        lines.append(f"    内訳 3倍未満&勝率{FINAL_LOW_ODDS_MIN_PROB:.0%}以上: {sim['rule_low_odds']['n']}点 ROI {sim['rule_low_odds']['roi']:.1f}% / "
                     f"5-20倍: {sim['rule_volume_zone']['n']}点 ROI {sim['rule_volume_zone']['roi']:.1f}%")
    lines += ["", "## 注意", "- 現状のモデルでは採用ルール適用後も単勝ROIは100%未満。",
              "- このルールは損失削減のフィルタであり、黒字化の根拠ではない。",
              "- 詳細は odds_band_performance.csv / low_odds_threshold_test.csv / rule_simulation.json を参照。"]
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "rule": {
        "low_odds_limit": FINAL_LOW_ODDS_LIMIT, "volume_min": FINAL_VOLUME_MIN,
        "volume_max": FINAL_VOLUME_MAX, "low_odds_min_probability": FINAL_LOW_ODDS_MIN_PROB}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

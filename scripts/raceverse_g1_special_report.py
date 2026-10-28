"""Generate a G1-only report from existing walk-forward predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from raceverse_roi_strategy_validation import (
    DEFAULT_DB,
    DEFAULT_INPUT,
    LEVELS,
    load_analysis_data,
    make_top_candidates,
    summarize_bets,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports/raceverse/g1_special_report"
MODEL_LABELS = {
    "base": "base",
    "formation": "formation",
    "pace": "pace",
    "consensus": "3方式合意",
}


def _wilson_interval(hits: int, count: int) -> tuple[float, float]:
    if not count:
        return np.nan, np.nan
    z = 1.959963984540054
    rate = hits / count
    denominator = 1 + z**2 / count
    center = (rate + z**2 / (2 * count)) / denominator
    margin = z * np.sqrt(rate * (1 - rate) / count + z**2 / (4 * count**2)) / denominator
    return (center - margin) * 100, (center + margin) * 100


def _bet_summary_rows(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model in (*LEVELS, "consensus"):
        sample = candidates.loc[candidates["model"].eq(model)]
        for year, group in [("全期間", sample), *sample.groupby("year", sort=True)]:
            metrics = summarize_bets(group)
            ci_low, ci_high = _wilson_interval(metrics["hits"], metrics["purchase_races"])
            rows.append(
                {
                    "model": model,
                    "year": year,
                    "races": metrics["purchase_races"],
                    "hits": metrics["hits"],
                    "hit_rate_pct": metrics["hit_rate_pct"],
                    "hit_rate_95ci_low_pct": ci_low,
                    "hit_rate_95ci_high_pct": ci_high,
                    "mean_predicted_win_probability": metrics["mean_predicted_win_probability"],
                    "investment_yen": metrics["investment_yen"],
                    "payout_yen": metrics["payout_yen"],
                    "profit_yen": metrics["profit_yen"],
                    "roi_pct": metrics["roi_pct"],
                    "max_drawdown_yen": metrics["max_drawdown_yen"],
                    "max_losing_streak": metrics["max_losing_streak"],
                    "mean_final_odds_post_race": metrics["avg_final_odds"],
                }
            )
    return pd.DataFrame(rows)


def _calibration_rows(runners: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model in LEVELS:
        sample = runners.loc[runners["level"].eq(model)]
        for year, group in [("全期間", sample), *sample.groupby("year", sort=True)]:
            winners = group.loc[group["target"].eq(1)]
            rows.append(
                {
                    "model": model,
                    "year": year,
                    "races": group["race_id"].nunique(),
                    "runners": len(group),
                    "brier_score": ((group["p_cal"] - group["target"]) ** 2).mean(),
                    "winner_logloss": (
                        -np.log(winners["p_cal"].clip(lower=1e-15)).mean()
                        if len(winners)
                        else np.nan
                    ),
                    "mean_predicted_runner_probability": group["p_cal"].mean(),
                    "actual_runner_win_rate": group["target"].mean(),
                }
            )
    return pd.DataFrame(rows)


def _agreement_rows(wide: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    consensus = candidates.loc[candidates["model"].eq("consensus")]
    for votes, label in ((3, "3方式一致"), (2, "2方式一致"), (1, "全方式不一致")):
        group = wide.loc[wide["top1_agreement_votes"].eq(votes)]
        selected = consensus.loc[consensus["race_id"].isin(group["race_id"])]
        metrics = summarize_bets(selected)
        rows.append(
            {
                "agreement": label,
                "races": len(group),
                "share_pct": len(group) / len(wide) * 100 if len(wide) else np.nan,
                "consensus_hits": metrics["hits"],
                "consensus_hit_rate_pct": metrics["hit_rate_pct"],
                "consensus_roi_pct": metrics["roi_pct"],
            }
        )
    return pd.DataFrame(rows)


def _race_detail(wide: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    detail_columns = [
        "race_id", "date", "racecourse", "surface_name", "distance_band",
        "going_name", "top1_agreement_votes", "top1_probability_sd",
    ]
    result = wide[detail_columns].copy()
    for model in LEVELS:
        sample = candidates.loc[candidates["model"].eq(model), [
            "race_id", "selected_horse_id", "selected_umaban", "top1_probability",
            "top2_probability", "top1_top2_gap", "hit", "payout_yen", "final_odds",
        ]].rename(
            columns={
                "selected_horse_id": f"{model}_horse_id",
                "selected_umaban": f"{model}_horse_number",
                "top1_probability": f"{model}_top1_probability",
                "top2_probability": f"{model}_top2_probability",
                "top1_top2_gap": f"{model}_top1_top2_gap",
                "hit": f"{model}_top1_hit",
                "payout_yen": f"{model}_payout_yen",
                "final_odds": f"{model}_final_odds_post_race",
            }
        )
        result = result.merge(sample, on="race_id", how="left", validate="one_to_one")
    result["odds_note"] = "確定オッズ（事後参照）"
    return result.sort_values(["date", "race_id"], kind="stable").reset_index(drop=True)


def _format_pct(value: object, digits: int = 1) -> str:
    return "—" if pd.isna(value) else f"{float(value):.{digits}f}%"


def _summary_markdown(
    runners: pd.DataFrame,
    candidates: pd.DataFrame,
    summaries: pd.DataFrame,
    calibration: pd.DataFrame,
    agreement: pd.DataFrame,
) -> str:
    race_count = runners["race_id"].nunique()
    start = runners["date"].min().strftime("%Y-%m-%d")
    end = runners["date"].max().strftime("%Y-%m-%d")
    model_rows = summaries.loc[summaries["year"].eq("全期間")]
    calibration_rows = calibration.loc[calibration["year"].eq("全期間")]

    lines = [
        "# RACEVERSE G1特化レポート",
        "",
        f"- 対象期間: {start}〜{end}",
        f"- G1レース数: {race_count}（各方式で1レース1頭を選択）",
        f"- 予測方式: {', '.join(LEVELS)}。別枠で3方式合意候補も集計。",
        "- 購入仮定: 各レースの各候補を単勝100円。",
        "- これは既存の校正済みWalk-Forward予測をG1（GradeCD=A）に絞った事後分析です。",
        "",
        "## 先に読む結論",
        "",
        "この標本からG1専用の購入ルールや収益性を確立したとは言えません。ROIは過去の結果を記述する指標であり、次のG1での期待収益を保証しません。単勝回収率だけでなく、的中率・予測勝率・年別の振れを併せて確認してください。",
        "",
        "## 方式別成績（全期間）",
        "",
        "| 方式 | レース | 的中 | 的中率（95% Wilson区間） | 平均予測勝率 | 投資額 | 払戻 | 損益 | ROI | 最大DD | 最長連敗 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in model_rows.itertuples(index=False):
        ci = f"{_format_pct(row.hit_rate_95ci_low_pct)}–{_format_pct(row.hit_rate_95ci_high_pct)}"
        lines.append(
            f"| {MODEL_LABELS[row.model]} | {row.races} | {row.hits} | "
            f"{_format_pct(row.hit_rate_pct)}（{ci}） | "
            f"{_format_pct(row.mean_predicted_win_probability * 100)} | "
            f"{row.investment_yen:,.0f}円 | {row.payout_yen:,.0f}円 | "
            f"{row.profit_yen:+,.0f}円 | {_format_pct(row.roi_pct)} | "
            f"{row.max_drawdown_yen:,.0f}円 | {row.max_losing_streak} |"
        )

    lines.extend(
        [
            "",
            "## 年別成績",
            "",
            "2023年と2026年は対象期間の一部のみです。各年の数値はサンプルが小さく、年ごとの優劣の断定には使えません。",
            "",
            "| 年 | 方式 | レース | 的中率 | ROI | 損益 |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    yearly = summaries.loc[~summaries["year"].eq("全期間")]
    for row in yearly.itertuples(index=False):
        lines.append(
            f"| {row.year} | {MODEL_LABELS[row.model]} | {row.races} | "
            f"{_format_pct(row.hit_rate_pct)} | {_format_pct(row.roi_pct)} | "
            f"{row.profit_yen:+,.0f}円 |"
        )

    lines.extend(
        [
            "",
            "## G1の確率予測の参考値",
            "",
            "全出走馬の校正済み勝率について集計。Brier scoreとWinner Loglossは小さいほど良い指標ですが、少数レースでは大きく変動します。",
            "",
            "| 方式 | レース | 出走馬 | Brier | Winner Logloss |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in calibration_rows.itertuples(index=False):
        lines.append(
            f"| {row.model} | {row.races} | {row.runners} | "
            f"{row.brier_score:.4f} | {row.winner_logloss:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 方式間の見解一致",
            "",
            "| Top1の一致 | レース | 割合 | 合意候補的中 | 合意候補的中率 | 合意候補ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in agreement.itertuples(index=False):
        lines.append(
            f"| {row.agreement} | {row.races} | {_format_pct(row.share_pct)} | "
            f"{row.consensus_hits} | {_format_pct(row.consensus_hit_rate_pct)} | "
            f"{_format_pct(row.consensus_roi_pct)} |"
        )

    lines.extend(
        [
            "",
            "## 使い方と制約",
            "",
            "- 詳細なレース別Top1、勝率、Top1-Top2差、的中、払戻は `g1_race_results.csv` を参照。",
            "- 年別・全期間のモデル成績は `g1_model_summary.csv`、確率指標は `g1_calibration.csv`、一致状況は `g1_model_agreement.csv`。",
            "- 払戻と確定オッズはレース後の参照値です。発走前に同じオッズで購入できたとは限らず、オッズ判断の運用成績ではありません。",
            "- 既存データは過去の分析で参照済みで、独立した未使用テストではありません。多数の条件を試して最良条件を選ぶことも避けてください。",
            "- 騎手・馬名等の説明可能な要因や展開シナリオを追加した「予想前ブリーフィング」にするには、次回G1の出走表・発走前オッズを時刻付きで保存し、予測時点のデータだけで生成する必要があります。",
            "- 実運用に使う前に、予測確率とオッズの時刻付き保存を続け、事前に固定した評価方法で将来期間を検証してください。",
            "",
            "## 再生成",
            "",
            "```bash",
            ".venv/bin/python scripts/raceverse_g1_special_report.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def generate_report(input_dir: Path, db_path: Path, out_dir: Path) -> None:
    runners, _, _ = load_analysis_data(input_dir, db_path)
    g1_runners = runners.loc[runners["grade_code_raw"].eq("A")].copy()
    if g1_runners.empty:
        raise ValueError("No G1 (GradeCD=A) races found in the calibrated prediction window")

    candidates, wide = make_top_candidates(g1_runners)
    g1_candidates = candidates.loc[candidates["grade_code_raw"].eq("A")].copy()
    g1_wide = wide.loc[wide["grade_code_raw"].eq("A")].copy()
    summaries = _bet_summary_rows(g1_candidates)
    calibration = _calibration_rows(g1_runners)
    agreement = _agreement_rows(g1_wide, g1_candidates)
    detail = _race_detail(g1_wide, g1_candidates)

    out_dir.mkdir(parents=True, exist_ok=True)
    summaries.to_csv(out_dir / "g1_model_summary.csv", index=False)
    calibration.to_csv(out_dir / "g1_calibration.csv", index=False)
    agreement.to_csv(out_dir / "g1_model_agreement.csv", index=False)
    detail.to_csv(out_dir / "g1_race_results.csv", index=False)
    (out_dir / "summary.md").write_text(
        _summary_markdown(g1_runners, g1_candidates, summaries, calibration, agreement),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Walk-forward prediction directory")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Race database containing grade and payouts")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    args = parser.parse_args()
    generate_report(args.input, args.db, args.out)


if __name__ == "__main__":
    main()

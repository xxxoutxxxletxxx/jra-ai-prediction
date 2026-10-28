"""RACEVERSE Walk-Forward予測を市場暗黙勝率と比較する。

入力:
  reports/raceverse/backtest_202509_202609/predictions.csv
  reports/raceverse/backtest_202509_202609/race_level.csv

出力:
  market_comparison.csv
  odds_band_analysis.csv
  category_performance.csv
  RACEVERSE_MARKET_ANALYSIS.md
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "raceverse" / "backtest_202509_202609"
DEFAULT_OUTPUT = ROOT / "reports" / "raceverse" / "market_analysis_202509_202608"
DEFAULT_REPORT = ROOT / "RACEVERSE_MARKET_ANALYSIS.md"

LOGGER = logging.getLogger(__name__)
LEVELS = ("base", "formation", "pace")
MODEL_NAMES = ("market",) + LEVELS
ODDS_BINS = [0.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0, 50.0, 100.0, np.inf]
ODDS_LABELS = ["O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O9"]
ODDS_DESCRIPTIONS = {
    "O1": "2.0倍未満",
    "O2": "2.0倍以上3.0倍未満",
    "O3": "3.0倍以上5.0倍未満",
    "O4": "5.0倍以上10.0倍未満",
    "O5": "10.0倍以上20.0倍未満",
    "O6": "20.0倍以上30.0倍未満",
    "O7": "30.0倍以上50.0倍未満",
    "O8": "50.0倍以上100.0倍未満",
    "O9": "100.0倍以上",
}


def distance_band(distance: pd.Series) -> pd.Series:
    return pd.cut(
        distance,
        bins=[0, 1400, 1800, 2200, np.inf],
        labels=["D1", "D2", "D3", "D4"],
        right=True,
    )


def winner_logloss(frame: pd.DataFrame, probability: str) -> float:
    winners = frame.loc[frame["target"] == 1, probability].to_numpy(dtype=float)
    if len(winners) != frame["race_id"].nunique():
        raise ValueError("Each race must have exactly one winner")
    return float(-np.log(np.clip(winners, 1e-15, 1.0)).mean())


def top1_rows(frame: pd.DataFrame, probability: str) -> pd.DataFrame:
    ordered = frame.sort_values(
        ["race_id", probability, "umaban"],
        ascending=[True, False, True],
        kind="stable",
    )
    return ordered.drop_duplicates("race_id", keep="first").copy()


def roi_pct(frame: pd.DataFrame) -> float:
    return float(frame["win_payout"].sum() / (len(frame) * 100.0) * 100.0) if len(frame) else np.nan


def _require_columns(frame: pd.DataFrame, required: Iterable[str], source: Path) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def load_analysis_data(input_dir: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    predictions_path = input_dir / "predictions.csv"
    races_path = input_dir / "race_level.csv"
    predictions = pd.read_csv(
        predictions_path,
        dtype={"race_id": str, "horse_id": str, "level": str},
    )
    races = pd.read_csv(races_path, dtype={"race_id": str, "surface": str})
    _require_columns(
        predictions,
        [
            "race_id",
            "horse_id",
            "umaban",
            "level",
            "target",
            "finish",
            "p_cal",
            "win_odds_reference",
            "win_payout",
        ],
        predictions_path,
    )
    _require_columns(races, ["race_id", "surface", "distance_m"], races_path)

    retired = predictions["level"] == "full"
    if retired.any():
        LOGGER.warning("Excluding %d legacy full prediction rows from analysis", int(retired.sum()))
        predictions = predictions.loc[~retired].copy()

    predictions["p_cal"] = pd.to_numeric(predictions["p_cal"], errors="coerce")
    predictions["odds"] = pd.to_numeric(predictions["win_odds_reference"], errors="coerce")
    predictions["win_payout"] = pd.to_numeric(predictions["win_payout"], errors="coerce")
    predictions["target"] = pd.to_numeric(predictions["target"], errors="coerce")
    predictions["umaban"] = pd.to_numeric(predictions["umaban"], errors="coerce")

    unexpected_levels = sorted(set(predictions["level"].dropna()) - set(LEVELS))
    if unexpected_levels:
        raise ValueError(f"Unexpected RACEVERSE levels: {unexpected_levels}")
    missing_levels = sorted(set(LEVELS) - set(predictions["level"].dropna()))
    if missing_levels:
        raise ValueError(f"Missing RACEVERSE levels: {missing_levels}")

    counts: dict[str, int] = {}
    keys = ["race_id", "horse_id"]
    reference: pd.DataFrame | None = None
    for level in LEVELS:
        level_frame = predictions[predictions["level"] == level].copy()
        if level_frame.duplicated(keys).any():
            raise ValueError(f"{level}: duplicate race_id/horse_id rows")
        counts[f"{level}_races"] = int(level_frame["race_id"].nunique())
        counts[f"{level}_horses"] = int(len(level_frame))
        probability_missing = int(level_frame["p_cal"].isna().sum())
        if probability_missing:
            raise ValueError(f"{level}: {probability_missing} missing p_cal values")
        probability_sum_error = level_frame.groupby("race_id")["p_cal"].sum().sub(1.0).abs().max()
        if probability_sum_error > 1e-8:
            raise ValueError(f"{level}: max race probability sum error is {probability_sum_error}")

        comparable = level_frame[keys + ["umaban", "target", "odds", "win_payout"]].sort_values(keys)
        if reference is None:
            reference = comparable
        elif not reference.reset_index(drop=True).equals(comparable.reset_index(drop=True)):
            raise ValueError(f"{level}: runners, odds, targets, or payouts differ from base")

    assert reference is not None
    base = predictions[predictions["level"] == "base"].copy()
    invalid_odds = base["odds"].isna() | (base["odds"] <= 0)
    if invalid_odds.any():
        examples = base.loc[invalid_odds, ["race_id", "horse_id", "odds"]].head().to_dict("records")
        raise ValueError(f"Invalid final odds for {int(invalid_odds.sum())} runners: {examples}")
    invalid_payout = base["win_payout"].isna() | (base["win_payout"] < 0)
    if invalid_payout.any():
        raise ValueError(f"Invalid win payout for {int(invalid_payout.sum())} runners")

    winner_counts = base.groupby("race_id")["target"].sum()
    if not winner_counts.eq(1).all():
        raise ValueError(f"{int((winner_counts != 1).sum())} races do not have exactly one winner")

    race_attributes = races[["race_id", "surface", "distance_m"]].drop_duplicates("race_id")
    if race_attributes.duplicated("race_id").any():
        raise ValueError("race_level.csv has conflicting duplicate race rows")
    base = base.merge(race_attributes, on="race_id", how="left", validate="many_to_one")
    missing_attributes = base[["surface", "distance_m"]].isna().any(axis=1)
    if missing_attributes.any():
        raise ValueError(f"Missing race attributes for {base.loc[missing_attributes, 'race_id'].nunique()} races")
    if not base["surface"].isin(["turf", "dirt"]).all():
        values = sorted(base.loc[~base["surface"].isin(["turf", "dirt"]), "surface"].unique())
        raise ValueError(f"Unsupported surfaces in analysis races: {values}")

    base["p_raw_market"] = 1.0 / base["odds"]
    overround = base.groupby("race_id")["p_raw_market"].transform("sum")
    base["p_market"] = base["p_raw_market"] / overround
    base["distance_band"] = distance_band(base["distance_m"])
    if base["distance_band"].isna().any():
        raise ValueError("At least one race could not be assigned to a distance band")
    base["category"] = base["surface"].map({"turf": "芝", "dirt": "ダート"}) + base["distance_band"].astype(str)
    base["odds_band"] = pd.cut(
        base["odds"],
        bins=ODDS_BINS,
        labels=ODDS_LABELS,
        right=False,
        include_lowest=True,
    )
    if base["odds_band"].isna().any():
        raise ValueError("At least one runner could not be assigned to an odds band")

    probability_frames = [
        predictions.loc[predictions["level"] == level, keys + ["p_cal"]]
        .rename(columns={"p_cal": f"p_{level}"})
        for level in LEVELS
    ]
    analysis = base.drop(columns=["level", "p_cal"])
    for probabilities in probability_frames:
        analysis = analysis.merge(probabilities, on=keys, how="left", validate="one_to_one")

    counts["analysis_races"] = int(analysis["race_id"].nunique())
    counts["analysis_horses"] = int(len(analysis))
    counts["missing_odds"] = int(analysis["odds"].isna().sum())
    counts["missing_race_attributes"] = int(analysis[["surface", "distance_m"]].isna().any(axis=1).sum())
    return analysis, counts


def market_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    market_loss = winner_logloss(frame, "p_market")
    market_top1 = top1_rows(frame, "p_market")
    rows = []
    for model in MODEL_NAMES:
        probability = "p_market" if model == "market" else f"p_{model}"
        loss = winner_logloss(frame, probability)
        chosen = top1_rows(frame, probability)
        rows.append(
            {
                "model": model,
                "races": int(frame["race_id"].nunique()),
                "horses": int(len(frame)),
                "winner_logloss": loss,
                "logloss_diff_vs_market": loss - market_loss,
                "logloss_improvement_pct_vs_market": (market_loss - loss) / market_loss * 100.0,
                "top1_hits": int(chosen["target"].sum()),
                "top1_hit_rate": float(chosen["target"].mean()),
                "top1_investment": float(len(chosen) * 100),
                "top1_returned": float(chosen["win_payout"].sum()),
                "top1_roi_pct": roi_pct(chosen),
                "top1_avg_odds": float(chosen["odds"].mean()),
                "top1_agreement_with_market": float(
                    chosen.set_index("race_id")["horse_id"].eq(
                        market_top1.set_index("race_id")["horse_id"]
                    ).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def odds_band_analysis(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model in MODEL_NAMES:
        probability = "p_market" if model == "market" else f"p_{model}"
        for scope, selected in (("all_runners", frame), ("top1", top1_rows(frame, probability))):
            for band in ODDS_LABELS:
                group = selected[selected["odds_band"] == band]
                rows.append(
                    {
                        "selection_scope": scope,
                        "model": model,
                        "odds_band": band,
                        "odds_definition": ODDS_DESCRIPTIONS[band],
                        "races": int(group["race_id"].nunique()),
                        "horses_or_bets": int(len(group)),
                        "wins": int(group["target"].sum()),
                        "predicted_win_rate": float(group[probability].mean()) if len(group) else np.nan,
                        "actual_win_rate": float(group["target"].mean()) if len(group) else np.nan,
                        "market_win_rate": float(group["p_market"].mean()) if len(group) else np.nan,
                        "calibration_gap": (
                            float(group[probability].mean() - group["target"].mean()) if len(group) else np.nan
                        ),
                        "avg_odds": float(group["odds"].mean()) if len(group) else np.nan,
                        "investment": float(len(group) * 100),
                        "returned": float(group["win_payout"].sum()),
                        "roi_pct": roi_pct(group),
                        "profit": float(group["win_payout"].sum() - len(group) * 100),
                    }
                )
    return pd.DataFrame(rows)


def category_performance(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category in ["芝D1", "芝D2", "芝D3", "芝D4", "ダートD1", "ダートD2", "ダートD3", "ダートD4"]:
        group = frame[frame["category"] == category]
        market_loss = winner_logloss(group, "p_market")
        market_top1 = top1_rows(group, "p_market")
        for model in MODEL_NAMES:
            probability = "p_market" if model == "market" else f"p_{model}"
            loss = winner_logloss(group, probability)
            chosen = top1_rows(group, probability)
            rows.append(
                {
                    "category": category,
                    "surface": str(group["surface"].iloc[0]),
                    "distance_band": str(group["distance_band"].iloc[0]),
                    "model": model,
                    "races": int(group["race_id"].nunique()),
                    "horses": int(len(group)),
                    "avg_field_size": float(group.groupby("race_id").size().mean()),
                    "winner_logloss": loss,
                    "market_winner_logloss": market_loss,
                    "logloss_diff_vs_market": loss - market_loss,
                    "logloss_improvement_pct_vs_market": (market_loss - loss) / market_loss * 100.0,
                    "top1_hits": int(chosen["target"].sum()),
                    "top1_hit_rate": float(chosen["target"].mean()),
                    "top1_investment": float(len(chosen) * 100),
                    "top1_returned": float(chosen["win_payout"].sum()),
                    "top1_roi_pct": roi_pct(chosen),
                    "top1_avg_odds": float(chosen["odds"].mean()),
                    "top1_agreement_with_market": float(
                        chosen.set_index("race_id")["horse_id"].eq(
                            market_top1.set_index("race_id")["horse_id"]
                        ).mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _format_percent(value: float) -> str:
    return "" if pd.isna(value) else f"{value * 100:.2f}%"


def _markdown_table(frame: pd.DataFrame) -> str:
    def cell(value: object) -> str:
        if pd.isna(value):
            return ""
        return str(value).replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(cell(column) for column in frame.columns) + " |"
    separator = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = [
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def _odds_markdown(odds: pd.DataFrame, scope: str) -> str:
    selected = odds[odds["selection_scope"] == scope].copy()
    parts = []
    for model in MODEL_NAMES:
        model_rows = selected[selected["model"] == model][
            ["odds_band", "odds_definition", "horses_or_bets", "predicted_win_rate", "actual_win_rate", "roi_pct"]
        ].copy()
        model_rows["predicted_win_rate"] = model_rows["predicted_win_rate"].map(_format_percent)
        model_rows["actual_win_rate"] = model_rows["actual_win_rate"].map(_format_percent)
        model_rows["roi_pct"] = model_rows["roi_pct"].map(lambda value: "" if pd.isna(value) else f"{value:.2f}%")
        model_rows = model_rows.rename(
            columns={
                "odds_band": "帯",
                "odds_definition": "定義",
                "horses_or_bets": "頭数/購入数",
                "predicted_win_rate": "平均予測勝率",
                "actual_win_rate": "実測勝率",
                "roi_pct": "単勝ROI",
            }
        )
        parts.extend([f"#### {model}", "", _markdown_table(model_rows), ""])
    return "\n".join(parts)


def render_report(
    comparison: pd.DataFrame,
    odds: pd.DataFrame,
    categories: pd.DataFrame,
    counts: dict[str, int],
    output_dir: Path,
) -> str:
    comparison_md = comparison[
        [
            "model",
            "winner_logloss",
            "logloss_diff_vs_market",
            "logloss_improvement_pct_vs_market",
            "top1_hits",
            "top1_hit_rate",
            "top1_roi_pct",
            "top1_agreement_with_market",
        ]
    ].copy()
    comparison_md["winner_logloss"] = comparison_md["winner_logloss"].map(lambda value: f"{value:.6f}")
    comparison_md["logloss_diff_vs_market"] = comparison_md["logloss_diff_vs_market"].map(
        lambda value: f"{value:+.6f}"
    )
    comparison_md["logloss_improvement_pct_vs_market"] = comparison_md[
        "logloss_improvement_pct_vs_market"
    ].map(lambda value: f"{value:+.2f}%")
    for column in ["top1_hit_rate", "top1_agreement_with_market"]:
        comparison_md[column] = comparison_md[column].map(_format_percent)
    comparison_md["top1_roi_pct"] = comparison_md["top1_roi_pct"].map(lambda value: f"{value:.2f}%")
    comparison_md = comparison_md.rename(
        columns={
            "model": "モデル",
            "winner_logloss": "Winner Logloss",
            "logloss_diff_vs_market": "市場との差",
            "logloss_improvement_pct_vs_market": "市場比改善率",
            "top1_hits": "Top1的中",
            "top1_hit_rate": "Top1的中率",
            "top1_roi_pct": "Top1単勝ROI",
            "top1_agreement_with_market": "市場Top1一致率",
        }
    )

    category_md = categories[
        [
            "category",
            "model",
            "races",
            "winner_logloss",
            "logloss_diff_vs_market",
            "top1_hit_rate",
            "top1_roi_pct",
        ]
    ].copy()
    category_md["winner_logloss"] = category_md["winner_logloss"].map(lambda value: f"{value:.5f}")
    category_md["logloss_diff_vs_market"] = category_md["logloss_diff_vs_market"].map(
        lambda value: f"{value:+.5f}"
    )
    category_md["top1_hit_rate"] = category_md["top1_hit_rate"].map(_format_percent)
    category_md["top1_roi_pct"] = category_md["top1_roi_pct"].map(lambda value: f"{value:.2f}%")
    category_md = category_md.rename(
        columns={
            "category": "カテゴリ",
            "model": "モデル",
            "races": "レース",
            "winner_logloss": "Winner Logloss",
            "logloss_diff_vs_market": "市場との差",
            "top1_hit_rate": "Top1的中率",
            "top1_roi_pct": "Top1単勝ROI",
        }
    )

    return f"""# RACEVERSE 市場比較・オッズ帯・カテゴリ分析

## 集計条件

- Walk-Forward予測: 2025-09-06〜2026-08-30
- 評価レース: {counts['analysis_races']:,}
- 評価出走馬: {counts['analysis_horses']:,}
- RACEVERSE予測: 校正後確率 `p_cal`
- 市場暗黙勝率: 確定単勝オッズの逆数をレース内で正規化
- 単勝購入額: 1頭100円
- 欠損確定オッズ: {counts['missing_odds']:,}頭
- 欠損レース属性: {counts['missing_race_attributes']:,}頭
- 注意: 確定オッズによる事後分析であり、発走前に同一オッズで購入できることを保証しない

## 1. 市場とRACEVERSEのWinner Logloss

`市場との差 = モデルWinner Logloss - 市場Winner Logloss`。負値は市場より良い。

{_markdown_table(comparison_md)}

この期間では市場のWinner Loglossが1.978751で最良となり、RACEVERSE最良のbaseでも市場より0.230414悪化した。市場Top1の的中率は32.49%、RACEVERSEの最高はbaseの25.87%だった。

## 2. O1〜O9: 全出走馬

全出走馬を各オッズ帯で100円ずつ購入した場合の参考ROI。各モデルの行では、そのモデルの平均予測勝率と同じ馬集合の実測勝率を比較する。

{_odds_markdown(odds, 'all_runners')}

## 3. O1〜O9: 各モデルのTop1選択馬

各レースで当該モデルの予測勝率が最大の1頭を選び、選択馬の確定単勝オッズ帯で集計した。

{_odds_markdown(odds, 'top1')}

## 4. 芝ダート×距離8カテゴリ

- D1: 1,400m以下
- D2: 1,400m超〜1,800m以下
- D3: 1,800m超〜2,200m以下
- D4: 2,200m超

{_markdown_table(category_md)}

## 5. 生成CSV

- [{(output_dir / 'market_comparison.csv').name}](./{output_dir.relative_to(ROOT).as_posix()}/market_comparison.csv)
- [{(output_dir / 'odds_band_analysis.csv').name}](./{output_dir.relative_to(ROOT).as_posix()}/odds_band_analysis.csv)
- [{(output_dir / 'category_performance.csv').name}](./{output_dir.relative_to(ROOT).as_posix()}/category_performance.csv)

## 再実行

```bash
.venv/bin/python scripts/raceverse_market_analysis.py
```
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    frame, counts = load_analysis_data(args.input_dir)
    comparison = market_comparison(frame)
    odds = odds_band_analysis(frame)
    categories = category_performance(frame)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.output_dir / "market_comparison.csv", index=False)
    odds.to_csv(args.output_dir / "odds_band_analysis.csv", index=False)
    categories.to_csv(args.output_dir / "category_performance.csv", index=False)
    args.report.write_text(
        render_report(comparison, odds, categories, counts, args.output_dir),
        encoding="utf-8",
    )
    print(f"races={counts['analysis_races']} horses={counts['analysis_horses']}")
    print(comparison[["model", "winner_logloss", "logloss_diff_vs_market", "top1_hit_rate", "top1_roi_pct"]])
    print(f"wrote {args.output_dir}")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()

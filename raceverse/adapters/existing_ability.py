"""既存Ranker(86特徴量・LGBMRanker)の能力指標を読み取り専用で取得するアダプタ。

能力指標 `ability_score` = 既存Rankerの raw score(`ranker_score`)。値の大きいほど強い。
秒や勝率として直接解釈しない。既存の学習・予測コードには一切変更を加えず、関数を呼び出すだけ。

過去レースの能力値は、月次Walk-Forwardで「その月より前のデータだけで学習したモデル」の
予測値(OOF)に限る。全期間学習済みモデルによる過去への当てはめは使わない。
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from raceverse.periods import floor_timestamp, period_range

ROOT = Path(__file__).resolve().parents[2]
EXISTING_WF_CSV = ROOT / "reports" / "ranker_walk_forward_86_features" / "walk_forward_predictions.csv"
PRODUCTION_CSV = ROOT / "output" / "predictions.csv"
OOF_CACHE = ROOT / "data" / "cache" / "raceverse" / "ability_oof_pre_test.parquet"
WEEKLY_OOF_CACHE = ROOT / "data" / "cache" / "raceverse" / "ability_oof_weekly.parquet"
LOGGER = logging.getLogger(__name__)

ABILITY_COLUMNS = ["race_id", "horse_id", "ability_score", "score_available_at", "model_training_cutoff"]


def build_oof(start: str, end: str, out_path: Path = OOF_CACHE) -> pd.DataFrame:
    """[start, end) の各月について、既存Rankerと同一手順の月次Walk-Forward予測を生成して保存する。"""
    from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES
    from src.ranker_walk_forward_backtest import CALIBRATION_MONTHS, load_frame, month_starts, monthly_walk_forward

    frame, features = load_frame(RANKER_MARGIN_CORRECTION_FEATURES)
    months = month_starts(pd.Timestamp(start), pd.Timestamp(end))
    predictions, _ = monthly_walk_forward(frame, features, months, CALIBRATION_MONTHS)
    table = _to_ability_table(predictions)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out_path, index=False)
    LOGGER.info("ability OOF saved: %s rows=%d races=%d", out_path, len(table), table["race_id"].nunique())
    return table


def build_oof_weekly(start: str, end: str, out_path: Path = WEEKLY_OOF_CACHE) -> pd.DataFrame:
    """[start, end) の各週(月曜始まり)について、その週の月曜より前の結果だけで学習したRankerのスコアを保存する。

    学習は既存Rankerと同じ特徴量・同じ LGBMRanker(ranker_scores)。確率の温度校正は能力指標(raw score)に不要なので行わない。
    """
    from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES
    from src.ranker_walk_forward_backtest import load_frame, ranker_scores

    frame, features = load_frame(RANKER_MARGIN_CORRECTION_FEATURES)
    parts = []
    for week in period_range(pd.Timestamp(start), pd.Timestamp(end), "week"):
        evaluation = frame[(frame["date"] >= week) & (frame["date"] < week + pd.Timedelta(days=7))]
        if evaluation.empty:
            continue
        scores = ranker_scores(frame[frame["date"] < week], evaluation, features)
        parts.append(pd.DataFrame({
            "race_id": evaluation["race_id"].astype(str).to_numpy(),
            "horse_id": evaluation["horse_id"].astype(str).to_numpy(),
            "ability_score": scores.astype(float),
            "score_available_at": evaluation["date"].to_numpy(),
            "model_training_cutoff": week - pd.Timedelta(days=1),
        }))
        LOGGER.info("weekly ability %s: %d rows", week.date(), len(evaluation))
    table = pd.concat(parts, ignore_index=True)[ABILITY_COLUMNS]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out_path, index=False)
    LOGGER.info("weekly ability OOF saved: %s rows=%d races=%d", out_path, len(table), table["race_id"].nunique())
    return table


def append_oof_weekly(end: str, out_path: Path = WEEKLY_OOF_CACHE) -> pd.DataFrame:
    """既存の週次OOFの最終週(未完了週の可能性があるため含めて)から end(排他)まで再計算して追記する。"""
    existing = load_weekly_ability_table(out_path)
    last_week = floor_timestamp(pd.Timestamp(existing["score_available_at"].max()), "week")
    kept = existing[pd.to_datetime(existing["score_available_at"]) < last_week]
    new = build_oof_weekly(str(last_week.date()), end, out_path.with_name(out_path.stem + "_new.parquet"))
    table = pd.concat([kept, new], ignore_index=True)[ABILITY_COLUMNS]
    table.to_parquet(out_path, index=False)
    out_path.with_name(out_path.stem + "_new.parquet").unlink(missing_ok=True)
    LOGGER.info("weekly ability OOF appended from %s: total rows=%d", last_week.date(), len(table))
    return table


def load_weekly_ability_table(path: Path = WEEKLY_OOF_CACHE) -> pd.DataFrame:
    """週次Walk-Forwardで作った能力指標だけを返す(月次OOFや既存12か月出力とは混ぜない)。"""
    if not path.exists():
        raise FileNotFoundError(f"週次の能力指標OOFがありません: {path} (python -m raceverse.adapters.existing_ability --weekly で作成)")
    return pd.read_parquet(path)


def _to_ability_table(predictions: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame({
        "race_id": predictions["race_id"].astype(str),
        "horse_id": predictions["horse_id"].astype(str),
        "ability_score": predictions["ranker_score"].astype(float),
        "score_available_at": pd.to_datetime(predictions["date"]),
        "model_training_cutoff": pd.to_datetime(predictions["model_train_end_date"]),
    })
    return table[ABILITY_COLUMNS]


def load_ability_table(
    oof_cache: Path = OOF_CACHE,
    existing_csv: Path = EXISTING_WF_CSV,
) -> pd.DataFrame:
    """過去OOF(事前生成キャッシュ) + 既存12か月Walk-Forward出力を結合して返す。"""
    parts = []
    if oof_cache.exists():
        parts.append(pd.read_parquet(oof_cache))
    else:
        LOGGER.warning("ability OOF cache not found (%s); training window will be limited", oof_cache)
    if existing_csv.exists():
        parts.append(_to_ability_table(pd.read_csv(existing_csv, dtype={"race_id": str, "horse_id": str})))
    if not parts:
        raise FileNotFoundError("既存Rankerの能力指標(OOF)が見つかりません")
    table = pd.concat(parts, ignore_index=True)
    table = table.drop_duplicates(["race_id", "horse_id"], keep="last")
    return table.reset_index(drop=True)


def load_production_ability(path: Path = PRODUCTION_CSV) -> pd.DataFrame:
    """未開催レース用。output/predictions.csv(本番Ranker出力)の ranker_score を返す。

    キーは (race_date, idJyoCD, idRaceNum, Umaban)。race_idにはkaiji/nichijiが必要なため呼び出し側で結合する。
    """
    frame = pd.read_csv(path, dtype={"idJyoCD": str, "idRaceNum": str, "KisyuCode": str})
    frame["idJyoCD"] = frame["idJyoCD"].str.zfill(2)
    frame["idRaceNum"] = frame["idRaceNum"].str.zfill(2)
    return frame.rename(columns={"ranker_score": "ability_score"})[
        ["race_date", "idJyoCD", "idRaceNum", "Umaban", "Bamei", "ability_score", "model_train_end_date"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="既存Rankerの過去OOF能力値を生成してキャッシュする")
    parser.add_argument("--start", default="2022-09-01")
    parser.add_argument("--end", default="2025-09-01")
    parser.add_argument("--weekly", action="store_true", help="週ごとに再学習した能力指標を生成する(ability_oof_weekly.parquet)")
    parser.add_argument("--append", action="store_true",
                        help="--weekly と併用: 既存キャッシュの最終週以降だけを再計算して追記する(--start は無視)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.weekly and args.append:
        append_oof_weekly(args.end)
    elif args.weekly:
        build_oof_weekly(args.start, args.end)
    else:
        build_oof(args.start, args.end)


if __name__ == "__main__":
    main()

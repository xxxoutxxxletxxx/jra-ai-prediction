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

ROOT = Path(__file__).resolve().parents[2]
EXISTING_WF_CSV = ROOT / "reports" / "ranker_walk_forward_86_features" / "walk_forward_predictions.csv"
PRODUCTION_CSV = ROOT / "output" / "predictions.csv"
OOF_CACHE = ROOT / "data" / "cache" / "raceverse" / "ability_oof_pre_test.parquet"
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    build_oof(args.start, args.end)


if __name__ == "__main__":
    main()

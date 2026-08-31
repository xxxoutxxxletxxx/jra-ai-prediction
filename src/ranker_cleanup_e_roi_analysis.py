#!/usr/bin/env python3
"""ROI/condition breakdown for the CLEANUP_E Ranker walk-forward predictions.

Betting rule: 単勝+複勝 on the horse the Ranker scores #1 in each race (prediction_rank == 1).
Enriches reports/ranker_cleanup_e_redesign/cleanup_e_predictions.csv (which only carries win
payouts and no course/distance/class columns) with:
- racecourse / surface / distance / race_first_prize / class_code from the Phase5 feature cache.
- 複勝(place) payouts and the official race name (RaceInfoHondai), both looked up from race.db
  directly (the Ranker payout_map() only builds win payouts).
Outputs condition breakdowns (racecourse/surface/distance/season/prize-quartile) and a list of
long-shot (人気薄) top picks with race name + horse name for manual review.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean

import pandas as pd

try:
    from src.backtest import RACE_KEY, distance_band, integer, payout, text
except ModuleNotFoundError:
    from backtest import RACE_KEY, distance_band, integer, payout, text

ROOT = Path(__file__).resolve().parent.parent
RACE_DB = ROOT / "data" / "raw" / "race.db"
PREDICTIONS = ROOT / "reports" / "ranker_cleanup_e_redesign" / "cleanup_e_predictions.csv"
CACHE = ROOT / "data" / "cache" / "phase5_f_features.parquet"
OUTPUT = ROOT / "reports" / "ranker_cleanup_e_roi_analysis"
LONGSHOT_POPULARITY_THRESHOLD = 6


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def race_key_from_id(race_id: str) -> tuple[str, ...]:
    return tuple(race_id.split("-"))


def load_place_payouts_and_names(min_year: int) -> tuple[dict[tuple[str, ...], dict], dict[tuple[str, ...], dict]]:
    key_columns = list(RACE_KEY)
    pay_columns = key_columns + [f"PayFukusyo{i}{suffix}" for i in range(5) for suffix in ("Umaban", "Pay")]
    race_columns = key_columns + ["RaceInfoHondai", "JyokenName", "GradeCD"]
    with sqlite3.connect(RACE_DB) as connection:
        pay_rows = [dict(zip(pay_columns, record))
                    for record in connection.execute(f"SELECT {', '.join(pay_columns)} FROM NL_HR_PAY WHERE idYear >= '{min_year}'")]
        race_rows = [dict(zip(race_columns, record))
                     for record in connection.execute(f"SELECT {', '.join(race_columns)} FROM NL_RA_RACE WHERE idYear >= '{min_year}'")]
    pays = {tuple(text(row[column]) for column in key_columns): row for row in pay_rows}
    races = {tuple(text(row[column]) for column in key_columns): row for row in race_rows}
    return pays, races


def season_label(month: int) -> str:
    return {12: "冬", 1: "冬", 2: "冬", 3: "春", 4: "春", 5: "春",
            6: "夏", 7: "夏", 8: "夏", 9: "秋", 10: "秋", 11: "秋"}[month]


def prize_band(prize: float) -> str:
    if prize < 11_000_000:
        return "8.0-10.9M"
    if prize < 16_000_000:
        return "11.0-15.9M"
    if prize < 25_000_000:
        return "16.0-24.9M"
    if prize < 50_000_000:
        return "25.0-49.9M"
    return "50M+"


def roi_summary(rows: pd.DataFrame) -> dict:
    races = len(rows)
    investment = races * 100
    win_return = rows["win_payout"].sum()
    place_return = rows["place_payout"].sum()
    return {"races": races, "win_hit_rate": rows["target"].mean() if races else None,
            "place_hit_rate": (rows["actual_rank"] <= 3).mean() if races else None,
            "win_investment": investment, "win_return": win_return,
            "win_roi": win_return / investment * 100 if investment else None,
            "place_investment": investment, "place_return": place_return,
            "place_roi": place_return / investment * 100 if investment else None}


def aggregate_by(rows: pd.DataFrame, key: str) -> list[dict]:
    out = []
    for value, group in rows.groupby(key):
        summary = roi_summary(group)
        out.append({key: value, **summary})
    return sorted(out, key=lambda item: item["races"], reverse=True)


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS)
    top_picks = predictions[predictions["prediction_rank"] == 1].copy()
    min_year = int(pd.to_datetime(top_picks["date"]).dt.year.min())

    cache_columns = ["race_id", "horse_id", "racecourse", "surface", "distance", "race_first_prize", "umaban", "class_code"]
    available = set(pd.read_parquet(CACHE).columns)
    cache = pd.read_parquet(CACHE, columns=[column for column in cache_columns if column in available])
    top_picks["race_id"] = top_picks["race_id"].astype(str)
    top_picks["horse_id"] = top_picks["horse_id"].astype(str)
    cache["race_id"] = cache["race_id"].astype(str)
    cache["horse_id"] = cache["horse_id"].astype(str)
    top_picks = top_picks.merge(cache, on=["race_id", "horse_id"], how="left")

    pays, races = load_place_payouts_and_names(min_year)
    place_payouts, race_names = [], []
    for race_id, umaban in zip(top_picks["race_id"], top_picks["umaban"]):
        key = race_key_from_id(race_id)
        place_payouts.append(payout(pays.get(key), "place", integer(umaban)))
        race_row = races.get(key, {})
        race_names.append(text(race_row.get("RaceInfoHondai")) or text(race_row.get("JyokenName")))
    top_picks["place_payout"] = place_payouts
    top_picks["race_name"] = race_names
    top_picks["distance_band"] = top_picks["distance"].map(distance_band)
    top_picks["season"] = pd.to_datetime(top_picks["date"]).dt.month.map(season_label)
    top_picks["prize_band"] = top_picks["race_first_prize"].map(prize_band)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    top_picks.to_csv(OUTPUT / "top_pick_bets.csv", index=False)

    overall = roi_summary(top_picks)
    breakdowns = {
        "by_racecourse": aggregate_by(top_picks, "racecourse"),
        "by_surface": aggregate_by(top_picks, "surface"),
        "by_distance_band": aggregate_by(top_picks, "distance_band"),
        "by_season": aggregate_by(top_picks, "season"),
        "by_prize_band": aggregate_by(top_picks, "prize_band"),
    }
    for name, rows in breakdowns.items():
        write_csv(OUTPUT / f"{name}.csv", rows)

    longshots = top_picks[top_picks["popularity"] >= LONGSHOT_POPULARITY_THRESHOLD].copy()
    longshots = longshots.sort_values(["date", "race_id"])
    longshot_columns = ["date", "racecourse", "race_name", "horse_name", "popularity", "odds",
                        "ranker_win_probability", "actual_rank", "target", "win_payout", "place_payout"]
    write_csv(OUTPUT / "longshot_top_picks.csv", longshots[longshot_columns].to_dict("records"))
    longshot_summary = roi_summary(longshots)
    longshot_hits = longshots[(longshots["target"] == 1) | (longshots["actual_rank"] <= 3)]

    summary = {"strategy": "prediction_rank==1 の馬に単勝100円+複勝100円",
               "period": {"start": str(top_picks["date"].min()), "end": str(top_picks["date"].max())},
               "overall": overall, "breakdowns": breakdowns,
               "longshot": {"popularity_threshold": LONGSHOT_POPULARITY_THRESHOLD, "summary": longshot_summary,
                            "bet_count": len(longshots), "hit_count": len(longshot_hits)}}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = ["# CLEANUP_E Ranker Top-Pick ROI Analysis", "",
             f"- 対象: {overall['races']}レース（prediction_rank==1の馬に単勝・複勝を100円ずつ）",
             f"- 期間: {top_picks['date'].min()} 〜 {top_picks['date'].max()}",
             f"- 単勝: 的中率 {overall['win_hit_rate']:.2%}, ROI {overall['win_roi']:.1f}%, 投資{overall['win_investment']:.0f}円/回収{overall['win_return']:.0f}円",
             f"- 複勝: 的中率 {overall['place_hit_rate']:.2%}, ROI {overall['place_roi']:.1f}%, 投資{overall['place_investment']:.0f}円/回収{overall['place_return']:.0f}円",
             "", "## 競馬場別"]
    for row in breakdowns["by_racecourse"]:
        lines.append(f"- {row['racecourse']}: {row['races']}レース, 単勝ROI {row['win_roi']:.1f}%, 複勝ROI {row['place_roi']:.1f}%")
    lines += ["", "## 馬場（芝/ダート）別"]
    for row in breakdowns["by_surface"]:
        lines.append(f"- {row['surface']}: {row['races']}レース, 単勝ROI {row['win_roi']:.1f}%, 複勝ROI {row['place_roi']:.1f}%")
    lines += ["", "## 距離帯別"]
    for row in breakdowns["by_distance_band"]:
        lines.append(f"- {row['distance_band']}: {row['races']}レース, 単勝ROI {row['win_roi']:.1f}%, 複勝ROI {row['place_roi']:.1f}%")
    lines += ["", "## 季節別"]
    for row in breakdowns["by_season"]:
        lines.append(f"- {row['season']}: {row['races']}レース, 単勝ROI {row['win_roi']:.1f}%, 複勝ROI {row['place_roi']:.1f}%")
    lines += ["", "## クラス（1着賞金帯）別"]
    for row in breakdowns["by_prize_band"]:
        lines.append(f"- {row['prize_band']}: {row['races']}レース, 単勝ROI {row['win_roi']:.1f}%, 複勝ROI {row['place_roi']:.1f}%")
    lines += ["", f"## 人気薄（{LONGSHOT_POPULARITY_THRESHOLD}番人気以下）でモデルが1位評価した馬",
             f"- 件数: {len(longshots)}, 単勝的中 {int(longshots['target'].sum())}件, 複勝的中 {int((longshots['actual_rank'] <= 3).sum())}件",
             f"- 単勝ROI {longshot_summary['win_roi']:.1f}%, 複勝ROI {longshot_summary['place_roi']:.1f}%",
             "- 詳細は longshot_top_picks.csv 参照。的中例（上位10件）:"]
    for _, row in longshot_hits.sort_values("win_payout", ascending=False).head(10).iterrows():
        lines.append(f"  - {row['date']} {row['racecourse']} 「{row['race_name']}」 {row['horse_name']}"
                     f"（{int(row['popularity'])}番人気, オッズ{row['odds']}）: 単勝払戻{row['win_payout']:.0f}円, 複勝払戻{row['place_payout']:.0f}円")
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "overall": overall,
                      "longshot_bet_count": len(longshots), "longshot_hit_count": len(longshot_hits)},
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

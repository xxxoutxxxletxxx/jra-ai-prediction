"""RACEVERSE の勝率1位馬(Top1)を毎レース買った場合の的中率・回収率を、条件別に集計する。

入力: raceverse.cli backtest の出力ディレクトリ(predictions.csv / race_level.csv)
出力: 条件別CSVと Markdown レポート。単勝・複勝の払戻は race.db(NL_HR_PAY)の確定払戻を使う。

集計条件: クラス(1着賞金帯) / 競馬場 / 芝・ダート / 距離 / 馬場(良・良以外)とその組み合わせ。
full は集計しない(入力に含まれていれば除外する)。確定オッズ・払戻による事後分析で、発走前に購入できた成績ではない。
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.raceverse_market_analysis import (
    LEVELS,
    category_performance,
    load_analysis_data,
    market_comparison,
    odds_band_analysis,
    top1_rows,
)

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "raw" / "race.db"
LOGGER = logging.getLogger(__name__)
KEYS = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
COURSES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
           "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}
PRIZE_BINS = [0, 11_000_000, 16_000_000, 25_000_000, 50_000_000, np.inf]
PRIZE_LABELS = ["800〜1,099万円", "1,100〜1,599万円", "1,600〜2,499万円", "2,500〜4,999万円", "5,000万円以上"]
DISTANCE_BINS = [0, 1000, 1150, 1600, 1700, 2500, np.inf]
DISTANCE_LABELS = ["1000m以下", "1150m", "1200〜1600m", "1700m", "1800〜2500m", "2600m以上"]
GRADES = {"A": "G1", "B": "G2", "C": "G3", "L": "Listed"}
MIN_BETS = 30
PREDICTION_COLUMNS = ["race_id", "horse_id", "umaban", "level", "date", "finish", "target", "p_cal", "win_odds_reference",
                      "win_payout"]


def read_official_results(years: tuple[int, int]) -> tuple[dict, dict, dict]:
    """race_id -> (賞金, GradeCD)、(race_id, 馬番) -> 単勝払戻、(race_id, 馬番) -> 複勝払戻(100円あたり)。"""
    columns = KEYS + ["GradeCD", "Honsyokin0"]
    columns += [f"PayTansyo{i}{s}" for i in range(3) for s in ("Umaban", "Pay")]
    columns += [f"PayFukusyo{i}{s}" for i in range(5) for s in ("Umaban", "Pay")]
    query = (f"SELECT {', '.join(columns)} FROM NL_RA_RACE JOIN NL_HR_PAY USING ({', '.join(KEYS)}) "
             f"WHERE idYear >= '{years[0]}' AND idYear <= '{years[1]}'")
    with sqlite3.connect(DB) as con:
        records = con.execute(query).fetchall()
    info, win, place = {}, {}, {}
    for rec in records:
        race_id = "-".join(str(v).strip() for v in rec[:6])
        info[race_id] = (float(rec[7] or 0) * 100.0, str(rec[6] or "").strip())
        for i in range(3):
            _store(win, race_id, rec[8 + 2 * i], rec[9 + 2 * i])
        for i in range(5):
            _store(place, race_id, rec[14 + 2 * i], rec[15 + 2 * i])
    return info, win, place


def _store(target: dict, race_id: str, number, amount) -> None:
    try:
        horse, pay = int(float(number or 0)), float(amount or 0)
    except (TypeError, ValueError):
        return
    if horse:
        target[(race_id, horse)] = pay


def prepare_frame(input_dir: Path, window: tuple[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw = pd.read_csv(input_dir / "predictions.csv", dtype={"race_id": str, "horse_id": str, "level": str},
                      parse_dates=["date"])
    raw = raw[raw["level"].isin(LEVELS)]
    raw = raw[(raw["date"] >= window[0]) & (raw["date"] < window[1])]
    if set(raw["level"]) != set(LEVELS):
        raise ValueError(f"expected levels {LEVELS}, got {sorted(set(raw['level']))}")
    complete = raw.groupby(["level", "race_id"])["p_cal"].apply(lambda s: s.notna().all()).groupby("race_id").all()
    keep = set(complete[complete].index)
    frame = raw[raw["race_id"].isin(keep)].copy()
    frame["umaban"] = pd.to_numeric(frame["umaban"], errors="raise").astype(int)

    years = (int(frame["date"].dt.year.min()), int(frame["date"].dt.year.max()))
    info, win, place = read_official_results(years)
    frame["win_payout"] = [win.get((r, u), 0.0) for r, u in zip(frame["race_id"], frame["umaban"])]
    frame["place_payout"] = [place.get((r, u), 0.0) for r, u in zip(frame["race_id"], frame["umaban"])]
    frame["prize_yen"] = frame["race_id"].map(lambda r: info.get(r, (np.nan, ""))[0])
    frame["grade_cd"] = frame["race_id"].map(lambda r: info.get(r, (np.nan, ""))[1])

    races = pd.read_csv(input_dir / "race_level.csv", dtype={"race_id": str})
    attrs = races[["race_id", "track", "surface", "distance_m", "going"]].drop_duplicates("race_id")
    frame = frame.merge(attrs, on="race_id", how="left", validate="many_to_one")
    if frame[["track", "surface", "distance_m", "going", "prize_yen"]].isna().any().any():
        raise ValueError("missing race attributes")

    frame["クラス"] = pd.cut(frame["prize_yen"], PRIZE_BINS, labels=PRIZE_LABELS, right=False).astype(str)
    frame["競馬場"] = frame["track"].astype(str).str.zfill(2).map(COURSES)
    frame["芝ダート"] = frame["surface"].map({"turf": "芝", "dirt": "ダート"})
    frame["距離"] = pd.cut(frame["distance_m"], DISTANCE_BINS, labels=DISTANCE_LABELS, right=True).astype(str)
    frame["馬場"] = frame["going"].map(lambda v: "良" if int(v) == 1 else "良以外")
    frame["格付"] = frame["grade_cd"].map(lambda v: GRADES.get(v, f"GradeCD={v}" if v else "GradeCD空欄"))
    if frame[["クラス", "競馬場", "芝ダート", "距離", "馬場"]].isin(["nan", None]).any().any():
        raise ValueError("unclassified race attribute")
    return frame, races, {"races_total": int(raw["race_id"].nunique()), "races_complete": len(keep)}


def summarize(group: pd.DataFrame) -> dict:
    n = len(group)
    stake = n * 100.0
    return {
        "bets": n,
        "win_hits": int((group["win_payout"] > 0).sum()),
        "win_hit_rate_pct": float((group["win_payout"] > 0).mean() * 100),
        "win_roi_pct": float(group["win_payout"].sum() / stake * 100),
        "place_hits": int((group["place_payout"] > 0).sum()),
        "place_hit_rate_pct": float((group["place_payout"] > 0).mean() * 100),
        "place_roi_pct": float(group["place_payout"].sum() / stake * 100),
    }


def aggregate(tops: dict[str, pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    rows = []
    for model, top in tops.items():
        groups = top.groupby(columns, observed=True) if columns else [((), top)]
        for key, group in groups:
            key = key if isinstance(key, tuple) else (key,)
            rows.append({"model": model, **dict(zip(columns, key)), **summarize(group)})
    return pd.DataFrame(rows)


def add_half_roi(combos: pd.DataFrame, tops: dict[str, pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    """上位条件が期間の前半・後半で続いているかを見る(前半・後半は対象レース数の中央日で分割)。"""
    out = combos.copy()
    first, second = [], []
    for row in out.itertuples(index=False):
        top = tops[row.model]
        mask = np.ones(len(top), dtype=bool)
        for column in columns:
            mask &= (top[column] == getattr(row, column)).to_numpy()
        part = top[mask]
        cut = top["date"].sort_values().iloc[len(top) // 2]
        early, late = part[part["date"] < cut], part[part["date"] >= cut]
        first.append(early["win_payout"].sum() / (len(early) * 100) * 100 if len(early) else np.nan)
        second.append(late["win_payout"].sum() / (len(late) * 100) * 100 if len(late) else np.nan)
    out["win_roi_first_half_pct"], out["win_roi_second_half_pct"] = first, second
    return out


def pct(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.1f}%"


def table(rows: list[list], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def dimension_table(stats: pd.DataFrame, column: str, order: list[str] | None, bet: str) -> str:
    hit, roi = f"{bet}_hit_rate_pct", f"{bet}_roi_pct"
    values = order or sorted(stats[column].unique())
    rows = []
    for value in values:
        sub = stats[stats[column] == value]
        if sub.empty:
            continue
        cells = [value, int(sub["bets"].iloc[0])]
        for model in LEVELS:
            r = sub[sub["model"] == model].iloc[0]
            cells.append(f"{pct(r[hit])} / {pct(r[roi])}")
        rows.append(cells)
    return table(rows, [column, "件数"] + [f"{m} 的中率/回収率" for m in LEVELS])


def combo_table(combos: pd.DataFrame, columns: list[str], model: str, limit: int) -> str:
    sub = combos[(combos["model"] == model) & (combos["bets"] >= MIN_BETS)]
    sub = sub.sort_values(["win_roi_pct", "bets"], ascending=[False, False]).head(limit)
    rows = [[*(getattr(r, c) for c in columns), r.bets, pct(r.win_hit_rate_pct), pct(r.win_roi_pct),
             pct(r.win_roi_first_half_pct), pct(r.win_roi_second_half_pct), pct(r.place_hit_rate_pct), pct(r.place_roi_pct)]
            for r in sub.itertuples(index=False)]
    return table(rows, columns + ["件数", "単勝的中率", "単勝回収率", "前半", "後半", "複勝的中率", "複勝回収率"])


def build_report(frame, counts, overall, singles, combos, market, window, refit_note) -> str:
    first, last = frame["date"].min().date(), frame["date"].max().date()
    by_year = frame.groupby(frame["date"].dt.year)["race_id"].nunique()
    lines = [
        "# RACEVERSE 条件別の的中率・回収率(full除外)", "",
        f"- 指定した評価窓: {window[0]}〜{window[1]}(終了日は含まない)。",
        f"- 校正済み予測が揃った実際の期間: {first}〜{last}、{counts['races_complete']:,}レース。",
        "- 年別レース数: " + "、".join(f"{y}年 {n:,}" for y, n in by_year.items()),
        f"- 予測方式: base / formation / pace のみ。fullは学習・予測・集計していません。{refit_note}",
        "- 買い方: 各レースで校正後勝率 `p_cal` が最大の馬を単勝100円、複勝100円ずつ購入したと仮定。同率は馬番の小さい馬。",
        "- 払戻は race.db の確定払戻。確定オッズ・払戻を使った事後参考値で、発走前に購入できた成績ではありません。",
        f"- クラスは1着賞金の区分で、実際のクラス名称ではありません。能力指標の対象が1着賞金800万円超のレースに限られるため、それ未満は含まれません。",
        f"- 組み合わせは件数{MIN_BETS}件未満を除外。多数の条件を事後に探索しているため、上位は偶然を含みます。前半・後半の両方で100%を超えるかも併せて確認してください。",
        "", "## 全体", "",
        table([[r.model, r.bets, pct(r.win_hit_rate_pct), pct(r.win_roi_pct), pct(r.place_hit_rate_pct), pct(r.place_roi_pct)]
               for r in overall.itertuples()], ["方式", "件数", "単勝的中率", "単勝回収率", "複勝的中率", "複勝回収率"]),
        "", "## 市場(確定単勝オッズ)との比較", "",
        table([[r.model, f"{r.winner_logloss:.4f}", f"{r.logloss_diff_vs_market:+.4f}", pct(r.top1_hit_rate * 100),
                f"{r.top1_roi_pct:.1f}%"] for r in market.itertuples()],
              ["モデル", "Winner Logloss", "市場との差", "Top1的中率", "Top1回収率"]),
        "", f"(Winner Loglossは勝ち馬が1頭のレースだけ: {counts['market_races']:,}レース。同着レースを除外)",
    ]
    for title, column, order in (("クラス(1着賞金帯)", "クラス", PRIZE_LABELS), ("競馬場", "競馬場", list(COURSES.values())),
                                 ("芝・ダート", "芝ダート", ["芝", "ダート"]), ("距離", "距離", DISTANCE_LABELS),
                                 ("馬場", "馬場", ["良", "良以外"]), ("格付(GradeCD)", "格付", None)):
        for bet, label in (("win", "単勝"), ("place", "複勝")):
            lines += ["", f"## {title}別 {label}(的中率 / 回収率)", "", dimension_table(singles[column], column, order, bet)]
    lines += ["", "## 組み合わせ(クラス × 競馬場 × 芝ダート × 距離 × 馬場)の単勝回収率上位", ""]
    columns = ["クラス", "競馬場", "芝ダート", "距離", "馬場"]
    for model in LEVELS:
        lines += [f"### {model}", "", combo_table(combos, columns, model, 15), ""]
    lines += ["## 注意", "",
              "- 芝・ダートはTrackCDから判定した値です。ただし能力指標を作る既存Rankerの特徴量側には、ダートを芝として扱う既知の不具合があり、芝ダート比較は暫定値です。",
              "- 全CSVは同じ出力ディレクトリにあります。"]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    window = (args.window_start, args.window_end)
    frame, _, counts = prepare_frame(args.input, window)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="raceverse-condition-") as tmp:
        tmp = Path(tmp)
        winners = frame[frame["level"] == LEVELS[0]].groupby("race_id")["target"].sum()
        # 同着で勝ち馬が複数いるレースは Winner Logloss の対象外(条件別集計には含める)
        single = frame[frame["race_id"].isin(set(winners[winners == 1].index))]
        single[PREDICTION_COLUMNS].to_csv(tmp / "predictions.csv", index=False)
        pd.read_csv(args.input / "race_level.csv", dtype={"race_id": str}).to_csv(tmp / "race_level.csv", index=False)
        market_frame, market_counts = load_analysis_data(tmp)
        market = market_comparison(market_frame)
        odds = odds_band_analysis(market_frame)
        categories = category_performance(market_frame)
    counts["market_races"] = market_counts["analysis_races"]
    market.to_csv(out / "market_comparison.csv", index=False)
    odds.to_csv(out / "odds_band_analysis.csv", index=False)
    categories.to_csv(out / "category_performance.csv", index=False)

    tops = {m: top1_rows(frame[frame["level"] == m], "p_cal") for m in LEVELS}
    overall = aggregate(tops, [])
    singles = {c: aggregate(tops, [c]) for c in ("クラス", "競馬場", "芝ダート", "距離", "馬場", "格付")}
    columns = ["クラス", "競馬場", "芝ダート", "距離", "馬場"]
    combos = add_half_roi(aggregate(tops, columns), tops, columns)
    overall.to_csv(out / "roi_overall.csv", index=False)
    pd.concat([df.rename(columns={c: "condition"}).assign(dimension=c) for c, df in singles.items()]).to_csv(
        out / "roi_by_condition.csv", index=False)
    combos.to_csv(out / "roi_by_combination.csv", index=False)
    yearly = aggregate({m: t.assign(年=t["date"].dt.year) for m, t in tops.items()}, ["年"])
    yearly.to_csv(out / "roi_by_year.csv", index=False)

    report = build_report(frame, counts, overall, singles, combos, market, window, args.note)
    args.report.write_text(report, encoding="utf-8")
    LOGGER.info("wrote %s", args.report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--window-start", default="2021-09-01")
    parser.add_argument("--window-end", default="2026-09-01")
    parser.add_argument("--note", default="")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

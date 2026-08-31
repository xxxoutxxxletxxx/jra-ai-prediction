#!/usr/bin/env python3
"""Race-class betting filter AB test on an existing prediction CSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
LABELS = ["新馬", "未勝利", "1勝", "2勝", "3勝", "OP", "L", "G3", "G2", "G1", "UNKNOWN"]
SCORE = {"新馬": 0, "未勝利": 0, "1勝": 1, "2勝": 2, "3勝": 3, "OP": 4, "L": 5, "G3": 6, "G2": 7, "G1": 8, "UNKNOWN": np.nan}


def norm(value):
    return unicodedata.normalize("NFKC", str(value or "")).strip().lower()


def race_id(values):
    return "-".join(str(values.get(key, "")).zfill(2) if key != "idYear" else str(values.get(key, "")) for key in KEYS)


def classify(row):
    name = norm(f"{row.get('JyokenName', '')} {row.get('RaceInfoHondai', '')} {row.get('RaceInfoFukudai', '')}")
    grade = norm(row.get("GradeCD", "")).upper()
    grade_map = {"A": "G1", "B": "G2", "C": "G3"}
    if grade in grade_map:
        return grade_map[grade]
    if "g1" in name or "ｇ１" in name:
        return "G1"
    if "g2" in name or "ｇ２" in name:
        return "G2"
    if "g3" in name or "ｇ３" in name:
        return "G3"
    if grade == "L" or "listed" in name or "リステッド" in name:
        return "L"
    if "新馬" in name:
        return "新馬"
    if "未勝利" in name:
        return "未勝利"
    if any(token in name for token in ("1勝", "１勝", "500万", "５００万")):
        return "1勝"
    if any(token in name for token in ("2勝", "２勝", "1000万", "１０００万")):
        return "2勝"
    if any(token in name for token in ("3勝", "３勝", "1600万", "１６００万")):
        return "3勝"
    if "オープン" in name or "open" in name or "ｏｐ" in name or name.endswith("op"):
        return "OP"
    return "UNKNOWN"


def metadata(db_path, race_ids):
    con = sqlite3.connect(db_path)
    columns = KEYS + ["GradeCD", "JyokenName", "RaceInfoHondai", "RaceInfoFukudai", "Honsyokin0"]
    query = f"SELECT {', '.join(columns)} FROM NL_RA_RACE"
    result = {}
    wanted = set(race_ids)
    for values in con.execute(query):
        raw = dict(zip(columns, values))
        rid = race_id(raw)
        if rid in wanted:
            label = classify(raw)
            result[rid] = {"normalized_race_class": label, "race_class_score": SCORE[label],
                           "race_first_prize": float(raw.get("Honsyokin0") or 0) * 100,
                           "race_name": raw.get("RaceInfoHondai") or raw.get("JyokenName") or "",
                           "condition_name": raw.get("JyokenName") or "", "grade_code_raw": raw.get("GradeCD") or ""}
    con.close()
    return result


def safe_float(series):
    return pd.to_numeric(series, errors="coerce")


def auc(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pos, neg = y.sum(), len(y) - y.sum()
    if not pos or not neg:
        return np.nan
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def selected_top1(df, labels=None):
    races = df[df["normalized_race_class"].isin(labels)] if labels is not None else df
    return races[races["prediction_rank"] == 1].copy()


def metrics(df):
    if df.empty:
        return {"races": 0, "horses": 0, "top1_wins": 0, "top1_places": 0, "win_rate": np.nan, "place_rate": np.nan,
                "logloss": np.nan, "brier": np.nan, "auc": np.nan, "top1_accuracy": np.nan, "top3_accuracy": np.nan}
    top = selected_top1(df)
    y = df["is_win"].astype(int).to_numpy()
    p = np.clip(df["predicted_probability"].astype(float).to_numpy(), 1e-15, 1 - 1e-15)
    race_count = df["race_id"].nunique()
    return {"races": race_count, "horses": len(df), "top1_wins": int(top["is_win"].sum()),
            "top1_places": int(top["is_place"].sum()), "win_rate": float(top["is_win"].mean()),
            "place_rate": float(top["is_place"].mean()), "logloss": float(-(y * np.log(p) + (1-y) * np.log(1-p)).mean()),
            "brier": float(np.mean((y-p) ** 2)), "auc": auc(y, p),
            "top1_accuracy": float(top["is_win"].mean()),
            "top3_accuracy": float(df.assign(_top3=(df["prediction_rank"] <= 3) & (df["is_win"] == 1)).groupby("race_id")["_top3"].any().mean())}


def betting(df):
    top = selected_top1(df)
    investment = len(top) * 100
    win_payout = float(top["win_payout"].sum())
    place_payout = float(top["place_payout"].sum())
    return {"win_investment": investment, "win_payout": win_payout, "win_profit": win_payout-investment,
            "win_roi": win_payout/investment*100 if investment else np.nan,
            "place_investment": investment, "place_payout": place_payout, "place_profit": place_payout-investment,
            "place_roi": place_payout/investment*100 if investment else np.nan}


def odds_stats(df):
    top = selected_top1(df)
    odds = safe_float(top["odds"])
    wins = top[top["is_win"] == 1]
    win_odds = safe_float(wins["odds"])
    popularity = safe_float(top["popularity"])
    return {"top1_mean_odds": odds.mean(), "top1_median_odds": odds.median(),
            "hit_mean_odds": win_odds.mean(), "hit_median_odds": win_odds.median(),
            "top1_mean_popularity": popularity.mean(), "top1_median_popularity": popularity.median()}


def summary_row(name, df):
    return {"filter": name, **metrics(df), **betting(df), **odds_stats(df)}


def band_summary(df, field, bands, name):
    top = selected_top1(df)
    values = safe_float(top[field])
    rows = []
    for label, low, high in bands:
        mask = (values >= low) & (values < high)
        part = top[mask]
        investment = len(part)*100
        rows.append({"filter": name, "band": label, "bets": len(part), "wins": int(part["is_win"].sum()),
                     "win_rate": part["is_win"].mean() if len(part) else np.nan,
                     "win_roi": part["win_payout"].sum()/investment*100 if investment else np.nan,
                     "places": int(part["is_place"].sum()), "place_rate": part["is_place"].mean() if len(part) else np.nan,
                     "place_roi": part["place_payout"].sum()/investment*100 if investment else np.nan})
    return rows


def bootstrap(df, n=3000, seed=42):
    rng = np.random.default_rng(seed)
    top = selected_top1(df).reset_index(drop=True)
    if top.empty:
        return {"win_rate_ci_low": np.nan, "win_rate_ci_high": np.nan, "win_roi_ci_low": np.nan, "win_roi_ci_high": np.nan,
                "place_roi_ci_low": np.nan, "place_roi_ci_high": np.nan}
    samples = rng.integers(0, len(top), size=(n, len(top)))
    win = top["is_win"].to_numpy()[samples]
    place = top["is_place"].to_numpy()[samples]
    win_pay = top["win_payout"].to_numpy()[samples]
    place_pay = top["place_payout"].to_numpy()[samples]
    return {"win_rate_ci_low": np.percentile(win.mean(axis=1), 2.5), "win_rate_ci_high": np.percentile(win.mean(axis=1), 97.5),
            "win_roi_ci_low": np.percentile(win_pay.sum(axis=1)/len(top), 2.5), "win_roi_ci_high": np.percentile(win_pay.sum(axis=1)/len(top), 97.5),
            "place_roi_ci_low": np.percentile(place_pay.sum(axis=1)/len(top), 2.5), "place_roi_ci_high": np.percentile(place_pay.sum(axis=1)/len(top), 97.5)}


def payout_sensitivity(df):
    top = selected_top1(df)
    result = {}
    for kind, col in (("win", "win_payout"), ("place", "place_payout")):
        ordered = top[col].sort_values(ascending=False).to_numpy()
        for n in (0, 1, 3, 5):
            result[f"{kind}_roi_exclude_top_{n}"] = (ordered[n:].sum() / (len(top)*100)*100) if len(top) else np.nan
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="reports/backtest_phase5_F_cached_df_432/predictions.csv")
    parser.add_argument("--db", default="data/raw/race.db")
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.predictions)
    df["prediction_rank"] = pd.to_numeric(df["prediction_rank"], errors="coerce")
    for col in ["actual_rank", "is_win", "is_place", "odds", "popularity", "predicted_probability", "win_payout", "place_payout"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    meta = metadata(args.db, df["race_id"].unique())
    info = pd.DataFrame.from_dict(meta, orient="index").rename_axis("race_id").reset_index()
    df = df.drop(columns=[c for c in ["normalized_race_class", "race_class_score", "race_first_prize"] if c in df])
    df = df.merge(info, on="race_id", how="left")
    df["normalized_race_class"] = df["normalized_race_class"].fillna("UNKNOWN")
    df["date"] = pd.to_datetime(df["date"])
    class_races = df[["race_id", "date", "racecourse", "race_name", "condition_name", "normalized_race_class", "race_class_score", "race_first_prize", "grade_code_raw"]].drop_duplicates("race_id")
    class_counts = class_races["normalized_race_class"].value_counts().reindex(LABELS, fill_value=0)
    validation = class_races.groupby("normalized_race_class", dropna=False).agg(races=("race_id", "nunique"), median_first_prize=("race_first_prize", "median"), min_first_prize=("race_first_prize", "min"), max_first_prize=("race_first_prize", "max")).reindex(LABELS).reset_index()
    validation["ratio"] = validation["races"] / len(class_races)
    validation.to_csv(out/"race_class_validation_crosswalk.csv", index=False)
    rows = []
    filters = {"ALL": None, "A_1plus": ["1勝", "2勝", "3勝", "OP", "L", "G3", "G2", "G1"], "B_2plus": ["2勝", "3勝", "OP", "L", "G3", "G2", "G1"], "1勝_ONLY": ["1勝"]}
    for name, labels in filters.items():
        part = df if labels is None else df[df["normalized_race_class"].isin(labels)]
        row = summary_row(name, part); row.update(payout_sensitivity(part)); rows.append(row)
    pd.DataFrame(rows).to_csv(out/"race_class_ab_summary.csv", index=False)
    individual = [summary_row(label, df[df["normalized_race_class"] == label]) for label in LABELS]
    pd.DataFrame(individual).to_csv(out/"race_class_individual_summary.csv", index=False)
    cumulative = {"1勝以上": filters["A_1plus"], "2勝以上": filters["B_2plus"], "3勝以上": ["3勝", "OP", "L", "G3", "G2", "G1"], "OP以上": ["OP", "L", "G3", "G2", "G1"], "重賞のみ": ["G3", "G2", "G1"]}
    pd.DataFrame([summary_row(name, df[df["normalized_race_class"].isin(labels)]) for name, labels in cumulative.items()]).to_csv(out/"race_class_cumulative_summary.csv", index=False)
    odds_bands = [("<2.0", 0, 2), ("2.0-2.9", 2, 3), ("3.0-4.9", 3, 5), ("5.0-9.9", 5, 10), ("10.0+", 10, np.inf)]
    pop_bands = [("1番人気", 1, 2), ("2番人気", 2, 3), ("3番人気", 3, 4), ("4-5番人気", 4, 6), ("6番人気以下", 6, np.inf)]
    pd.DataFrame(sum((band_summary(df[df["normalized_race_class"].isin(filters[n] or LABELS)], "odds", odds_bands, n) for n in ("ALL", "A_1plus", "B_2plus", "1勝_ONLY")), [])).to_csv(out/"race_class_odds_band_summary.csv", index=False)
    pd.DataFrame(sum((band_summary(df[df["normalized_race_class"].isin(filters[n] or LABELS)], "popularity", pop_bands, n) for n in ("ALL", "A_1plus", "B_2plus", "1勝_ONLY")), [])).to_csv(out/"race_class_popularity_summary.csv", index=False)
    monthly = []
    for name, labels in filters.items():
        part = df if labels is None else df[df["normalized_race_class"].isin(labels)]
        for month, group in part.groupby(part["date"].dt.to_period("M")):
            row = summary_row(name, group); row["month"] = str(month); monthly.append(row)
    pd.DataFrame(monthly).to_csv(out/"race_class_monthly_summary.csv", index=False)
    boot = []
    for name, labels in {"A_1plus": filters["A_1plus"], "B_2plus": filters["B_2plus"], "1勝_ONLY": ["1勝"]}.items():
        part = df[df["normalized_race_class"].isin(labels)]
        boot.append({"filter": name, **bootstrap(part)})
    a = selected_top1(df[df["normalized_race_class"].isin(filters["A_1plus"])]); b = selected_top1(df[df["normalized_race_class"].isin(filters["B_2plus"])])
    if not a.empty and not b.empty:
        rng = np.random.default_rng(42); diffs = []
        for _ in range(3000):
            ai = rng.integers(0, len(a), len(a)); bi = rng.integers(0, len(b), len(b))
            diffs.append(a.iloc[ai]["win_payout"].sum()/len(a) - b.iloc[bi]["win_payout"].sum()/len(b))
        boot.append({"filter": "A_minus_B_win_roi_difference", "estimate": betting(a)["win_roi"]-betting(b)["win_roi"], "ci_low": np.percentile(diffs, 2.5), "ci_high": np.percentile(diffs, 97.5)})
    pd.DataFrame(boot).to_csv(out/"race_class_ab_bootstrap.csv", index=False)
    one = df[df["normalized_race_class"] == "1勝"].copy(); one = one[one["prediction_rank"] == 1]
    one[["race_id", "date", "racecourse", "race_name", "normalized_race_class", "horse_name", "actual_rank", "predicted_probability", "prediction_rank", "odds", "popularity", "is_win", "win_payout", "is_place", "place_payout"]].to_csv(out/"race_class_ab_one_win_details.csv", index=False)
    unknown = int((class_races["normalized_race_class"] == "UNKNOWN").sum())
    crosswalk_text = validation.to_csv(index=False).strip()
    lines = ["# Race Class Filter Validation", "", f"Prediction source: `{args.predictions}`", f"Prediction rows: {len(df)}, races: {len(class_races)}", f"UNKNOWN: {unknown} races ({unknown/len(class_races):.2%})", "", "## Crosswalk", "", "```csv", crosswalk_text, "```", "", "Class labels are reconstructed from NL_RA_RACE JyokenName/RaceInfo and GradeCD. UNKNOWN is excluded from A/B and cumulative filters; no class is inferred from prize alone.", "", "## Anomaly review", "", "The prize crosswalk above is the audit surface. Large ranges reflect race-level prize variation and should be reviewed before operationalizing a prize threshold; no automatic relabeling was performed."]
    (out/"race_class_validation.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    ab = pd.DataFrame(rows).set_index("filter")
    def v(name, col):
        value = ab.loc[name, col]
        return "N/A" if pd.isna(value) else f"{value:.2f}" if isinstance(value, (float, np.floating)) else str(value)
    md = ["# Race Class Filter AB Test", "", "## 結論", "", "新馬・未勝利は購入対象外とし、同一モデルFの既存予測に対してA/Bフィルタだけを適用した。", "", "| 条件 | レース | 勝率 | 複勝率 | 単勝ROI | 複勝ROI |", "|---|---:|---:|---:|---:|---:|"]
    for name, title in (("A_1plus", "A: 1勝クラス以上"), ("B_2plus", "B: 2勝クラス以上"), ("1勝_ONLY", "1勝クラス単独")):
        md.append(f"| {title} | {v(name,'races')} | {v(name,'win_rate')} | {v(name,'place_rate')} | {v(name,'win_roi')}% | {v(name,'place_roi')}% |")
    md += ["", "## Detailed metrics", "", "```csv", ab.reset_index().to_csv(index=False).strip(), "```", "", "## Interpretation", "", "A/Bの採用判断はROI単独で決めず、1勝クラス単独の的中率、ML指標、オッズ、bootstrap CI、払戻上位除外ROI、月別結果を併読する。", "", "## Outputs", "", "- `race_class_ab_summary.csv`", "- `race_class_individual_summary.csv`", "- `race_class_cumulative_summary.csv`", "- `race_class_odds_band_summary.csv`", "- `race_class_popularity_summary.csv`", "- `race_class_monthly_summary.csv`", "- `race_class_ab_one_win_details.csv`", "- `race_class_ab_bootstrap.csv"]
    (out/"race_class_ab_summary.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    print(f"wrote race-class AB reports: races={len(class_races)}, unknown={unknown}, labels={class_counts.to_dict()}")


if __name__ == "__main__":
    main()

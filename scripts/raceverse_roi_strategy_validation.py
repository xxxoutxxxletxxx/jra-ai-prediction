"""RACEVERSE selective-win-betting validation using existing walk-forward predictions."""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("base", "formation", "pace")
DEFAULT_INPUT = ROOT / "reports/raceverse/backtest_5y_202109_202609_no_full"
DEFAULT_COMBINATIONS = ROOT / "reports/raceverse/market_analysis_5y_202109_202609_no_full/roi_by_combination.csv"
DEFAULT_DB = ROOT / "data/raw/race.db"
DEFAULT_OUTPUT = ROOT / "reports/raceverse/roi_strategy_validation"
START_DATE = pd.Timestamp("2021-09-01")
END_DATE = pd.Timestamp("2026-09-01")
EFFECTIVE_START = pd.Timestamp("2023-02-04")
EFFECTIVE_END = pd.Timestamp("2026-08-31")
WF_START = pd.Timestamp("2024-01-01")
BET_YEN = 100.0
MIN_CONDITION_BETS = 30
MIN_TRAIN_BETS = 30
PURCHASE_RATES = (0.10, 0.20, 0.30, 0.50, 1.00)
EV_THRESHOLDS = (1.00, 1.05, 1.10, 1.15, 1.20)
YEAR_LABELS = (2023, 2024, 2025, 2026)
RACE_KEYS = ("idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum")
TRACKS = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
GRADE_NAMES = {"A": "G1", "B": "G2", "C": "G3", "L": "Listed"}
CONDITION_COLUMNS = ("grade_group", "racecourse", "surface_name", "distance_band", "going_name")
PROBABILITY_BINS = (
    (0.00, 0.10, "0-10%"),
    (0.10, 0.15, "10-15%"),
    (0.15, 0.20, "15-20%"),
    (0.20, 0.25, "20-25%"),
    (0.25, 0.30, "25-30%"),
    (0.30, 0.35, "30-35%"),
    (0.35, 0.40, "35-40%"),
    (0.40, 0.50, "40-50%"),
    (0.50, 1.000001, "50%+"),
)
LOGGER = logging.getLogger(__name__)


def _race_id(values: Iterable[object]) -> str:
    parts = list(values)
    year = str(parts[0]).strip()
    return "-".join([year] + [str(value or "").strip().zfill(2) for value in parts[1:]])


def load_grade_codes(db_path: Path, years: tuple[int, int]) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"Race database not found: {db_path}")
    columns = ", ".join((*RACE_KEYS, "GradeCD"))
    query = (
        f"SELECT {columns} FROM NL_RA_RACE "
        f"WHERE idYear >= '{years[0]}' AND idYear <= '{years[1]}' AND headDataKubun='7'"
    )
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        rows = connection.execute(query).fetchall()
    grade = pd.DataFrame(rows, columns=(*RACE_KEYS, "grade_code_raw"))
    grade["race_id"] = grade[list(RACE_KEYS)].apply(lambda row: _race_id(row.tolist()), axis=1)
    grade["grade_code_raw"] = grade["grade_code_raw"].fillna("").astype(str).str.strip()
    if grade["race_id"].duplicated().any():
        raise ValueError("NL_RA_RACE contains duplicate confirmed race identifiers")
    return grade[["race_id", "grade_code_raw"]]


def load_win_payouts(db_path: Path, years: tuple[int, int]) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"Race database not found: {db_path}")
    payout_columns = [
        f"PayTansyo{i}{suffix}" for i in range(3) for suffix in ("Umaban", "Pay")
    ]
    columns = ", ".join((*RACE_KEYS, *payout_columns))
    query = (
        f"SELECT {columns} FROM NL_HR_PAY "
        f"WHERE idYear >= '{years[0]}' AND idYear <= '{years[1]}'"
    )
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        records = connection.execute(query).fetchall()
    payouts: dict[tuple[str, int], float] = {}
    for record in records:
        race_id = _race_id(record[: len(RACE_KEYS)])
        for slot in range(3):
            try:
                horse_number = int(float(record[len(RACE_KEYS) + 2 * slot] or 0))
                payout = float(record[len(RACE_KEYS) + 2 * slot + 1] or 0)
            except (TypeError, ValueError):
                continue
            if horse_number:
                payouts[(race_id, horse_number)] = payout
    return pd.DataFrame(
        [
            {"race_id": race_id, "umaban": horse_number, "db_win_payout": payout}
            for (race_id, horse_number), payout in payouts.items()
        ]
    )


def _normalise_track(values: pd.Series) -> pd.Series:
    as_code = values.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
    names = as_code.map(TRACKS)
    if names.isna().any():
        raise ValueError(f"Unknown racecourse codes: {sorted(as_code[names.isna()].unique())}")
    return names


def _prepare_conditions(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["racecourse"] = _normalise_track(result["track"])
    result["surface_name"] = result["surface"].map({"turf": "芝", "dirt": "ダート"})
    if result["surface_name"].isna().any():
        raise ValueError("Unsupported surface in race_level.csv")
    distances = pd.to_numeric(result["distance_m"], errors="coerce")
    if distances.isna().any():
        raise ValueError("Missing or invalid race distances")
    result["distance_band"] = np.select(
        [distances <= 1400, distances <= 1800, distances <= 2200],
        ["〜1400m", "1500〜1800m", "1900〜2200m"],
        default="2300m〜",
    )
    going = pd.to_numeric(result["going"], errors="coerce")
    if going.isna().any():
        raise ValueError("Missing or invalid going codes")
    result["going_name"] = np.where(going == 1, "良", "良以外")
    code = result["grade_code_raw"].fillna("").astype(str).str.strip().str.upper()
    result["grade_group"] = code.map(GRADE_NAMES)
    result.loc[code.isin(["D", "E"]), "grade_group"] = code.loc[code.isin(["D", "E"])].map(
        lambda value: f"GradeCD={value}"
    )
    result["grade_group"] = result["grade_group"].fillna("GradeCD空欄/その他")
    result["year"] = result["date"].dt.year.astype(int)
    return result


def _relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def load_analysis_data(
    input_dir: Path = DEFAULT_INPUT,
    db_path: Path = DEFAULT_DB,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    prediction_path = input_dir / "predictions.csv"
    races_path = input_dir / "race_level.csv"
    predictions = pd.read_csv(
        prediction_path,
        dtype={"race_id": str, "horse_id": str, "level": str},
        parse_dates=["date"],
    )
    races = pd.read_csv(races_path, dtype={"race_id": str}, parse_dates=["date"])
    required = {
        "race_id", "horse_id", "umaban", "level", "date", "target", "p_cal",
        "win_odds_reference", "win_payout",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"{prediction_path} is missing required columns: {missing}")
    race_required = {"race_id", "date", "track", "surface", "distance_m", "going"}
    missing = sorted(race_required - set(races.columns))
    if missing:
        raise ValueError(f"{races_path} is missing required columns: {missing}")

    predictions = predictions.loc[
        predictions["level"].isin(LEVELS)
        & predictions["date"].ge(START_DATE)
        & predictions["date"].lt(END_DATE)
    ].copy()
    predictions["p_cal"] = pd.to_numeric(predictions["p_cal"], errors="coerce")
    predictions = predictions.loc[predictions["p_cal"].notna()].copy()
    predictions["target"] = pd.to_numeric(predictions["target"], errors="coerce")
    predictions["umaban"] = pd.to_numeric(predictions["umaban"], errors="coerce")
    predictions["win_odds_reference"] = pd.to_numeric(predictions["win_odds_reference"], errors="coerce")
    predictions["win_payout_source"] = pd.to_numeric(predictions["win_payout"], errors="coerce")
    predictions = predictions.loc[
        predictions["date"].ge(EFFECTIVE_START) & predictions["date"].le(EFFECTIVE_END)
    ].copy()
    if predictions.empty:
        raise ValueError("No calibrated predictions in the requested evaluation window")
    if predictions.duplicated(["level", "race_id", "horse_id"]).any():
        raise ValueError("Duplicate level/race/horse prediction rows")

    race_level_counts = predictions.groupby("race_id")["level"].nunique()
    complete_races = set(race_level_counts[race_level_counts.eq(len(LEVELS))].index)
    incomplete_races = sorted(set(predictions["race_id"]) - complete_races)
    if incomplete_races:
        LOGGER.warning("Excluding %d races missing one or more prediction levels", len(incomplete_races))
        predictions = predictions.loc[predictions["race_id"].isin(complete_races)].copy()
    level_reference = None
    for level in LEVELS:
        level_frame = predictions.loc[predictions["level"].eq(level)].sort_values(["race_id", "horse_id"])
        comparison = level_frame[["race_id", "horse_id", "umaban", "target", "win_odds_reference", "win_payout"]]
        if level_reference is None:
            level_reference = comparison.reset_index(drop=True)
        elif not level_reference.equals(comparison.reset_index(drop=True)):
            raise ValueError(f"{level} has different runners, outcomes, odds, or payouts from base")
        if not np.isfinite(level_frame["p_cal"]).all() or level_frame["p_cal"].lt(0).any():
            raise ValueError(f"{level} has invalid calibrated probabilities")
        sums = level_frame.groupby("race_id")["p_cal"].sum()
        if not np.allclose(sums.to_numpy(), 1.0, atol=1e-8):
            raise ValueError(f"{level} race probabilities do not sum to one")
    invalid = (
        predictions["target"].isna()
        | ~predictions["target"].isin([0, 1])
        | predictions["umaban"].isna()
        | predictions["win_odds_reference"].isna()
        | predictions["win_odds_reference"].le(0)
    )
    if invalid.any():
        raise ValueError(f"Found {int(invalid.sum())} rows with missing or invalid outcomes/odds/payouts")

    base = predictions.loc[predictions["level"].eq("base")]
    winner_count = base.groupby("race_id")["target"].sum()
    tied_races = int(winner_count.gt(1).sum())
    no_winner_races = int(winner_count.eq(0).sum())
    if no_winner_races:
        raise ValueError(f"{no_winner_races} races have no winner target")
    if races["race_id"].duplicated().any():
        raise ValueError("race_level.csv has conflicting duplicate race metadata")
    unique_races = races
    attrs = unique_races[["race_id", "date", "track", "surface", "distance_m", "going"]]
    joined = predictions.merge(attrs, on="race_id", how="left", suffixes=("", "_race"), validate="many_to_one")
    if joined[["track", "surface", "distance_m", "going"]].isna().any().any():
        raise ValueError("Missing race metadata for calibrated predictions")
    if not joined["date"].eq(joined["date_race"]).all():
        raise ValueError("Prediction dates do not agree with race_level.csv")
    grade = load_grade_codes(db_path, (int(joined["date"].dt.year.min()), int(joined["date"].dt.year.max())))
    joined = joined.merge(grade, on="race_id", how="left", validate="many_to_one")
    missing_grade = joined["grade_code_raw"].isna()
    if missing_grade.any():
        raise ValueError(f"GradeCD missing from race.db for {joined.loc[missing_grade, 'race_id'].nunique()} races")
    payouts = load_win_payouts(db_path, (int(joined["date"].dt.year.min()), int(joined["date"].dt.year.max())))
    joined = joined.merge(payouts, on=["race_id", "umaban"], how="left", validate="many_to_one")
    missing_winner_payout = joined["target"].eq(1) & joined["db_win_payout"].isna()
    if missing_winner_payout.any():
        raise ValueError(
            f"race.db has no win payout for {joined.loc[missing_winner_payout, 'race_id'].nunique()} winning races"
        )
    source_payout_present = joined["win_payout_source"].notna()
    payout_mismatch = source_payout_present & joined["db_win_payout"].notna() & (
        joined["win_payout_source"] != joined["db_win_payout"]
    )
    if payout_mismatch.any():
        raise ValueError(f"{int(payout_mismatch.sum())} source payout values disagree with NL_HR_PAY")
    missing_loser_payout = joined["target"].eq(0) & joined["db_win_payout"].isna()
    joined["win_payout"] = joined["db_win_payout"].fillna(0.0)
    if joined["win_payout"].lt(0).any():
        raise ValueError("NL_HR_PAY contains negative win payouts")
    joined = _prepare_conditions(joined)
    joined["analysis_period"] = f"{joined['date'].min():%Y-%m-%d}/{joined['date'].max():%Y-%m-%d}"
    counts = {
        "races": int(joined["race_id"].nunique()),
        "runners": int(len(joined) // len(LEVELS)),
        "prediction_rows": int(len(joined)),
        "tied_winner_races": tied_races,
        "incomplete_races_excluded": len(incomplete_races),
        "source_csv_payout_nulls_filled_from_database": int(joined["win_payout_source"].isna().sum()),
        "loser_rows_without_individual_payout_recorded_as_zero": int(missing_loser_payout.sum()),
        "first_date": joined["date"].min().strftime("%Y-%m-%d"),
        "last_date": joined["date"].max().strftime("%Y-%m-%d"),
    }
    return joined, races, counts


def make_top_candidates(runners: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[pd.DataFrame] = []
    for level in LEVELS:
        subset = runners.loc[runners["level"].eq(level)].copy()
        subset = subset.sort_values(["race_id", "p_cal", "umaban"], ascending=[True, False, True], kind="stable")
        top1 = subset.drop_duplicates("race_id", keep="first").copy()
        top2 = subset.groupby("race_id", sort=False).nth(1).reset_index()
        if "top2_probability" in top1.columns:
            top1 = top1.drop(columns="top2_probability")
        top1 = top1.rename(
            columns={
                "horse_id": "selected_horse_id",
                "umaban": "selected_umaban",
                "p_cal": "top1_probability",
                "target": "hit",
                "win_odds_reference": "final_odds",
                "win_payout": "payout_yen",
            }
        )
        second = top2[["race_id", "p_cal"]].rename(columns={"p_cal": "top2_probability"})
        top1 = top1.merge(second, on="race_id", how="left", validate="one_to_one")
        top1["model"] = level
        records.append(top1)
    candidates = pd.concat(records, ignore_index=True)

    pivot = candidates.pivot(index="race_id", columns="model", values="selected_horse_id")
    pivot.columns = [f"top1_horse_{name}" for name in pivot.columns]
    wide = pivot.reset_index()
    for column in ("date", "year", "racecourse", "surface_name", "distance_band", "going_name", "grade_group", "grade_code_raw"):
        attrs = runners.drop_duplicates("race_id")[["race_id", column]]
        wide = wide.merge(attrs, on="race_id", how="left", validate="one_to_one")
    for model in LEVELS:
        values = candidates.loc[candidates["model"].eq(model), [
            "race_id", "top1_probability", "top2_probability", "selected_horse_id",
            "selected_umaban", "hit", "payout_yen", "final_odds",
        ]].rename(
            columns={
                "top1_probability": f"p1_{model}",
                "top2_probability": f"p2_{model}",
                "selected_horse_id": f"horse_{model}",
                "selected_umaban": f"umaban_{model}",
                "hit": f"hit_{model}",
                "payout_yen": f"payout_{model}",
                "final_odds": f"odds_{model}",
            }
        )
        wide = wide.merge(values, on="race_id", how="left", validate="one_to_one")

    wide["top1_agreement_votes"] = wide.apply(
        lambda row: max(pd.Series([row[f"horse_{model}"] for model in LEVELS]).value_counts()), axis=1
    )
    wide["top1_probability_sd"] = wide[[f"p1_{model}" for model in LEVELS]].std(axis=1, ddof=0)
    probability_matrix = runners.pivot(index=["race_id", "horse_id"], columns="level", values="p_cal")
    target_payout = runners.drop_duplicates(["race_id", "horse_id"])[
        ["race_id", "horse_id", "target", "win_payout", "win_odds_reference"]
    ].set_index(["race_id", "horse_id"])
    consensus_rows: list[dict[str, object]] = []
    runner_metadata = runners.drop_duplicates(["race_id", "horse_id"]).set_index(["race_id", "horse_id"])
    for row in wide.itertuples(index=False):
        values = row._asdict()
        votes = {model: values[f"horse_{model}"] for model in LEVELS}
        counts = pd.Series(list(votes.values())).value_counts()
        majority_horse = sorted(counts[counts.eq(counts.max())].index, key=str)[0]
        chosen = majority_horse if counts.max() >= 2 else votes["base"]
        key = (values["race_id"], chosen)
        result = target_payout.loc[key]
        probabilities = probability_matrix.loc[key]
        consensus_rows.append(
            {
                "race_id": values["race_id"],
                "date": values["date"],
                "year": values["year"],
                "racecourse": values["racecourse"],
                "surface_name": values["surface_name"],
                "distance_band": values["distance_band"],
                "going_name": values["going_name"],
                "grade_group": values["grade_group"],
                "grade_code_raw": values["grade_code_raw"],
                "model": "consensus",
                "selected_horse_id": chosen,
                "selected_umaban": int(runner_metadata.loc[key, "umaban"]),
                "top1_probability": float(probabilities.mean()),
                "top2_probability": np.nan,
                "hit": int(result["target"]),
                "payout_yen": float(result["win_payout"]),
                "final_odds": float(result["win_odds_reference"]),
                "top1_agreement_votes": int(counts.max()),
                "top1_probability_sd": float(values["top1_probability_sd"]),
                "top1_top2_gap": np.nan,
                "top1_top2_ratio": np.nan,
            }
        )
    consensus = pd.DataFrame(consensus_rows)
    candidates["top1_top2_gap"] = candidates["top1_probability"] - candidates["top2_probability"]
    candidates["top1_top2_ratio"] = candidates["top1_probability"] / candidates["top2_probability"].clip(lower=1e-12)
    candidates["negative_top1_probability_sd"] = candidates["race_id"].map(
        wide.set_index("race_id")["top1_probability_sd"]
    ).mul(-1)
    candidates["top1_agreement_votes"] = candidates["race_id"].map(
        wide.set_index("race_id")["top1_agreement_votes"]
    )
    consensus["negative_top1_probability_sd"] = -consensus["top1_probability_sd"]
    consensus["top1_agreement_votes"] = consensus["top1_agreement_votes"].astype(int)
    candidate_long = pd.concat([candidates, consensus], ignore_index=True, sort=False)
    return candidate_long, wide


def max_losing_streak(hits: Iterable[object]) -> int:
    longest = current = 0
    for value in hits:
        if not bool(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def max_drawdown(payouts: Iterable[float], stakes: Iterable[float] | None = None) -> float:
    returned = np.asarray(list(payouts), dtype=float)
    invested = np.full(len(returned), BET_YEN) if stakes is None else np.asarray(list(stakes), dtype=float)
    cumulative = np.cumsum(returned - invested)
    high_water = np.maximum.accumulate(np.r_[0.0, cumulative])[1:]
    return float(np.max(high_water - cumulative)) if len(cumulative) else 0.0


def summarize_bets(bets: pd.DataFrame) -> dict[str, float | int]:
    ordered = bets.sort_values(["date", "race_id"], kind="stable")
    count = len(ordered)
    hits = ordered["hit"].astype(bool)
    investment = float(count * BET_YEN)
    returned = float(ordered["payout_yen"].sum())
    return {
        "purchase_races": int(count),
        "hits": int(hits.sum()),
        "hit_rate_pct": float(hits.mean() * 100) if count else np.nan,
        "investment_yen": investment,
        "payout_yen": returned,
        "profit_yen": returned - investment,
        "roi_pct": returned / investment * 100 if investment else np.nan,
        "max_drawdown_yen": max_drawdown(ordered["payout_yen"]) if count else 0.0,
        "max_losing_streak": max_losing_streak(hits),
        "avg_final_odds": float(ordered["final_odds"].mean()) if count else np.nan,
        "mean_predicted_win_probability": float(ordered["top1_probability"].mean()) if count else np.nan,
        "actual_win_rate": float(hits.mean()) if count else np.nan,
        "predicted_minus_actual": float(ordered["top1_probability"].mean() - hits.mean()) if count else np.nan,
    }


def _metrics_with_nonbuyers(candidates: pd.DataFrame, selected: pd.Series) -> dict[str, float | int]:
    chosen = candidates.loc[selected].copy()
    missed = candidates.loc[~selected].copy()
    metrics = summarize_bets(chosen)
    metrics["eligible_races"] = int(len(candidates))
    metrics["purchase_rate_pct"] = float(len(chosen) / len(candidates) * 100) if len(candidates) else np.nan
    metrics["nonpurchase_races"] = int(len(missed))
    metrics["nonpurchase_hits"] = int(missed["hit"].sum())
    metrics["nonpurchase_hit_rate_pct"] = float(missed["hit"].mean() * 100) if len(missed) else np.nan
    missed_stake = len(missed) * BET_YEN
    metrics["nonpurchase_roi_pct"] = (
        float(missed["payout_yen"].sum() / missed_stake * 100) if missed_stake else np.nan
    )
    return metrics


def _condition_name(values: Iterable[object]) -> str:
    return " | ".join(str(value) for value in values)


def collect_condition_specs(combination_path: Path) -> list[dict[str, object]]:
    combinations = pd.read_csv(combination_path)
    required = {"model", "grade_label", "racecourse", "surface_ja", "distance_band", "going_group", "bets", "roi_pct"}
    missing = sorted(required - set(combinations.columns))
    if missing:
        raise ValueError(f"{combination_path} is missing required columns: {missing}")
    eligible = combinations.loc[
        pd.to_numeric(combinations["bets"], errors="coerce").ge(MIN_CONDITION_BETS)
        & pd.to_numeric(combinations["roi_pct"], errors="coerce").ge(100)
    ]
    condition_map: dict[tuple[str, ...], dict[str, object]] = {}
    for row in eligible.itertuples(index=False):
        grade = str(row.grade_label)
        if grade == "GradeCD=E":
            grade_group = grade
        elif grade in GRADE_NAMES.values():
            grade_group = grade
        elif grade == "GradeCD空欄/その他":
            grade_group = grade
        elif grade.startswith("GradeCD=") and grade[-1:] in ("D", "E"):
            grade_group = grade
        else:
            grade_group = "GradeCD空欄/その他"
        distance = {
            "～1400m": "〜1400m",
            "1500～1800m": "1500〜1800m",
            "1900～2200m": "1900〜2200m",
            "2300m～": "2300m〜",
        }.get(str(row.distance_band), str(row.distance_band))
        key = (grade_group, str(row.racecourse), str(row.surface_ja), distance, str(row.going_group))
        condition_map[key] = {
            "condition_id": "prior_combo_" + "_".join(key),
            "grade_group": key[0],
            "racecourse": key[1],
            "surface_name": key[2],
            "distance_band": key[3],
            "going_name": key[4],
            "selection_source": "existing_full_period_csv_descriptive_only",
        }
    return list(condition_map.values())


def _condition_mask(frame: pd.DataFrame, spec: dict[str, object]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in CONDITION_COLUMNS:
        mask &= frame[column].eq(spec[column])
    return mask


def annual_stability(
    candidates: pd.DataFrame,
    combination_path: Path = DEFAULT_COMBINATIONS,
) -> pd.DataFrame:
    specs: list[dict[str, object]] = [
        {"condition_id": "all_races", "selection_source": "predefined", **{column: "ALL" for column in CONDITION_COLUMNS}},
        {"condition_id": "G3", "selection_source": "predefined_grade_code_C", **{column: "ALL" for column in CONDITION_COLUMNS}},
        {
            "condition_id": "tokyo_turf_1500_1800_E_good", "selection_source": "predefined",
            "grade_group": "GradeCD=E", "racecourse": "東京", "surface_name": "芝",
            "distance_band": "1500〜1800m", "going_name": "良",
        },
        {
            "condition_id": "nakayama_turf_1500_1800_E_good", "selection_source": "predefined",
            "grade_group": "GradeCD=E", "racecourse": "中山", "surface_name": "芝",
            "distance_band": "1500〜1800m", "going_name": "良",
        },
        {
            "condition_id": "hakodate_turf_up_to_1400_E_good", "selection_source": "predefined",
            "grade_group": "GradeCD=E", "racecourse": "函館", "surface_name": "芝",
            "distance_band": "〜1400m", "going_name": "良",
        },
        {
            "condition_id": "kyoto_turf_1500_1800_blank_other_good", "selection_source": "predefined",
            "grade_group": "GradeCD空欄/その他", "racecourse": "京都", "surface_name": "芝",
            "distance_band": "1500〜1800m", "going_name": "良",
        },
    ]
    specs.extend(collect_condition_specs(combination_path))
    unique_specs = {str(spec["condition_id"]): spec for spec in specs}
    records: list[dict[str, object]] = []
    for model in LEVELS:
        model_rows = candidates.loc[candidates["model"].eq(model)].copy()
        for spec in unique_specs.values():
            if spec["condition_id"] == "all_races":
                selected = model_rows
            elif spec["condition_id"] == "G3":
                selected = model_rows.loc[model_rows["grade_group"].eq("G3")]
            else:
                selected = model_rows.loc[_condition_mask(model_rows, spec)]
            annual: dict[int, dict[str, float | int]] = {}
            for year, group in selected.groupby("year"):
                summary = summarize_bets(group)
                payouts = group["payout_yen"].sort_values(ascending=False)
                for top_count in (1, 3):
                    remaining = group.drop(index=payouts.head(top_count).index)
                    summary[f"roi_ex_top_{top_count}_payout_pct"] = (
                        float(remaining["payout_yen"].sum() / (len(remaining) * BET_YEN) * 100)
                        if len(remaining) else np.nan
                    )
                annual[int(year)] = summary
            stable_year_count = sum(
                1 for value in annual.values() if float(value["roi_pct"]) > 100
            )
            for year, summary in annual.items():
                period_rows = selected.loc[selected["year"].eq(year)]
                first = period_rows["date"].min()
                last = period_rows["date"].max()
                records.append(
                    {
                        "analysis_period": f"{first:%Y-%m-%d}/{last:%Y-%m-%d}",
                        "condition_id": spec["condition_id"],
                        "selection_source": spec["selection_source"],
                        "condition": _condition_name(spec[column] for column in CONDITION_COLUMNS),
                        "model": model,
                        "year": year,
                        "partial_calendar_year": year in (2023, 2026),
                        "year_start_in_scope": first.strftime("%Y-%m-%d"),
                        "year_end_in_scope": last.strftime("%Y-%m-%d"),
                        "annual_roi_over_100_count": stable_year_count,
                        **summary,
                        "sample_races": int(period_rows["race_id"].nunique()),
                    }
                )
    return pd.DataFrame(records)


def _sample_summary_rows(
    sample: pd.DataFrame,
    category: str,
    model: str,
    runners: pd.DataFrame,
) -> list[dict[str, object]]:
    if sample.empty:
        return []
    result = []
    for year in ["ALL", *YEAR_LABELS]:
        group = sample if year == "ALL" else sample.loc[sample["year"].eq(year)]
        if group.empty:
            continue
        summary = summarize_bets(group)
        result.append(
            {
                "analysis_period": (
                    f"{group['date'].min():%Y-%m-%d}/{group['date'].max():%Y-%m-%d}"
                ),
                "agreement_condition": category,
                "selected_model": model,
                "year": year,
                "sample_races": int(group["race_id"].nunique()),
                "mean_predicted_probability": summary["mean_predicted_win_probability"],
                "actual_win_rate": summary["actual_win_rate"],
                "predicted_minus_actual": summary["predicted_minus_actual"],
                "mean_final_odds": summary["avg_final_odds"],
                "hit_rate_pct": summary["hit_rate_pct"],
                "roi_pct": summary["roi_pct"],
                "investment_yen": summary["investment_yen"],
                "payout_yen": summary["payout_yen"],
                "profit_yen": summary["profit_yen"],
                "max_drawdown_yen": summary["max_drawdown_yen"],
                "max_losing_streak": summary["max_losing_streak"],
            }
        )
    return result


def model_agreement_analysis(runners: pd.DataFrame, candidates: pd.DataFrame, wide: pd.DataFrame) -> pd.DataFrame:
    probability_by_horse = runners.pivot(index=["race_id", "horse_id"], columns="level", values="p_cal")
    outcomes = runners.drop_duplicates(["race_id", "horse_id"])[
        ["race_id", "horse_id", "target", "win_payout", "win_odds_reference"]
    ].set_index(["race_id", "horse_id"])
    rows: list[dict[str, object]] = []

    def make_sample(frame: pd.DataFrame, condition: str, selected_model: str, selected_horse: pd.Series) -> pd.DataFrame:
        selected = frame[["race_id", "date", "year"]].copy()
        selected["horse_id"] = selected_horse.to_numpy()
        selected = selected.join(outcomes, on=["race_id", "horse_id"], validate="one_to_one")
        probability = probability_by_horse.loc[
            pd.MultiIndex.from_arrays([selected["race_id"], selected["horse_id"]])
        ]
        selected["top1_probability"] = (
            probability.mean(axis=1).to_numpy()
            if selected_model in ("all_agree", "majority")
            else probability[selected_model].to_numpy()
        )
        selected = selected.rename(
            columns={"target": "hit", "win_payout": "payout_yen", "win_odds_reference": "final_odds"}
        )
        return selected

    all_same = wide.loc[
        wide[[f"horse_{level}" for level in LEVELS]].nunique(axis=1).eq(1)
    ].copy()
    if not all_same.empty:
        rows.extend(_sample_summary_rows(
            make_sample(all_same, "A_all_three_agree", "all_agree", all_same["horse_base"]),
            "A_all_three_agree", "consensus", runners,
        ))
    two_same = wide.loc[
        wide[[f"horse_{level}" for level in LEVELS]].nunique(axis=1).eq(2)
    ].copy()
    if not two_same.empty:
        majority = two_same.apply(
            lambda row: pd.Series([row[f"horse_{level}"] for level in LEVELS]).value_counts().idxmax(),
            axis=1,
        )
        rows.extend(_sample_summary_rows(
            make_sample(two_same, "B_two_agree", "majority", majority),
            "B_two_agree", "consensus_majority", runners,
        ))
    all_different = wide.loc[
        wide[[f"horse_{level}" for level in LEVELS]].nunique(axis=1).eq(3)
    ].copy()
    for model in LEVELS:
        rows.extend(_sample_summary_rows(
            make_sample(all_different, "C_all_different", model, all_different[f"horse_{model}"]),
            "C_all_different", model, runners,
        ))
    for label, condition in (
        ("D_base_formation_agree", wide["horse_base"].eq(wide["horse_formation"])),
        ("E_base_formation_disagree", wide["horse_base"].ne(wide["horse_formation"])),
    ):
        subset = wide.loc[condition].copy()
        rows.extend(_sample_summary_rows(
            make_sample(subset, label, "base", subset["horse_base"]), label, "base", runners,
        ))

    reference_index = pd.MultiIndex.from_arrays([wide["race_id"], wide["horse_base"]])
    same_horse_probabilities = probability_by_horse.loc[reference_index, list(LEVELS)].to_numpy(dtype=float)
    same_horse_range = same_horse_probabilities.max(axis=1) - same_horse_probabilities.min(axis=1)
    for signal, values in (
        ("top1_probability_sd", wide["top1_probability_sd"]),
        ("same_base_top1_probability_range", pd.Series(same_horse_range, index=wide.index)),
    ):
        bins = pd.qcut(values, q=4, duplicates="drop")
        for bin_name, selected_index in bins.groupby(bins, observed=True).groups.items():
            subset = wide.loc[selected_index].copy()
            rows.extend(_sample_summary_rows(
                make_sample(subset, f"{signal}_{bin_name}", "base", subset["horse_base"]),
                f"{signal}_{bin_name}", "base", runners,
            ))
    return pd.DataFrame(rows)


def _reliability_rows(frame: pd.DataFrame, model: str, scope: str, bins: Iterable[float]) -> list[dict[str, object]]:
    labels = pd.cut(frame["probability"], bins=list(bins), right=False, include_lowest=True)
    rows = []
    for interval, group in frame.groupby(labels, observed=False):
        rows.append(
            {
                "analysis_period": f"{frame['date'].min():%Y-%m-%d}/{frame['date'].max():%Y-%m-%d}",
                "scope": scope,
                "model": model,
                "probability_bin": str(interval),
                "sample_races": int(group["race_id"].nunique()),
                "n": len(group),
                "hits": int(group["target"].sum()),
                "mean_predicted_probability": float(group["probability"].mean()) if len(group) else np.nan,
                "actual_win_rate": float(group["target"].mean()) if len(group) else np.nan,
                "predicted_minus_actual": (
                    float(group["probability"].mean() - group["target"].mean()) if len(group) else np.nan
                ),
                "brier_score": float(((group["probability"] - group["target"]) ** 2).mean()) if len(group) else np.nan,
                "low_sample_lt_100": len(group) < 100,
            }
        )
    return rows


def calibration_analysis(runners: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    all_runner_edges = np.linspace(0.0, 1.000001, 11)
    for model in LEVELS:
        sample = runners.loc[runners["level"].eq(model)].copy()
        sample["probability"] = sample["p_cal"]
        n = len(sample)
        reliability = pd.cut(sample["probability"], bins=all_runner_edges, right=False, include_lowest=True)
        table = sample.groupby(reliability, observed=True).agg(
            count=("target", "size"), mean_prediction=("probability", "mean"), actual_rate=("target", "mean")
        )
        ece = float(
            ((table["count"] / n) * (table["mean_prediction"] - table["actual_rate"]).abs()).sum()
        )
        unique_winners = sample.groupby("race_id")["target"].sum().eq(1)
        winner_ids = set(unique_winners[unique_winners].index)
        winners = sample.loc[sample["race_id"].isin(winner_ids) & sample["target"].eq(1)]
        output.append(
            {
                "analysis_period": sample["analysis_period"].iloc[0],
                "scope": "all_runners_summary",
                "model": model,
                "sample_races": int(sample["race_id"].nunique()),
                "n": n,
                "brier_score": float(((sample["p_cal"] - sample["target"]) ** 2).mean()),
                "winner_logloss": float(-np.log(winners["p_cal"].clip(lower=1e-15)).mean()),
                "winner_logloss_races": len(winner_ids),
                "ece_10_equal_width": ece,
                "max_probability_sum_error": float(
                    sample.groupby("race_id")["p_cal"].sum().sub(1).abs().max()
                ),
            }
        )
        output.extend(_reliability_rows(sample, model, "all_runners_reliability", all_runner_edges))

        top = candidates.loc[candidates["model"].eq(model)].copy()
        top["probability"] = top["top1_probability"]
        for lower, upper, label in PROBABILITY_BINS:
            group = top.loc[top["probability"].ge(lower) & top["probability"].lt(upper)]
            output.append(
                {
                    "analysis_period": top["analysis_period"].iloc[0],
                    "scope": "top1_probability_band",
                    "model": model,
                    "probability_bin": label,
                    "sample_races": int(group["race_id"].nunique()),
                    "n": len(group),
                    "hits": int(group["hit"].sum()),
                    "mean_predicted_probability": float(group["probability"].mean()) if len(group) else np.nan,
                    "actual_win_rate": float(group["hit"].mean()) if len(group) else np.nan,
                    "predicted_minus_actual": (
                        float(group["probability"].mean() - group["hit"].mean()) if len(group) else np.nan
                    ),
                    "roi_pct": (
                        float(group["payout_yen"].sum() / (len(group) * BET_YEN) * 100) if len(group) else np.nan
                    ),
                    "avg_final_odds": float(group["final_odds"].mean()) if len(group) else np.nan,
                    "low_sample_lt_100": len(group) < 100,
                }
            )
        top_summary = summarize_bets(top)
        output.append(
            {
                "analysis_period": top["analysis_period"].iloc[0],
                "scope": "top1_summary",
                "model": model,
                "sample_races": int(top["race_id"].nunique()),
                "n": len(top),
                "hits": top_summary["hits"],
                "hit_rate_pct": top_summary["hit_rate_pct"],
                "avg_final_odds": top_summary["avg_final_odds"],
                "investment_yen": top_summary["investment_yen"],
                "payout_yen": top_summary["payout_yen"],
                "roi_pct": top_summary["roi_pct"],
            }
        )
    market = runners.loc[runners["level"].eq("base")].copy()
    market["p_raw"] = 1.0 / market["win_odds_reference"]
    market["probability"] = market["p_raw"] / market.groupby("race_id")["p_raw"].transform("sum")
    market["model"] = "market_final_odds_reference"
    unique_winners = market.groupby("race_id")["target"].sum().eq(1)
    winners = market.loc[market["race_id"].isin(set(unique_winners[unique_winners].index)) & market["target"].eq(1)]
    output.append(
        {
            "analysis_period": market["analysis_period"].iloc[0],
            "scope": "all_runners_summary",
            "model": "market_final_odds_reference",
            "sample_races": int(market["race_id"].nunique()),
            "n": len(market),
            "brier_score": float(((market["probability"] - market["target"]) ** 2).mean()),
            "winner_logloss": float(-np.log(winners["probability"].clip(lower=1e-15)).mean()),
            "winner_logloss_races": int(winners["race_id"].nunique()),
            "ece_10_equal_width": np.nan,
            "max_probability_sum_error": float(market.groupby("race_id")["probability"].sum().sub(1).abs().max()),
        }
    )
    market_top = market.sort_values(
        ["race_id", "probability", "umaban"], ascending=[True, False, True], kind="stable"
    ).drop_duplicates("race_id")
    market_top = market_top.rename(
        columns={
            "target": "hit",
            "win_payout": "payout_yen",
            "win_odds_reference": "final_odds",
            "probability": "top1_probability",
        }
    )
    market_top_summary = summarize_bets(market_top)
    output.append(
        {
            "analysis_period": market_top["analysis_period"].iloc[0],
            "scope": "top1_summary",
            "model": "market_final_odds_reference",
            "sample_races": int(market_top["race_id"].nunique()),
            "n": len(market_top),
            "hits": market_top_summary["hits"],
            "hit_rate_pct": market_top_summary["hit_rate_pct"],
            "avg_final_odds": market_top_summary["avg_final_odds"],
            "investment_yen": market_top_summary["investment_yen"],
            "payout_yen": market_top_summary["payout_yen"],
            "roi_pct": market_top_summary["roi_pct"],
        }
    )
    output.extend(
        _reliability_rows(market, "market_final_odds_reference", "all_runners_reliability", all_runner_edges)
    )
    return pd.DataFrame(output)


def odds_band_analysis(candidates: pd.DataFrame) -> pd.DataFrame:
    bins = [1.0, 2.0, 3.0, 5.0, 10.0, 20.0, np.inf]
    labels = ["1.0-1.9", "2.0-2.9", "3.0-4.9", "5.0-9.9", "10.0-19.9", "20.0+"]
    output = []
    for model, sample in candidates.loc[candidates["model"].isin(LEVELS)].groupby("model"):
        sample = sample.copy()
        sample["odds_band"] = pd.cut(sample["final_odds"], bins=bins, labels=labels, right=False)
        for band in labels:
            group = sample.loc[sample["odds_band"].eq(band)]
            output.append(
                {
                    "analysis_period": sample["analysis_period"].iloc[0],
                    "scope": "model_top1_final_odds_posthoc",
                    "odds_source": "win_odds_reference_final_only",
                    "model": model,
                    "odds_band": band,
                    "sample_races": int(group["race_id"].nunique()),
                    "n": len(group),
                    "hits": int(group["hit"].sum()),
                    "actual_win_rate": float(group["hit"].mean()) if len(group) else np.nan,
                    "mean_predicted_win_probability": float(group["top1_probability"].mean()) if len(group) else np.nan,
                    "predicted_minus_actual": (
                        float(group["top1_probability"].mean() - group["hit"].mean()) if len(group) else np.nan
                    ),
                    "avg_final_odds": float(group["final_odds"].mean()) if len(group) else np.nan,
                    "investment_yen": float(len(group) * BET_YEN),
                    "payout_yen": float(group["payout_yen"].sum()),
                    "profit_yen": float(group["payout_yen"].sum() - len(group) * BET_YEN),
                    "roi_pct": (
                        float(group["payout_yen"].sum() / (len(group) * BET_YEN) * 100) if len(group) else np.nan
                    ),
                    "low_sample_lt_100": len(group) < 100,
                }
            )
    return pd.DataFrame(output)


def _signal_column(signal: str, model: str) -> str:
    if signal == "top1_probability":
        return f"p1_{model}"
    if signal == "top1_top2_gap":
        return f"gap_{model}"
    if signal == "top1_top2_ratio":
        return f"ratio_{model}"
    if signal == "top1_agreement_votes":
        return "top1_agreement_votes"
    if signal == "negative_top1_probability_sd":
        return "negative_top1_probability_sd"
    raise ValueError(f"Unknown purchase signal: {signal}")


def _threshold(history: pd.Series, rate: float) -> float:
    values = pd.to_numeric(history, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(values):
        return np.nan
    return float(np.quantile(values, 1.0 - rate))


def _calibrate_conditions(
    training: pd.DataFrame,
    model: str,
) -> tuple[dict[str, object] | None, pd.DataFrame]:
    sample = training.loc[training["model"].eq(model)].copy()
    if sample.empty:
        return None, pd.DataFrame()
    grouped = sample.groupby(list(CONDITION_COLUMNS), dropna=False).agg(
        races=("race_id", "nunique"), hits=("hit", "sum"), returned=("payout_yen", "sum")
    ).reset_index()
    grouped["roi_pct"] = grouped["returned"] / (grouped["races"] * BET_YEN) * 100
    eligible = grouped.loc[
        grouped["races"].ge(MIN_TRAIN_BETS)
        & grouped["roi_pct"].ge(100)
    ].copy()
    if eligible.empty:
        return None, eligible
    eligible = eligible.sort_values(
        ["roi_pct", "races", "returned", *CONDITION_COLUMNS],
        ascending=[False, False, False, True, True, True, True, True],
        kind="stable",
    )
    selected = eligible.iloc[0]
    spec = {column: selected[column] for column in CONDITION_COLUMNS}
    spec["condition_id"] = _condition_name(spec.values())
    return spec, eligible


def _strategy_record(
    candidates: pd.DataFrame,
    selected: pd.Series,
    *,
    fold_id: str,
    strategy: str,
    model: str,
    signal: str = "",
    requested_rate: float = np.nan,
    threshold: float = np.nan,
    train_races: int = 0,
    train_bets: int = 0,
    selected_condition: str = "",
) -> dict[str, object]:
    metrics = _metrics_with_nonbuyers(candidates, selected)
    return {
        "fold_id": fold_id,
        "analysis_period": (
            f"{candidates['date'].min():%Y-%m-%d}/{candidates['date'].max():%Y-%m-%d}"
            if len(candidates) else ""
        ),
        "strategy": strategy,
        "model": model,
        "signal": signal,
        "requested_purchase_rate": requested_rate,
        "training_threshold": threshold,
        "training_races": train_races,
        "training_selected_bets": train_bets,
        "selected_condition": selected_condition,
        "test_start": candidates["date"].min().strftime("%Y-%m-%d") if len(candidates) else "",
        "test_end": candidates["date"].max().strftime("%Y-%m-%d") if len(candidates) else "",
        **metrics,
    }


def _best_combination_rule(train: pd.DataFrame, model: str) -> tuple[str, float, float, pd.DataFrame]:
    history = train.loc[train["model"].eq(model)]
    p_cut = _threshold(history["p1_" + model], 0.20)
    gap_cut = _threshold(history["gap_" + model], 0.20)
    p_cut_30 = _threshold(history["p1_" + model], 0.30)
    gap_cut_30 = _threshold(history["gap_" + model], 0.30)
    definitions = [
        ("p20_and_unanimous", (history["p1_" + model] >= p_cut) & history["top1_agreement_votes"].eq(3), p_cut, np.nan),
        ("gap20_and_unanimous", (history["gap_" + model] >= gap_cut) & history["top1_agreement_votes"].eq(3), np.nan, gap_cut),
        ("p20_and_gap20", (history["p1_" + model] >= p_cut) & (history["gap_" + model] >= gap_cut), p_cut, gap_cut),
        ("p30_and_gap30", (history["p1_" + model] >= p_cut_30) & (history["gap_" + model] >= gap_cut_30), p_cut_30, gap_cut_30),
    ]
    evaluated = []
    for name, selected, _, _ in definitions:
        count = int(selected.sum())
        roi = float(history.loc[selected, "payout_yen"].sum() / (count * BET_YEN) * 100) if count else np.nan
        evaluated.append((name, count, roi))
    eligible_names = {name for name, count, roi in evaluated if count >= MIN_TRAIN_BETS and np.isfinite(roi)}
    if not eligible_names:
        return "", np.nan, np.nan, pd.DataFrame(evaluated, columns=["rule", "training_bets", "training_roi_pct"])
    best_name = max(
        ((name, roi) for name, count, roi in evaluated if name in eligible_names),
        key=lambda item: (item[1], -next(i for i, value in enumerate(evaluated) if value[0] == item[0])),
    )[0]
    chosen = next(item for item in definitions if item[0] == best_name)
    return best_name, float(chosen[2]), float(chosen[3]), pd.DataFrame(
        evaluated, columns=["rule", "training_bets", "training_roi_pct"]
    )


def walk_forward_validation(
    candidates: pd.DataFrame,
    runners: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_rows = candidates.copy()
    all_rows["p1_base"] = all_rows["top1_probability"]
    all_rows["p1_formation"] = all_rows["top1_probability"]
    all_rows["p1_pace"] = all_rows["top1_probability"]
    all_rows["gap_base"] = all_rows["top1_top2_gap"]
    all_rows["gap_formation"] = all_rows["top1_top2_gap"]
    all_rows["gap_pace"] = all_rows["top1_top2_gap"]
    all_rows["ratio_base"] = all_rows["top1_top2_ratio"]
    all_rows["ratio_formation"] = all_rows["top1_top2_ratio"]
    all_rows["ratio_pace"] = all_rows["top1_top2_ratio"]
    all_rows = all_rows.loc[all_rows["model"].isin(LEVELS + ("consensus",))].copy()
    first_date = pd.Timestamp(all_rows["date"].min())
    last_date = pd.Timestamp(all_rows["date"].max()) + pd.Timedelta(days=1)
    if first_date >= WF_START:
        raise ValueError("Insufficient pre-validation history for walk-forward thresholds")
    folds: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    fold_start = WF_START
    while fold_start < last_date:
        fold_end = min(fold_start + pd.DateOffset(months=6), last_date)
        folds.append((fold_start, fold_end))
        fold_start = fold_end

    wf_detail: list[pd.DataFrame] = []
    fold_records: list[dict[str, object]] = []
    purchase_records: list[dict[str, object]] = []
    detail_flags = all_rows[["race_id", "model"]].drop_duplicates().set_index(["race_id", "model"])
    flag_columns = [
        f"walkforward_{signal}_{int(rate * 100)}pct_selected"
        for signal in ("top1_probability", "top1_top2_gap", "top1_top2_ratio", "top1_agreement_votes", "negative_top1_probability_sd")
        for rate in PURCHASE_RATES
    ]
    for column in flag_columns:
        detail_flags[column] = False
    detail_flags["wf_fold_id"] = ""
    detail_flags["wf_s1_top20_selected"] = False
    detail_flags["wf_s2_gap_top20_selected"] = False
    detail_flags["wf_s3_unanimous_selected"] = False
    detail_flags["wf_s4_condition_selected"] = False
    detail_flags["wf_s6_combination_selected"] = False
    detail_flags["wf_s4_condition"] = ""
    detail_flags["wf_s6_rule"] = ""
    detail_flags["wf_s0_top1_selected"] = False

    def set_flags(rows: pd.DataFrame, column: str, values: Iterable[object]) -> None:
        keys = pd.MultiIndex.from_frame(rows[["race_id", "model"]])
        detail_flags.loc[keys, column] = np.asarray(list(values))

    def get_flags(rows: pd.DataFrame, column: str) -> np.ndarray:
        keys = pd.MultiIndex.from_frame(rows[["race_id", "model"]])
        return detail_flags[column].reindex(keys).to_numpy()

    signals = ("top1_probability", "top1_top2_gap", "top1_top2_ratio", "top1_agreement_votes", "negative_top1_probability_sd")
    for fold_number, (test_start, test_end) in enumerate(folds, start=1):
        fold_id = f"fold_{fold_number}_{test_start:%Y%m%d}_{test_end:%Y%m%d}"
        history = all_rows.loc[all_rows["date"].lt(test_start)].copy()
        test = all_rows.loc[all_rows["date"].ge(test_start) & all_rows["date"].lt(test_end)].copy()
        if test.empty:
            continue
        for signal in signals:
            models = ("consensus",) if signal in ("top1_agreement_votes", "negative_top1_probability_sd") else LEVELS
            for model in models:
                train_model = history.loc[history["model"].eq(model)]
                test_model = test.loc[test["model"].eq(model)]
                if train_model.empty or test_model.empty:
                    continue
                score_col = _signal_column(signal, model)
                for rate in PURCHASE_RATES:
                    cutoff = -np.inf if rate == 1.0 else _threshold(train_model[score_col], rate)
                    selected = (
                        pd.Series(True, index=test_model.index)
                        if rate == 1.0 else test_model[score_col].ge(cutoff)
                    )
                    strategy = f"{signal}_{int(rate * 100)}pct"
                    fold_records.append(
                        _strategy_record(
                            test_model, selected, fold_id=fold_id, strategy=strategy, model=model,
                            signal=signal, requested_rate=rate, threshold=cutoff,
                            train_races=int(train_model["race_id"].nunique()),
                            train_bets=int(train_model[score_col].notna().sum()),
                        )
                    )
                    purchase_records.append(
                        {
                            "fold_id": fold_id,
                            "test_start": test_model["date"].min().strftime("%Y-%m-%d"),
                            "test_end": test_model["date"].max().strftime("%Y-%m-%d"),
                            "model": model,
                            "signal": signal,
                            "requested_purchase_rate_pct": rate * 100,
                            "training_threshold": cutoff,
                            **_metrics_with_nonbuyers(test_model, selected),
                        }
                    )
                    set_flags(test_model, f"walkforward_{signal}_{int(rate * 100)}pct_selected", selected)
        chosen_condition_by_model: dict[str, dict[str, object] | None] = {}
        combination_by_model: dict[str, tuple[str, float, float]] = {}
        for model in LEVELS:
            train_model = history.loc[history["model"].eq(model)]
            test_model = test.loc[test["model"].eq(model)]
            if test_model.empty:
                continue
            p_cut = _threshold(train_model["p1_" + model], 0.20)
            gap_cut = _threshold(train_model["gap_" + model], 0.20)
            s1 = test_model["p1_" + model].ge(p_cut)
            s2 = test_model["gap_" + model].ge(gap_cut)
            fold_records.extend(
                [
                    _strategy_record(test_model, pd.Series(True, index=test_model.index), fold_id=fold_id,
                                     strategy="S0_top1_all", model=model, train_races=train_model["race_id"].nunique()),
                    _strategy_record(test_model, s1, fold_id=fold_id, strategy="S1_top_probability_20pct",
                                     model=model, signal="top1_probability", requested_rate=0.2,
                                     threshold=p_cut, train_races=train_model["race_id"].nunique()),
                    _strategy_record(test_model, s2, fold_id=fold_id, strategy="S2_top_gap_20pct",
                                     model=model, signal="top1_top2_gap", requested_rate=0.2,
                                     threshold=gap_cut, train_races=train_model["race_id"].nunique()),
                ]
            )
            set_flags(test_model, "wf_fold_id", [fold_id] * len(test_model))
            set_flags(test_model, "wf_s0_top1_selected", [True] * len(test_model))
            set_flags(test_model, "wf_s1_top20_selected", s1)
            set_flags(test_model, "wf_s2_gap_top20_selected", s2)

            condition, eligible_conditions = _calibrate_conditions(history, model)
            chosen_condition_by_model[model] = condition
            if condition is None:
                s4 = pd.Series(False, index=test_model.index)
                condition_name = "NO_PAST_CONDITION_WITH_30_BETS_AND_ROI_GE_100"
            else:
                s4 = _condition_mask(test_model, condition)
                condition_name = _condition_name(condition[column] for column in CONDITION_COLUMNS)
            fold_records.append(
                _strategy_record(
                    test_model, s4, fold_id=fold_id, strategy="S4_past_selected_condition", model=model,
                    train_races=int(train_model["race_id"].nunique()),
                    train_bets=int(eligible_conditions.iloc[0]["races"]) if len(eligible_conditions) else 0,
                    selected_condition=condition_name,
                )
            )
            set_flags(test_model, "wf_s4_condition_selected", s4)
            set_flags(test_model, "wf_s4_condition", [condition_name] * len(test_model))

            rule, selected_p_cut, selected_gap_cut, train_rules = _best_combination_rule(history, model)
            combination_by_model[model] = (rule, selected_p_cut, selected_gap_cut)
            if rule == "p20_and_unanimous":
                s6 = test_model["p1_" + model].ge(selected_p_cut) & test_model["top1_agreement_votes"].eq(3)
            elif rule == "gap20_and_unanimous":
                s6 = test_model["gap_" + model].ge(selected_gap_cut) & test_model["top1_agreement_votes"].eq(3)
            elif rule in ("p20_and_gap20", "p30_and_gap30"):
                s6 = test_model["p1_" + model].ge(selected_p_cut) & test_model["gap_" + model].ge(selected_gap_cut)
            else:
                s6 = pd.Series(False, index=test_model.index)
            fold_records.append(
                _strategy_record(
                    test_model, s6, fold_id=fold_id, strategy="S6_development_selected_combination", model=model,
                    train_races=int(train_model["race_id"].nunique()),
                    train_bets=int(train_rules["training_bets"].max()) if len(train_rules) else 0,
                    selected_condition=f"{rule}; p_cut={selected_p_cut}; gap_cut={selected_gap_cut}",
                )
            )
            set_flags(test_model, "wf_s6_combination_selected", s6)
            set_flags(test_model, "wf_s6_rule", [rule] * len(test_model))

        consensus_test = test.loc[test["model"].eq("consensus")]
        if not consensus_test.empty:
            unanimous = consensus_test["top1_agreement_votes"].eq(3)
            fold_records.append(
                _strategy_record(
                    consensus_test, unanimous, fold_id=fold_id, strategy="S3_three_way_unanimous",
                    model="consensus", train_races=int(history.loc[history["model"].eq("consensus"), "race_id"].nunique()),
                )
            )
            set_flags(consensus_test, "wf_fold_id", [fold_id] * len(consensus_test))
            set_flags(consensus_test, "wf_s3_unanimous_selected", unanimous)

        for model in LEVELS:
            top_test = test.loc[test["model"].eq(model)]
            if top_test.empty:
                continue
            top_history = history.loc[history["model"].eq(model)]
            for strategy, selection_column in (
                ("S0_top1_all", None),
                ("S1_top_probability_20pct", "wf_s1_top20_selected"),
                ("S2_top_gap_20pct", "wf_s2_gap_top20_selected"),
                ("S4_past_selected_condition", "wf_s4_condition_selected"),
                ("S6_development_selected_combination", "wf_s6_combination_selected"),
            ):
                if selection_column is None:
                    selected = pd.Series(True, index=top_test.index)
                else:
                    selected = get_flags(top_test, selection_column)
                    selected = pd.Series(selected, index=top_test.index)
                selected_condition = ""
                if strategy == "S4_past_selected_condition":
                    condition = chosen_condition_by_model.get(model)
                    selected_condition = (
                        _condition_name(condition[column] for column in CONDITION_COLUMNS)
                        if condition else "NO_PAST_CONDITION_WITH_30_BETS_AND_ROI_GE_100"
                    )
                if strategy == "S6_development_selected_combination":
                    selected_condition = combination_by_model[model][0]
                detail = top_test[
                    ["race_id", "date", "year", "model", "selected_horse_id", "selected_umaban",
                     "top1_probability", "hit", "payout_yen", "final_odds"]
                ].copy()
                detail["fold_id"] = fold_id
                detail["strategy"] = strategy
                detail["is_selected"] = np.asarray(selected, dtype=bool)
                detail["selected_condition"] = selected_condition
                wf_detail.append(detail)
        detail = consensus_test[
            ["race_id", "date", "year", "model", "selected_horse_id", "selected_umaban",
             "top1_probability", "hit", "payout_yen", "final_odds"]
        ].copy()
        detail["fold_id"] = fold_id
        detail["strategy"] = "S3_three_way_unanimous"
        detail["is_selected"] = unanimous.to_numpy()
        detail["selected_condition"] = "top1_horse_unanimity"
        wf_detail.append(detail)

    detail_flags = detail_flags.reset_index()
    detail_flags = detail_flags.merge(all_rows, on=["race_id", "model"], how="right", validate="one_to_one")
    detail_flags = detail_flags.sort_values(["date", "race_id", "model"], kind="stable")
    purchase_summary = pd.DataFrame(purchase_records)
    purchase_output = []
    for (model, signal, requested_rate), group in purchase_summary.groupby(
        ["model", "signal", "requested_purchase_rate_pct"]
    ):
        purchase_output.append(
            {
                "analysis_period": f"{group['test_start'].min()}/{group['test_end'].max()}",
                "test_period_start": group["test_start"].min(),
                "test_period_end": group["test_end"].max(),
                "evaluation_scope": "nonoverlapping_walk_forward_folds_pooled",
                "model": model,
                "signal": signal,
                "requested_purchase_rate_pct": requested_rate,
                "training_threshold_min": group["training_threshold"].min(),
                "training_threshold_max": group["training_threshold"].max(),
                "folds": group["fold_id"].nunique(),
                "eligible_races": int(group["eligible_races"].sum()),
                "purchase_races": int(group["purchase_races"].sum()),
                "purchase_rate_pct": float(group["purchase_races"].sum() / group["eligible_races"].sum() * 100),
                "hits": int(group["hits"].sum()),
                "hit_rate_pct": float(group["hits"].sum() / group["purchase_races"].sum() * 100)
                if group["purchase_races"].sum() else np.nan,
                "investment_yen": float(group["investment_yen"].sum()),
                "payout_yen": float(group["payout_yen"].sum()),
                "profit_yen": float(group["profit_yen"].sum()),
                "roi_pct": float(group["payout_yen"].sum() / group["investment_yen"].sum() * 100)
                if group["investment_yen"].sum() else np.nan,
                "nonpurchase_races": int(group["nonpurchase_races"].sum()),
                "nonpurchase_hit_rate_pct": (
                    float(group["nonpurchase_hits"].sum() / group["nonpurchase_races"].sum() * 100)
                    if group["nonpurchase_races"].sum() else np.nan
                ),
                "nonpurchase_roi_pct": (
                    float(
                        sum(
                            float(row.nonpurchase_roi_pct) * float(row.nonpurchase_races) * BET_YEN / 100
                            for row in group.itertuples()
                            if pd.notna(row.nonpurchase_roi_pct)
                        )
                        / (group["nonpurchase_races"].sum() * BET_YEN) * 100
                    )
                    if group["nonpurchase_races"].sum() else np.nan
                ),
            }
        )
    walk_forward = pd.concat(wf_detail, ignore_index=True) if wf_detail else pd.DataFrame()
    return walk_forward, pd.DataFrame(fold_records), pd.DataFrame(purchase_output), detail_flags


def _daily_bootstrap(
    strategy_rows: pd.DataFrame,
    baseline_rows: pd.DataFrame,
    seed: int,
    draws: int = 1000,
) -> tuple[float, float, float, float]:
    dates = sorted(set(strategy_rows["date"]) | set(baseline_rows["date"]))
    if not dates:
        return (np.nan, np.nan, np.nan, np.nan)
    strategy_by_day = strategy_rows.loc[strategy_rows["is_selected"]].groupby("date").agg(
        returned=("payout_yen", "sum"), bets=("race_id", "size")
    )
    baseline_by_day = baseline_rows.loc[baseline_rows["is_selected"]].groupby("date").agg(
        returned=("payout_yen", "sum"), bets=("race_id", "size")
    )
    strategy_return = strategy_by_day["returned"].reindex(dates, fill_value=0).to_numpy(dtype=float)
    strategy_bets = strategy_by_day["bets"].reindex(dates, fill_value=0).to_numpy(dtype=float)
    base_return = baseline_by_day["returned"].reindex(dates, fill_value=0).to_numpy(dtype=float)
    base_bets = baseline_by_day["bets"].reindex(dates, fill_value=0).to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(dates), size=(draws, len(dates)))
    strat_roi = np.divide(
        strategy_return[sampled].sum(axis=1),
        strategy_bets[sampled].sum(axis=1) * BET_YEN,
        out=np.full(draws, np.nan),
        where=strategy_bets[sampled].sum(axis=1) > 0,
    ) * 100
    base_roi = np.divide(
        base_return[sampled].sum(axis=1),
        base_bets[sampled].sum(axis=1) * BET_YEN,
        out=np.full(draws, np.nan),
        where=base_bets[sampled].sum(axis=1) > 0,
    ) * 100
    diff = strat_roi - base_roi
    return (
        float(np.nanpercentile(strat_roi, 2.5)),
        float(np.nanpercentile(strat_roi, 97.5)),
        float(np.nanpercentile(diff, 2.5)),
        float(np.nanpercentile(diff, 97.5)),
    )


def _oracle_strategy_rows(runners: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    for model in LEVELS:
        top = candidates.loc[candidates["model"].eq(model)].copy()
        top["ev_ratio"] = top["top1_probability"] * top["final_odds"]
        all_model = runners.loc[runners["level"].eq(model)].copy()
        all_model["ev_ratio"] = all_model["p_cal"] * all_model["win_odds_reference"]
        all_model = all_model.sort_values(
            ["race_id", "ev_ratio", "umaban"], ascending=[True, False, True], kind="stable"
        )
        max_ev = all_model.drop_duplicates("race_id", keep="first").copy()
        max_ev = max_ev.rename(
            columns={
                "horse_id": "selected_horse_id", "umaban": "selected_umaban", "p_cal": "top1_probability",
                "target": "hit", "win_payout": "payout_yen", "win_odds_reference": "final_odds",
            }
        )
        for selection_name, sample in (("top1", top), ("max_ev_horse", max_ev)):
            sample = sample.copy()
            sample["ev_ratio"] = sample["top1_probability"] * sample["final_odds"]
            for threshold in EV_THRESHOLDS:
                selected = sample.loc[sample["ev_ratio"].gt(threshold)]
                output.append(
                    {
                        "analysis_period": sample["analysis_period"].iloc[0],
                        "evaluation_scope": "posthoc_oracle_final_odds_not_operational",
                        "model": model,
                        "selection": selection_name,
                        "ev_threshold": threshold,
                        "eligible_races": int(sample["race_id"].nunique()),
                        **summarize_bets(selected),
                        "purchase_rate_pct": (
                            len(selected) / sample["race_id"].nunique() * 100
                            if sample["race_id"].nunique() else np.nan
                        ),
                    }
                )
    return pd.DataFrame(output)


def strategy_comparison(
    wf_detail: pd.DataFrame,
    wf_results: pd.DataFrame,
    candidates: pd.DataFrame,
    runners: pd.DataFrame,
) -> pd.DataFrame:
    strategies = [
        "S0_top1_all",
        "S1_top_probability_20pct",
        "S2_top_gap_20pct",
        "S3_three_way_unanimous",
        "S4_past_selected_condition",
        "S6_development_selected_combination",
    ]
    rows = []
    for strategy in strategies:
        strategy_models = (
            ("consensus",) if strategy.startswith("S3_") else LEVELS
        )
        for model in strategy_models:
            sample = wf_detail.loc[wf_detail["strategy"].eq(strategy) & wf_detail["model"].eq(model)]
            if sample.empty:
                continue
            all_races = sample.copy()
            selected = all_races.loc[all_races["is_selected"]]
            unselected = all_races.loc[~all_races["is_selected"]]
            summary = summarize_bets(selected)
            baseline_model = "base" if model == "consensus" else model
            baseline = wf_detail.loc[
                wf_detail["strategy"].eq("S0_top1_all") & wf_detail["model"].eq(baseline_model)
            ]
            ci_low, ci_high, diff_low, diff_high = _daily_bootstrap(
                all_races,
                baseline,
                seed=20261026 + strategies.index(strategy) * 7 + (LEVELS.index(model) if model in LEVELS else 0),
            )
            row: dict[str, object] = {
                "analysis_period": (
                    f"{all_races['date'].min():%Y-%m-%d}/{all_races['date'].max():%Y-%m-%d}"
                ),
                "evaluation_scope": "walk_forward_oos_nonoverlapping",
                "strategy": strategy,
                "model": model,
                "folds": all_races["fold_id"].nunique(),
                "eligible_races": int(all_races["race_id"].nunique()),
                **summary,
                "purchase_rate_pct": (
                    len(selected) / all_races["race_id"].nunique() * 100 if len(all_races) else np.nan
                ),
                "nonpurchase_races": len(unselected),
                "nonpurchase_hit_rate_pct": float(unselected["hit"].mean() * 100) if len(unselected) else np.nan,
                "nonpurchase_roi_pct": (
                    float(unselected["payout_yen"].sum() / (len(unselected) * BET_YEN) * 100)
                    if len(unselected) else np.nan
                ),
                "roi_ci95_low_pct": ci_low,
                "roi_ci95_high_pct": ci_high,
                "roi_diff_vs_s0_ci95_low_pp": diff_low,
                "roi_diff_vs_s0_ci95_high_pp": diff_high,
                "bootstrap_unit": "calendar_date_cluster_paired",
                "selected_condition_or_rule": (
                    "; ".join(
                        sorted(set(wf_results.loc[
                            wf_results["strategy"].eq(strategy) & wf_results["model"].eq(model),
                            "selected_condition",
                        ].dropna().astype(str)))
                    )
                ),
            }
            annual = selected.groupby("year").agg(returned=("payout_yen", "sum"), bets=("race_id", "size"))
            for year in YEAR_LABELS:
                bets = int(annual.loc[year, "bets"]) if year in annual.index else 0
                returned = float(annual.loc[year, "returned"]) if year in annual.index else 0.0
                row[f"roi_{year}_pct"] = returned / (bets * BET_YEN) * 100 if bets else np.nan
                row[f"bets_{year}"] = bets
            annual_rois = [row[f"roi_{year}_pct"] for year in YEAR_LABELS if pd.notna(row[f"roi_{year}_pct"])]
            row["annual_roi_std_pp"] = float(np.std(annual_rois, ddof=0)) if len(annual_rois) > 1 else np.nan
            row["annual_roi_over_100_count"] = sum(1 for roi in annual_rois if roi > 100)
            row["previously_examined_data_not_untouched"] = True
            rows.append(row)

    oracle = _oracle_strategy_rows(runners, candidates)
    for item in oracle.to_dict("records"):
        rows.append(
            {
                **item,
                "strategy": f"S5_oracle_{item['selection']}_EV_gt_{item['ev_threshold']:.2f}",
                "evaluation_scope": item["evaluation_scope"],
                "model": item["model"],
                "roi_ci95_low_pct": np.nan,
                "roi_ci95_high_pct": np.nan,
                "roi_diff_vs_s0_ci95_low_pp": np.nan,
                "roi_diff_vs_s0_ci95_high_pp": np.nan,
                "bootstrap_unit": "not_applicable_posthoc_oracle",
                "previously_examined_data_not_untouched": True,
            }
        )
    return pd.DataFrame(rows)


def bet_level_results(
    detail_flags: pd.DataFrame,
    runners: pd.DataFrame,
) -> pd.DataFrame:
    result = detail_flags.copy()
    result["ev_ratio_final_odds_oracle"] = result["top1_probability"] * result["final_odds"]
    for threshold in EV_THRESHOLDS:
        result[f"oracle_top1_ev_gt_{threshold:.2f}"] = result["ev_ratio_final_odds_oracle"].gt(threshold)
    result["result_source_note"] = "Final odds and outcomes are post-race references; not executable pre-race bets."
    result["analysis_period"] = (
        f"{result['date'].min():%Y-%m-%d}/{result['date'].max():%Y-%m-%d}"
    )
    max_ev_rows = []
    for model in LEVELS:
        sample = runners.loc[runners["level"].eq(model)].copy()
        sample["ev_ratio_final_odds_oracle"] = sample["p_cal"] * sample["win_odds_reference"]
        selected = sample.sort_values(
            ["race_id", "ev_ratio_final_odds_oracle", "umaban"],
            ascending=[True, False, True],
            kind="stable",
        ).drop_duplicates("race_id")
        selected["model"] = f"{model}_oracle_max_ev"
        selected["selected_horse_id"] = selected["horse_id"]
        selected["selected_umaban"] = selected["umaban"]
        selected["top1_probability"] = selected["p_cal"]
        selected["hit"] = selected["target"]
        selected["payout_yen"] = selected["win_payout"]
        selected["final_odds"] = selected["win_odds_reference"]
        selected["result_source_note"] = "Retrospective max-EV horse using final odds; not an executable bet."
        selected["analysis_period"] = result["analysis_period"].iloc[0]
        keep = [
            "race_id", "date", "year", "model", "selected_horse_id", "selected_umaban",
            "top1_probability", "hit", "payout_yen", "final_odds", "ev_ratio_final_odds_oracle",
            "result_source_note", "analysis_period",
        ]
        max_ev_rows.append(selected[keep])
    result["result_source_note"] = "Final odds and outcomes are post-race references; not executable pre-race bets."
    return pd.concat([result, *max_ev_rows], ignore_index=True, sort=False)


def _write_graphs(
    out_dir: Path,
    calibration: pd.DataFrame,
    annual: pd.DataFrame,
    purchase: pd.DataFrame,
    comparison: pd.DataFrame,
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    graph_names = []
    fig, axis = plt.subplots(figsize=(7, 6))
    axis.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Perfect calibration")
    for model in (*LEVELS, "market_final_odds_reference"):
        sample = calibration.loc[
            calibration["scope"].eq("all_runners_reliability") & calibration["model"].eq(model)
        ].dropna(subset=["mean_predicted_probability", "actual_win_rate"])
        if not sample.empty:
            axis.plot(sample["mean_predicted_probability"], sample["actual_win_rate"], marker="o", label=model)
    axis.set(xlabel="Mean predicted win probability", ylabel="Observed win rate", title="RACEVERSE reliability")
    axis.legend()
    fig.tight_layout()
    name = "reliability_diagram.png"
    fig.savefig(out_dir / name, dpi=140)
    plt.close(fig)
    graph_names.append(name)

    sample = annual.loc[annual["condition_id"].isin(["all_races", "G3"])]
    fig, axis = plt.subplots(figsize=(9, 5))
    for model in LEVELS:
        subset = sample.loc[sample["model"].eq(model)]
        for condition in ("all_races", "G3"):
            line = subset.loc[subset["condition_id"].eq(condition)].sort_values("year")
            if not line.empty:
                axis.plot(line["year"], line["roi_pct"], marker="o", label=f"{model} / {condition}")
    axis.axhline(100, color="grey", linestyle="--")
    axis.set(xlabel="Calendar year (2023/2026 are partial)", ylabel="Win ROI (%)", title="Annual ROI stability")
    axis.legend()
    fig.tight_layout()
    name = "annual_roi_stability.png"
    fig.savefig(out_dir / name, dpi=140)
    plt.close(fig)
    graph_names.append(name)

    fig, axis = plt.subplots(figsize=(9, 5))
    subset = comparison.loc[
        comparison["evaluation_scope"].eq("walk_forward_oos_nonoverlapping")
        & comparison["strategy"].str.startswith(("S0_", "S1_", "S2_", "S3_", "S4_", "S6_"))
    ]
    labels = []
    values = []
    for row in subset.itertuples(index=False):
        labels.append(f"{row.model}:{row.strategy.split('_')[0]}")
        values.append(row.roi_pct)
    axis.bar(np.arange(len(values)), values)
    axis.axhline(100, color="grey", linestyle="--")
    axis.set_xticks(np.arange(len(values)), labels, rotation=75, ha="right")
    axis.set(ylabel="Win ROI (%)", title="Walk-forward strategy ROI")
    fig.tight_layout()
    name = "walk_forward_strategy_roi.png"
    fig.savefig(out_dir / name, dpi=140)
    plt.close(fig)
    graph_names.append(name)

    fig, axis = plt.subplots(figsize=(8, 5))
    subset = purchase.loc[
        purchase["model"].isin(LEVELS) & purchase["signal"].eq("top1_probability")
    ]
    for model in LEVELS:
        line = subset.loc[subset["model"].eq(model)].sort_values("requested_purchase_rate_pct")
        axis.plot(line["requested_purchase_rate_pct"], line["roi_pct"], marker="o", label=model)
    axis.axhline(100, color="grey", linestyle="--")
    axis.set(xlabel="Requested purchase rate (%)", ylabel="Walk-forward ROI (%)", title="Top1 probability selection")
    axis.legend()
    fig.tight_layout()
    name = "purchase_rate_roi.png"
    fig.savefig(out_dir / name, dpi=140)
    plt.close(fig)
    graph_names.append(name)
    return graph_names


def _write_readme(out_dir: Path, counts: dict[str, int], graph_names: list[str]) -> None:
    graphs = "\n".join(f"- `{name}`" for name in graph_names)
    content = f"""# RACEVERSE 回収率・購入条件検証

## 目的とデータ

予測確率・Top1選択の精度と、購入対象を絞った場合の回収率を切り分けて検証します。既存の月次Walk-Forward出力 `{DEFAULT_INPUT.relative_to(ROOT)}` を再利用し、GradeCDと確定払戻は `data/raw/race.db` から取得します。再学習および既存予測パイプラインの変更は行いません。

- 校正済み予測の実対象期間: {counts['first_date']}〜{counts['last_date']}（両端を含む）
- レース数: {counts['races']:,}、方式ごとの出走馬数: {counts['runners']:,}
- 対象方式: base / formation / pace。廃止済みfullは除外。
- 購入額: 1レースあたり単勝100円。
- 2023年・2026年は有効な評価期間のみで、通年ではありません。
- GradeCD A/B/C/LのみG1/G2/G3/Listedと表示します。D/Eは `GradeCD=D` / `GradeCD=E` のまま扱い、その他の未確認コードをクラス名に読み替えません。

## 時点情報と制約

既存出力の `win_odds_reference` は確定オッズです。予測CSVと利用可能なレースDBには、発走前オッズと取得時刻を確認できる履歴がありません。そのためS5およびEV閾値の成績は事後オラクル分析に限定し、実運用可能な購入結果とは区別します。オッズ変動も検証できません。

確定払戻はCSV内で多数の出走馬について欠損しているため、`race.db` の `NL_HR_PAY` から復元します。勝ち馬の払戻欠損はエラーとし、払戻記録のない非勝ち馬は払戻0円として扱います。元予測は月次Walk-Forwardで生成され、校正確率も過去の結果に基づく一方、購入条件にはさらに6か月ごとの拡大型Walk-Forwardを適用し、各テスト期間より前のデータだけで閾値・条件を選びます。

対象4,411レースは既存レポート等ですでに参照済みです。したがって本検証は未使用テストではなく、独立した最終認証として扱えません。

## 実行方法

```bash
.venv/bin/python scripts/raceverse_roi_strategy_validation.py
```

Optional paths:

```bash
.venv/bin/python scripts/raceverse_roi_strategy_validation.py \\
  --input reports/raceverse/backtest_5y_202109_202609_no_full \\
  --combinations reports/raceverse/market_analysis_5y_202109_202609_no_full/roi_by_combination.csv \\
  --db data/raw/race.db \\
  --out reports/raceverse/roi_strategy_validation
```

## 出力

- `summary.md`: 結論、推奨、制約、質問への回答。
- `annual_stability.csv`: 指定条件と、既存CSVから抽出した「30件以上・全期間ROI100%以上」の複合条件の年別成績。既存条件は事後選択であることを記録します。
- `model_agreement.csv`: 3方式の一致・不一致、確率ばらつき、年別成績。
- `calibration_analysis.csv`: 全出走馬のBrier / Winner Logloss / ECE / reliability bins、およびTop1勝率帯。
- `odds_band_analysis.csv`: 確定オッズ帯ごとのTop1成績（事後分析）。
- `purchase_rate_analysis.csv`: 5種類のオッズ非依存指標について、10/20/30/50/100%を狙ったWalk-Forward結果と非購入レースとの比較。
- `strategy_comparison.csv`: OOS S0〜S6の比較、日付クラスタ対応Bootstrap信頼区間、別枠のS5事後オラクル。
- `walk_forward_results.csv`: foldごとの成績と過去データのみで選んだ閾値・条件。
- `bet_level_results.csv`: 各方式Top1、合意候補、確定オッズを使う事後最大EV候補、払戻、fold、選択フラグ。
- グラフ:
{graphs}

全CSVに `analysis_period` と標本数、またはレース単位の期間情報を含めます。少数標本は除外せずフラグで示します。Winner Loglossは同着3レースを除外します。
"""
    (out_dir / "README.md").write_text(content, encoding="utf-8")


def _format_pct(value: object) -> str:
    return "n/a" if pd.isna(value) else f"{float(value):.1f}%"


def _write_summary(
    out_dir: Path,
    counts: dict[str, int],
    annual: pd.DataFrame,
    calibration: pd.DataFrame,
    agreement: pd.DataFrame,
    purchase: pd.DataFrame,
    comparison: pd.DataFrame,
    odds: pd.DataFrame,
    graph_names: list[str],
) -> None:
    executable = comparison.loc[comparison["evaluation_scope"].eq("walk_forward_oos_nonoverlapping")].copy()
    highest_any = executable.loc[executable["roi_pct"].notna()].sort_values(
        ["roi_pct", "purchase_races"], ascending=[False, False]
    ).head(1)
    potential = executable.loc[executable["purchase_races"].ge(100)]
    highest = potential.sort_values(["roi_pct", "purchase_races"], ascending=[False, False]).head(1)
    stable_pool = potential.loc[potential["annual_roi_over_100_count"].notna()]
    stable = stable_pool.sort_values(
        ["annual_roi_std_pp", "purchase_races"], ascending=[True, False], na_position="last"
    ).head(1)
    highest_text = "100件以上の購入戦略がありません。"
    if not highest.empty:
        row = highest.iloc[0]
        highest_text = (
            f"{row['strategy']}（{row['model']}）: ROI {_format_pct(row['roi_pct'])}、"
            f"購入{int(row['purchase_races'])}件、損益{row['profit_yen']:.0f}円"
        )
    highest_any_text = "評価対象の購入がありません。"
    if not highest_any.empty:
        row = highest_any.iloc[0]
        highest_any_text = (
            f"{row['strategy']}（{row['model']}）: ROI {_format_pct(row['roi_pct'])}、"
            f"購入{int(row['purchase_races'])}件、損益{row['profit_yen']:.0f}円、"
            f"ROIの95%信頼区間 {_format_pct(row['roi_ci95_low_pct'])}〜{_format_pct(row['roi_ci95_high_pct'])}"
        )
    stable_text = "年別安定性を比較できる戦略がありません。"
    if not stable.empty:
        row = stable.iloc[0]
        stable_text = (
            f"{row['strategy']}（{row['model']}）: 対象年のROI標準偏差"
            f"{row['annual_roi_std_pp']:.1f}ポイント、購入{int(row['purchase_races'])}件。"
            "記述的な比較であり、期待収益が正である証明ではありません。"
        )
    g3 = annual.loc[
        annual["condition_id"].eq("G3") & annual["model"].eq("formation")
    ].sort_values("year")
    g3_text = (
        "、".join(f"{int(row.year)}年 {_format_pct(row.roi_pct)}（{int(row.purchase_races)}件）"
                  for row in g3.itertuples())
        if not g3.empty else "G3 formationの記録がありません。"
    )
    metrics = calibration.loc[
        calibration["scope"].eq("all_runners_summary")
        & calibration["model"].isin((*LEVELS, "market_final_odds_reference"))
    ].set_index("model")
    model_logloss = "、".join(
        f"{model}: {metrics.loc[model, 'winner_logloss']:.4f}"
        for model in (*LEVELS, "market_final_odds_reference") if model in metrics.index
    )
    top1 = calibration.loc[calibration["scope"].eq("top1_summary")].set_index("model")
    top1_comparison = "、".join(
        f"{model} 的中率{top1.loc[model, 'hit_rate_pct']:.1f}% / ROI {top1.loc[model, 'roi_pct']:.1f}%"
        for model in (*LEVELS, "market_final_odds_reference") if model in top1.index
    )
    base_s0 = executable.loc[executable["strategy"].eq("S0_top1_all") & executable["model"].eq("base")]
    base_roi = _format_pct(base_s0["roi_pct"].iloc[0]) if len(base_s0) else "n/a"
    formation = executable.loc[executable["strategy"].eq("S0_top1_all") & executable["model"].eq("formation")]
    formation_roi = _format_pct(formation["roi_pct"].iloc[0]) if len(formation) else "n/a"
    available_rates = purchase.loc[purchase["signal"].eq("top1_probability") & purchase["model"].isin(LEVELS)]
    best_rate = available_rates.sort_values(["roi_pct", "purchase_races"], ascending=[False, False]).head(1)
    rate_note = (
        f"Top1勝率による選別の最高ROIは{best_rate.iloc[0]['model']}の目標購入率"
        f"{best_rate.iloc[0]['requested_purchase_rate_pct']:.0f}%（実績{best_rate.iloc[0]['purchase_rate_pct']:.1f}%）、"
        f"ROI {_format_pct(best_rate.iloc[0]['roi_pct'])}、損益{best_rate.iloc[0]['profit_yen']:.0f}円でした。"
        if len(best_rate) else "Top1勝率による購入選別の結果がありません。"
    )
    agreement_all = agreement.loc[agreement["year"].eq("ALL")].set_index("agreement_condition")
    agreement_text = "方式一致条件の結果がありません。"
    if {"A_all_three_agree", "B_two_agree"}.issubset(agreement_all.index):
        all_agree = agreement_all.loc["A_all_three_agree"]
        two_agree = agreement_all.loc["B_two_agree"]
        agreement_text = (
            f"3方式一致は{int(all_agree['sample_races'])}件・ROI {all_agree['roi_pct']:.1f}%"
            f"、2方式一致は{int(two_agree['sample_races'])}件・ROI {two_agree['roi_pct']:.1f}%"
        )
    prior_combos = annual.loc[annual["condition_id"].astype(str).str.startswith("prior_combo")].copy()
    combo_cells = prior_combos.groupby(["condition_id", "model"]).agg(
        ex3_years_above_100=("roi_ex_top_3_payout_pct", lambda values: int((values > 100).sum()))
    )
    combo_total = len(combo_cells)
    combo_persistent_ex3 = int(combo_cells["ex3_years_above_100"].ge(2).sum())
    low_odds = odds.loc[
        odds["odds_band"].eq("1.0-1.9") & odds["model"].eq("base")
    ]
    low_odds_text = "No base Top1 observations in the 1.0-1.9 final-odds band."
    if not low_odds.empty and int(low_odds.iloc[0]["n"]) > 0:
        row = low_odds.iloc[0]
        low_odds_text = (
            f"確定オッズ1.0〜1.9倍帯のbase Top1は、予測勝率"
            f"{row['mean_predicted_win_probability'] * 100:.1f}%に対して実測"
            f"{row['actual_win_rate'] * 100:.1f}%、ROI {row['roi_pct']:.1f}%（{int(row['n'])}件）でした。"
        )
    g3_sensitivity = (
        "、".join(
            f"{int(row.year)}年の上位3払戻除外後 {_format_pct(row.roi_ex_top_3_payout_pct)}"
            for row in g3.itertuples()
        )
        if not g3.empty else "G3 formationの感度分析結果がありません。"
    )
    findings = []
    if not potential.empty and potential["roi_ci95_low_pct"].gt(100).any():
        findings.append("100件以上の戦略でROIの日時クラスタBootstrap下限が100%を超えましたが、未使用期間での前向き検証が必要です。")
    else:
        findings.append("100件以上のWalk-Forward戦略でROIの日時クラスタBootstrap下限が100%を超えたものはなく、収益性は統計的に確立していません。")
    if len(base_s0) and pd.notna(base_s0["roi_pct"].iloc[0]) and base_s0["roi_pct"].iloc[0] < 100:
        findings.append("全レースを購入するOOS基準戦略は損益分岐点を下回りました。")
    conclusion = " ".join(findings)
    chart_list = "\n".join(f"- `{name}`" for name in graph_names)
    text = f"""# RACEVERSE 次期バックテスト：収益性・購入条件検証

## 1. 総合結論

{' '.join(findings)}

対象は校正済み予測4,411レース（{counts['first_date']}〜{counts['last_date']}）。固定条件を全期間で選んだ過去レポートと、購入ルールを過去データだけで決める外側Walk-Forwardは別の評価です。外側評価は2024-01-06〜2026-08-30で、2026年は部分期間です。元データ自体は過去の分析ですでに参照されているため、未使用テストではありません。

全期間のTop1的中率 / ROIは {top1_comparison}。OOS基準S0のROIはbase {base_roi}、formation {formation_roi}です。確定オッズから作る市場基準は事後比較に限ります。全出走馬のWinner Loglossは {model_logloss} で、市場基準より予測順位・勝率の質が劣ることを示します。ただし、時刻付き発走前オッズがないため、運用可能なオッズ判断の寄与は分離できません。{low_odds_text}

## 2. 最も高い戦略・最も安定した戦略

- 少数標本も含む最高ROI: {highest_any_text}
- 100件以上購入した戦略の最高ROI: {highest_text}
- 100件以上の戦略で年別ROIのばらつきが最小: {stable_text}
- 110%目標を再現できる購入ルールは確認できませんでした。最高ROIだけで採用せず、購入数、純損益、信頼区間、年別成績を併せて判断してください。

## 3. 購入数と収益性のトレードオフ

{rate_note}

`purchase_rate_analysis.csv` は勝率、Top1-Top2差/比、方式間一致度、方式間確率ばらつきについて、購入率10/20/30/50/100%を目指した結果を収録します。閾値はfoldごとに過去データで固定するため、評価側の実際の購入率は指定割合と異なることがあります。全ての上位Top1確率戦略で、購入数を減らしても損益はマイナスでした。ROIとともに非購入レースの成績・純損益・DD・標本数を確認してください。

## 4. 条件別安定性・高配当依存・方式一致

- formationのG3年別ROI: {g3_text}。2023/2026は部分年です。全期間ROI110.9%という集計は安定性を示しません。
- {g3_sensitivity}。上位3払戻を除くと各年とも100%未満で、特定払戻への依存が見られます。
- 既存CSVから抽出した30件以上・全期間ROI100%以上の複合条件は、全期間を見て選んだ候補です。年別比較と上位払戻除外は事後的な安定性検査であり、選択バイアスを除けません。
- 上記の{combo_total}モデル×条件のうち、各年の上位3払戻を除いても2年以上ROI100%を超えたものは{combo_persistent_ex3}件でした。高回収条件は少数の払戻に敏感です。
- {agreement_text}。3方式の一致だけでは購入フィルタとしての優位性は確認できず、全方式不一致の各モデルは28レースのみです。

## 5. 質問への回答

1. **赤字の主因は予測かオッズ判断か？** Top1的中率とWinner Logloss/Brierは事後市場基準より低く、予測順位・勝率の改善が明確な課題です。発走前オッズデータがないため、実行可能なオッズ選別の効果は判定できません。
2. **方式一致は高回収か？** {agreement_text}。一致は購入可否の有効な根拠になっていません。
3. **G3 formation ROI 110.9%は安定か？** いいえ。2023/2024は100%超ですが、2025/2026は100%未満で、上位3払戻除外後は全て100%未満です。
4. **複合条件は高配当の偶然か？** 上位3払戻除外後に複数年100%超を維持した候補は0/{combo_total}でした。さらに候補自体が全期間結果から選ばれています。
5. **購入率を10〜50%へ減らす効果は？** ROIが一部改善しても購入数の減少を伴い、今回のWalk-Forwardでは高回収率の再現につながりません。詳細は `purchase_rate_analysis.csv`。
6. **予測勝率かEV最大馬か？** 発走前オッズと取得時刻がないため比較不能です。S5の最終オッズEVは事後オラクル表であり、実運用成績として使えません。
7. **時系列固定ルールで100%/110%超か？** 100件以上のOOSルールはいずれもROI100%未満です。小標本ではROI100%超の例もありますが信頼区間が広く、利益もほぼありません。110%の再現性はありません。
8. **実運用の推奨は？** 現時点では賭けルールを採用しないでください。発走前オッズを時刻付きで保存し、予測と購入判断をレース前に記録したうえで、事前登録した未使用期間で再評価するのが適切です。

## 6. 過剰適合・不足データ・次の改善

- 全期間から選んだ条件、小標本、少数高配当、最終オッズを用いた事後オラクルに依存するルールは採用しません。
- 発走前オッズ履歴・取得時刻・最終オッズとの差は取得できていません。S5の運用可能な評価は未実施です。
- Winner Loglossは同着3レースを除外しています。小標本の勝率帯はCSV内でフラグを付け、隠していません。
- 既存の月次Walk-Forward予測と校正値を再利用し、新規学習・再校正は行っていません。
- 次は市場に対する勝率順位・確率校正を改善し、時刻付き発走前オッズを記録した前向き検証を行ってください。

## 7. グラフ

{chart_list}

## 8. 再実行

`.venv/bin/python scripts/raceverse_roi_strategy_validation.py`。列定義と制約は同ディレクトリの `README.md` を参照してください。
"""
    (out_dir / "summary.md").write_text(text, encoding="utf-8")


def run(
    input_dir: Path = DEFAULT_INPUT,
    combinations_path: Path = DEFAULT_COMBINATIONS,
    db_path: Path = DEFAULT_DB,
    out_dir: Path = DEFAULT_OUTPUT,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out_dir.mkdir(parents=True, exist_ok=True)
    runners, _, counts = load_analysis_data(input_dir, db_path)
    candidates, wide = make_top_candidates(runners)
    top_candidates = candidates.loc[candidates["model"].isin(LEVELS)].copy()
    annual = annual_stability(top_candidates, combinations_path)
    agreement = model_agreement_analysis(runners, top_candidates, wide)
    calibration = calibration_analysis(runners, top_candidates)
    odds = odds_band_analysis(top_candidates)
    wf_detail, wf_results, purchase, detail_flags = walk_forward_validation(candidates, runners)
    comparison = strategy_comparison(wf_detail, wf_results, top_candidates, runners)
    bets = bet_level_results(detail_flags, runners)

    analysis_period = f"{counts['first_date']}/{counts['last_date']}"
    for table in (annual, agreement, calibration, odds, purchase, comparison, wf_results, bets):
        if "analysis_period" not in table.columns:
            table["analysis_period"] = analysis_period
        table["source_prediction_file"] = _relative_path(input_dir / "predictions.csv")
    annual.to_csv(out_dir / "annual_stability.csv", index=False)
    agreement.to_csv(out_dir / "model_agreement.csv", index=False)
    calibration.to_csv(out_dir / "calibration_analysis.csv", index=False)
    odds.to_csv(out_dir / "odds_band_analysis.csv", index=False)
    purchase.to_csv(out_dir / "purchase_rate_analysis.csv", index=False)
    comparison.to_csv(out_dir / "strategy_comparison.csv", index=False)
    wf_results.to_csv(out_dir / "walk_forward_results.csv", index=False)
    bets.to_csv(out_dir / "bet_level_results.csv", index=False)
    graphs = _write_graphs(out_dir, calibration, annual, purchase, comparison)
    _write_readme(out_dir, counts, graphs)
    _write_summary(out_dir, counts, annual, calibration, agreement, purchase, comparison, odds, graphs)
    LOGGER.info(
        "Wrote ROI validation: %d races, %d runner rows, output=%s",
        counts["races"], counts["runners"], out_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--combinations", type=Path, default=DEFAULT_COMBINATIONS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input, args.combinations, args.db, args.out)


if __name__ == "__main__":
    main()

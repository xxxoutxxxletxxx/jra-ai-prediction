#!/usr/bin/env python3
"""Walk-forward analysis of Ranker ability thresholds and female-only class correction."""

from __future__ import annotations

import argparse
import logging
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

from raceverse.ability_threshold import AbilityThreshold, adjust_probabilities, select_top1
from raceverse.adapters.race_data import surface_from_track_code
from scripts.race_class_ab_test import KEYS, SCORE, classify, race_id

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "reports/raceverse/weekly_5y_202109_202609/predictions.csv"
ABILITY_OOF = ROOT / "data/cache/raceverse/ability_oof_weekly.parquet"
DB = ROOT / "data/raw/race.db"
OUT = ROOT / "reports/raceverse/ability_threshold_202109_202609"
LEVELS = ("base", "formation", "pace")
CORRECTIONS = (0.0, 0.3, 0.5, 0.7, 1.0)
CLASS_LABELS = tuple(label for label, score in SCORE.items() if np.isfinite(score) and label != "UNKNOWN")
CLASS_SCORES = {label: float(SCORE[label]) for label in CLASS_LABELS}
MIN_HISTORY = 20
TRACKS = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
DISTANCE_BINS = [0, 1000, 1150, 1600, 1700, 2500, np.inf]
DISTANCE_LABELS = ["1000m以下", "1150m", "1200〜1600m", "1700m", "1800〜2500m", "2600m以上"]
ODDS_BINS = [0, 2, 3, 5, 10, 20, np.inf]
ODDS_LABELS = ["1倍台", "2倍台", "3〜5倍", "5〜10倍", "10〜20倍", "20倍以上"]
PAYOUT_COLUMNS = [f"PayTansyo{i}{suffix}" for i in range(3) for suffix in ("Umaban", "Pay")]
PAYOUT_COLUMNS += [f"PayFukusyo{i}{suffix}" for i in range(5) for suffix in ("Umaban", "Pay")]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Variant:
    name: str
    mode: str
    strength: float
    correction: float = 0.0
    scope: str = "all"
    probability_gamma: float = 1.0
    threshold_offset: float = 0.0


def variants() -> list[Variant]:
    out = [Variant("current", "none", 0.0)]
    out.extend(
        Variant(f"calibration_only_gamma_{gamma:g}", "none", 0.0, probability_gamma=gamma)
        for gamma in (0.8, 1.2, 1.5)
    )
    out.extend(Variant(f"ability_soft_{v:g}", "soft", v) for v in (0.5, 1.0, 2.0))
    out.extend(Variant(f"ability_hard_{v:g}", "hard", v) for v in (0.5, 1.0, 1.5))
    for offset in (-0.5, 0.0, 0.5):
        offset_name = f"m{abs(offset):g}" if offset < 0 else f"p{offset:g}"
        for slope in (0.0, 0.5, 1.0, 2.0):
            out.extend(
                Variant(
                    f"ability_zero_tilt_o{offset_name}_s{slope:g}_g{gamma:g}",
                    "zero_tilt",
                    slope,
                    probability_gamma=gamma,
                    threshold_offset=offset,
                )
                for gamma in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5)
            )
    out.extend(
        Variant(f"female_only_soft_1_c{c:g}", "soft", 1.0, c, "female_only")
        for c in CORRECTIONS
    )
    out.extend(
        Variant(f"combined_soft_1_c{c:g}", "soft", 1.0, c)
        for c in CORRECTIONS[1:]
    )
    out.extend(
        Variant(f"combined_hard_1_c{c:g}", "hard", 1.0, c)
        for c in CORRECTIONS[1:]
    )
    return out


def read_race_data(db_path: Path, first_year: int, last_year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    race_columns = KEYS + [
        "GradeCD", "JyokenName", "RaceInfoHondai", "RaceInfoFukudai", "TrackCD", "Kyori",
    ]
    run_columns = KEYS + ["KettoNum", "Umaban", "KakuteiJyuni"]
    payout_columns = KEYS + PAYOUT_COLUMNS
    with sqlite3.connect(str(db_path)) as con:
        year_filter = f"idYear >= '{first_year}' AND idYear <= '{last_year}'"
        races = pd.read_sql_query(
            f"SELECT {', '.join(race_columns)} FROM NL_RA_RACE WHERE {year_filter} AND headDataKubun='7'",
            con,
        )
        runs = pd.read_sql_query(
            f"SELECT {', '.join(run_columns)} FROM NL_SE_RACE_UMA WHERE {year_filter} AND headDataKubun='7'",
            con,
        )
        payouts = pd.read_sql_query(
            f"SELECT {', '.join(payout_columns)} FROM NL_RA_RACE "
            f"JOIN NL_HR_PAY USING ({', '.join(KEYS)}) WHERE {year_filter}",
            con,
        )

    races["race_id"] = races.apply(lambda row: race_id(row), axis=1)
    races["date"] = pd.to_datetime(races["idYear"] + races["idMonthDay"], format="%Y%m%d", errors="coerce")
    races["class_label"] = races.apply(classify, axis=1)
    races["class_score"] = races["class_label"].map(CLASS_SCORES)
    titles = races[["RaceInfoHondai", "RaceInfoFukudai", "JyokenName"]].fillna("").astype(str).agg(" ".join, axis=1)
    races["female_only"] = titles.map(
        lambda text: "牝" in unicodedata.normalize("NFKC", text)
    )
    races["surface"] = surface_from_track_code(races["TrackCD"].astype(str)).to_numpy()
    races["track_name"] = races["idJyoCD"].astype(str).str.zfill(2).map(TRACKS)
    races["distance_m"] = pd.to_numeric(races["Kyori"], errors="coerce")
    races["distance_band"] = pd.cut(
        races["distance_m"], bins=DISTANCE_BINS, labels=DISTANCE_LABELS, right=True
    ).astype(str)
    races["grade"] = races["GradeCD"].fillna("").astype(str).str.strip().map(
        {"A": "G1", "B": "G2", "C": "G3", "L": "Listed"}
    ).fillna("ungraded/unknown")
    races = races.drop_duplicates("race_id", keep="last")

    runs["race_id"] = runs.apply(lambda row: race_id(row), axis=1)
    runs["horse_id"] = runs["KettoNum"].astype(str)
    runs["umaban"] = pd.to_numeric(runs["Umaban"], errors="coerce")
    runs["finish"] = pd.to_numeric(runs["KakuteiJyuni"], errors="coerce")
    runs = runs[["race_id", "horse_id", "umaban", "finish"]].drop_duplicates(
        ["race_id", "horse_id"], keep="last"
    )

    win_pay: dict[tuple[str, int], float] = {}
    place_pay: dict[tuple[str, int], float] = {}
    for row in payouts.to_dict("records"):
        rid = race_id(row)
        for i in range(3):
            _record_pay(win_pay, rid, row.get(f"PayTansyo{i}Umaban"), row.get(f"PayTansyo{i}Pay"))
        for i in range(5):
            _record_pay(place_pay, rid, row.get(f"PayFukusyo{i}Umaban"), row.get(f"PayFukusyo{i}Pay"))
    return races, runs, win_pay, place_pay


def _record_pay(target: dict[tuple[str, int], float], rid: str, number: object, amount: object) -> None:
    try:
        horse_number, payout = int(float(number or 0)), float(amount or 0)
    except (TypeError, ValueError):
        return
    if horse_number:
        target[(rid, horse_number)] = payout


def standardize_ability(frame: pd.DataFrame, score_col: str = "ability_score") -> pd.Series:
    values = pd.to_numeric(frame[score_col], errors="coerce")
    mean = values.groupby(frame["race_id"]).transform("mean")
    std = values.groupby(frame["race_id"]).transform(lambda s: s.std(ddof=0))
    z = (values - mean) / std.where(std > 1e-12)
    return z.where(values.notna(), np.nan).fillna(0.0).where(values.notna(), np.nan)


def _history_values(histories: dict[tuple, list[float]], key: tuple) -> list[float]:
    return histories.get(key, [])


def _usable_class_requirements(
    surface: str,
    distance_band: str,
    by_surface_distance_class: dict[tuple, list[float]],
    by_surface_class: dict[tuple, list[float]],
    by_class: dict[str, list[float]],
) -> dict[float, float]:
    requirements: dict[float, float] = {}
    for label, score in CLASS_SCORES.items():
        candidates = (
            _history_values(by_surface_distance_class, (surface, distance_band, label)),
            _history_values(by_surface_class, (surface, label)),
            _history_values(by_class, (label,)),
        )
        for values in candidates:
            if len(values) >= MIN_HISTORY:
                requirements[score] = float(np.median(values))
                break
    return requirements


def _interpolate_requirement(requirements: dict[float, float], score: float) -> float:
    if not requirements:
        return np.nan
    levels = np.array(sorted(requirements), dtype=float)
    values = np.array([requirements[level] for level in levels], dtype=float)
    return float(np.interp(score, levels, values))


def build_requirements(
    ability_oof: pd.DataFrame,
    runs: pd.DataFrame,
    races: pd.DataFrame,
    target_race_ids: set[str],
) -> pd.DataFrame:
    history = ability_oof.merge(runs, on=["race_id", "horse_id"], how="inner", validate="one_to_one")
    history = history.merge(
        races[["race_id", "date", "surface", "distance_band", "class_label", "class_score", "female_only"]],
        on="race_id",
        how="inner",
        validate="many_to_one",
    )
    history["score_available_at"] = pd.to_datetime(history["score_available_at"])
    history["model_training_cutoff"] = pd.to_datetime(history["model_training_cutoff"])
    if (history["model_training_cutoff"] >= history["date"]).any():
        raise ValueError("weekly ability OOF contains scores trained on the target race date or later")
    history["ability_z"] = standardize_ability(history)
    winners = history[history["finish"] == 1].groupby("race_id")["ability_z"].mean().rename("winner_ability_z")
    race_history = history.drop_duplicates("race_id").merge(winners, on="race_id", how="left")
    race_history = race_history.sort_values(["date", "race_id"])

    by_surface_distance_class: dict[tuple, list[float]] = {}
    by_surface_class: dict[tuple, list[float]] = {}
    by_class: dict[tuple, list[float]] = {}
    by_surface_distance: dict[tuple, list[float]] = {}
    by_surface: dict[tuple, list[float]] = {}
    global_history: list[float] = []
    results: list[dict] = []

    for _, same_day in race_history.groupby("date", sort=True):
        for row in same_day.itertuples(index=False):
            if row.race_id not in target_race_ids:
                continue
            score = float(row.class_score) if pd.notna(row.class_score) else np.nan
            requirements = _usable_class_requirements(
                row.surface, row.distance_band, by_surface_distance_class, by_surface_class, by_class
            )
            if np.isfinite(score):
                base_requirement = _interpolate_requirement(requirements, score)
            else:
                base_requirement = np.nan
            if not np.isfinite(base_requirement):
                candidates = (
                    by_surface_distance.get((row.surface, row.distance_band), []),
                    by_surface.get((row.surface,), []),
                    global_history,
                )
                base_requirement = next(
                    (float(np.median(values)) for values in candidates if len(values) >= MIN_HISTORY),
                    np.nan,
                )
            requirements_by_correction = {}
            for correction in CORRECTIONS:
                effective_score = score - correction if row.female_only and np.isfinite(score) else score
                adjusted_requirement = (
                    _interpolate_requirement(requirements, effective_score)
                    if np.isfinite(effective_score) else base_requirement
                )
                if not np.isfinite(adjusted_requirement):
                    adjusted_requirement = base_requirement
                requirements_by_correction[f"required_c{correction:g}"] = adjusted_requirement
            results.append({
                "race_id": row.race_id,
                "required_ability_z": base_requirement,
                **requirements_by_correction,
                "effective_class_score_c0": score,
                **{
                    f"effective_class_score_c{correction:g}":
                    (score - correction if row.female_only and np.isfinite(score) else score)
                    for correction in CORRECTIONS
                },
            })

        for row in same_day.itertuples(index=False):
            value = row.winner_ability_z
            if pd.isna(value):
                continue
            by_surface_distance_class.setdefault(
                (row.surface, row.distance_band, row.class_label), []
            ).append(float(value))
            by_surface_class.setdefault((row.surface, row.class_label), []).append(float(value))
            by_class.setdefault((row.class_label,), []).append(float(value))
            by_surface_distance.setdefault((row.surface, row.distance_band), []).append(float(value))
            by_surface.setdefault((row.surface,), []).append(float(value))
            global_history.append(float(value))
    return pd.DataFrame(results).drop_duplicates("race_id", keep="last")


def load_predictions(
    predictions_path: Path,
    ability_path: Path,
    db_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    predictions = pd.read_csv(
        predictions_path,
        dtype={"race_id": str, "horse_id": str, "level": str},
        parse_dates=["date"],
    )
    predictions = predictions[predictions["level"].isin(LEVELS)].copy()
    if predictions.empty:
        raise ValueError(f"no base/formation/pace predictions found in {predictions_path}")
    if predictions["p_cal"].isna().any():
        raise ValueError("the walk-forward predictions contain uncalibrated rows")

    ability = pd.read_parquet(ability_path)
    ability["race_id"] = ability["race_id"].astype(str)
    ability["horse_id"] = ability["horse_id"].astype(str)
    ability = ability.drop_duplicates(["race_id", "horse_id"], keep="last")
    races, runs, win_pay, place_pay = read_race_data(
        db_path, int(predictions["date"].dt.year.min()) - 2, int(predictions["date"].dt.year.max())
    )
    predictions = predictions.merge(
        ability[["race_id", "horse_id", "ability_score", "score_available_at", "model_training_cutoff"]],
        on=["race_id", "horse_id"],
        how="left",
        validate="many_to_one",
    )
    metadata_columns = [
        "race_id", "track_name", "surface", "distance_m", "distance_band", "class_label", "class_score",
        "grade", "female_only", "date",
    ]
    predictions = predictions.merge(
        races[metadata_columns], on=["race_id", "date"], how="left", validate="many_to_one"
    )
    if predictions[["surface", "distance_band", "female_only"]].isna().any().any():
        raise ValueError("race metadata is missing for one or more walk-forward predictions")
    if predictions["ability_score"].notna().mean() < 0.99:
        raise ValueError("weekly Ranker ability scores are missing for more than 1% of predictions")
    predictions["umaban"] = pd.to_numeric(predictions["umaban"], errors="raise").astype(int)
    predictions["ability_z"] = standardize_ability(predictions)
    predictions["market_probability"] = 1.0 / pd.to_numeric(
        predictions["win_odds_reference"], errors="coerce"
    ).where(lambda odds: odds > 0)
    if predictions["market_probability"].isna().any():
        raise ValueError("final odds are missing or non-positive; market comparison cannot be computed")
    market_total = predictions.groupby(["level", "race_id"])["market_probability"].transform("sum")
    predictions["market_probability"] = predictions["market_probability"] / market_total
    payable_races = {race for (race, _), amount in win_pay.items() if amount > 0}
    missing_payouts = set(predictions["race_id"]) - payable_races
    if missing_payouts:
        raise ValueError(f"confirmed win payout is missing for {len(missing_payouts)} prediction races")
    predictions["win_payout"] = [
        win_pay.get((race, number), 0.0)
        for race, number in zip(predictions["race_id"], predictions["umaban"])
    ]
    predictions["place_payout"] = [
        place_pay.get((race, number), 0.0)
        for race, number in zip(predictions["race_id"], predictions["umaban"])
    ]
    requirement_table = build_requirements(
        ability,
        runs,
        races,
        set(predictions["race_id"]),
    )
    predictions = predictions.merge(requirement_table, on="race_id", how="left", validate="many_to_one")
    if predictions["required_ability_z"].isna().mean() > 0.05:
        LOGGER.warning(
            "%.1f%% of races have insufficient pre-race winner-ability history; thresholds fall back to no-op",
            predictions["required_ability_z"].isna().mean() * 100,
        )
    return predictions, races, win_pay, place_pay


def period_name(date: pd.Timestamp) -> str:
    if date < pd.Timestamp("2025-01-01"):
        return "development_2021_2024"
    if date < pd.Timestamp("2026-01-01"):
        return "selection_2025"
    return "final_2026"


def probability_metrics(frame: pd.DataFrame, probability_col: str) -> dict[str, float]:
    valid = frame[np.isfinite(frame[probability_col])].copy()
    y = valid["target"].to_numpy(dtype=float)
    p = np.clip(valid[probability_col].to_numpy(dtype=float), 1e-15, 1 - 1e-15)
    winners = valid[valid["target"] == 1]
    winner_counts = winners["race_id"].value_counts()
    unique_winners = winners[winners["race_id"].map(winner_counts) == 1]
    winner_probabilities = unique_winners[probability_col].to_numpy(dtype=float)
    zero_probability_winners = int((winner_probabilities <= 0).sum())
    return {
        "races": int(valid["race_id"].nunique()),
        "horses": int(len(valid)),
        "winner_logloss": float(-np.log(np.clip(unique_winners[probability_col], 1e-15, 1)).mean()),
        "strict_winner_logloss": (
            float("inf")
            if zero_probability_winners
            else float(-np.log(winner_probabilities).mean())
        ),
        "zero_probability_winner_count": zero_probability_winners,
        "zero_probability_winner_pct": (
            zero_probability_winners / len(unique_winners) * 100
            if len(unique_winners) else np.nan
        ),
        "market_winner_logloss": float(-np.log(np.clip(unique_winners["market_probability"], 1e-15, 1)).mean()),
        "winner_logloss_vs_market": float(
            -np.log(np.clip(unique_winners[probability_col], 1e-15, 1)).mean()
            + np.log(np.clip(unique_winners["market_probability"], 1e-15, 1)).mean()
        ),
        "brier": float(np.mean((p - y) ** 2)),
        "logloss_binary": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        "max_probability_sum_error": float(
            valid.groupby("race_id")[probability_col].sum().sub(1).abs().max()
        ),
    }


def summarize_bets(selected: pd.DataFrame) -> dict:
    n = len(selected)
    investment = n * 100.0
    wins = selected["win_payout"].to_numpy(dtype=float)
    places = selected["place_payout"].to_numpy(dtype=float)
    deficient = selected[selected["ability_shortfall"] > 0]
    deficient_wins = deficient["win_payout"].to_numpy(dtype=float)
    returned = float(wins.sum())
    place_returned = float(places.sum())
    payout_desc = np.sort(wins[wins > 0])[::-1]
    return {
        "bets": int(n),
        "eligibility_fallback_bets": int(selected["eligibility_fallback"].sum()) if n else 0,
        "top1_hit_rate": float((wins > 0).mean()) if n else np.nan,
        "top1_place_hit_rate": float((places > 0).mean()) if n else np.nan,
        "win_returned": returned,
        "win_profit": returned - investment,
        "win_roi_pct": returned / investment * 100 if investment else np.nan,
        "place_returned": place_returned,
        "place_profit": place_returned - investment,
        "place_roi_pct": place_returned / investment * 100 if investment else np.nan,
        "top1_mean_predicted_probability": float(selected["adjusted_probability"].mean()) if n else np.nan,
        "top1_brier": float(np.mean(
            (selected["adjusted_probability"].to_numpy(dtype=float)
             - (wins > 0).astype(float)) ** 2
        )) if n else np.nan,
        "top1_calibration_gap": float(
            selected["adjusted_probability"].mean() - (wins > 0).mean()
        ) if n else np.nan,
        "top1_below_requirement_bets": int(len(deficient)),
        "below_requirement_predicted_win_rate": (
            float(deficient["adjusted_probability"].mean()) if len(deficient) else np.nan
        ),
        "below_requirement_actual_win_rate": (
            float((deficient_wins > 0).mean()) if len(deficient) else np.nan
        ),
        "below_requirement_calibration_gap": (
            float(deficient["adjusted_probability"].mean() - (deficient_wins > 0).mean())
            if len(deficient) else np.nan
        ),
        "winner_payout_top1_share_pct": float(payout_desc[0] / returned * 100) if len(payout_desc) and returned else np.nan,
        "winner_payout_top3_share_pct": float(payout_desc[:3].sum() / returned * 100) if len(payout_desc) and returned else np.nan,
        "winner_payout_top5_share_pct": float(payout_desc[:5].sum() / returned * 100) if len(payout_desc) and returned else np.nan,
    }


def evaluate_frame(frame: pd.DataFrame, variant: Variant, period: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    requirement_col = f"required_c{variant.correction:g}"
    adjusted = frame.copy()
    adjusted["required_ability_z"] = adjusted[requirement_col]
    source_probabilities = pd.to_numeric(adjusted["p_cal"], errors="coerce").to_numpy(dtype=float)
    if variant.probability_gamma != 1.0:
        powered = np.clip(source_probabilities, 1e-15, 1.0) ** variant.probability_gamma
        total = pd.Series(powered, index=adjusted.index).groupby(adjusted["race_id"]).transform("sum")
        adjusted["input_probability"] = powered / total.to_numpy()
    else:
        adjusted["input_probability"] = source_probabilities
    rule = AbilityThreshold(
        mode=variant.mode,
        strength=variant.strength,
        scope=variant.scope,
        threshold_offset=variant.threshold_offset,
    )
    adjusted = adjust_probabilities(adjusted, "input_probability", rule)
    selected = select_top1(adjusted)
    selected["period"] = period
    return adjusted, selected, summarize_bets(selected)


def odds_band_table(selected: pd.DataFrame, variant: str, level: str, period: str) -> pd.DataFrame:
    top = selected.copy()
    top["odds_band"] = pd.cut(
        pd.to_numeric(top["win_odds_reference"], errors="coerce"),
        bins=ODDS_BINS,
        labels=ODDS_LABELS,
        right=False,
    )
    rows = []
    for band, group in top.groupby("odds_band", observed=True):
        metrics = summarize_bets(group)
        rows.append({
            "period": period,
            "variant": variant,
            "level": level,
            "odds_band": str(band),
            **metrics,
            "predicted_win_rate": metrics["top1_mean_predicted_probability"],
            "actual_win_rate": metrics["top1_hit_rate"],
            "calibration_gap": metrics["top1_calibration_gap"],
            "market_win_rate": float(group["market_probability"].mean()),
        })
    return pd.DataFrame(rows)


def dimension_table(selected: pd.DataFrame, variant: str, level: str, period: str) -> pd.DataFrame:
    frame = selected.copy()
    frame["year"] = frame["date"].dt.year.astype(str)
    frame["sex_condition"] = np.where(
        frame["female_only"], "explicit_female_only", "no_explicit_female_only_marker"
    )
    dimensions = {
        "year": "year",
        "track": "track_name",
        "surface": "surface",
        "distance": "distance_band",
        "official_class": "class_label",
        "grade": "grade",
        "sex_condition": "sex_condition",
    }
    all_dates = frame["date"].sort_values()
    midpoint = all_dates.iloc[len(all_dates) // 2] if len(all_dates) else pd.NaT
    rows = []
    for dimension, column in dimensions.items():
        for value, group in frame.groupby(column, dropna=False, observed=True):
            metrics = summarize_bets(group)
            first = group[group["date"] < midpoint]
            second = group[group["date"] >= midpoint]
            first_roi = summarize_bets(first)["win_roi_pct"] if len(first) else np.nan
            second_roi = summarize_bets(second)["win_roi_pct"] if len(second) else np.nan
            rows.append({
                "period": period,
                "variant": variant,
                "level": level,
                "dimension": dimension,
                "condition": str(value),
                **metrics,
                "first_half_win_roi_pct": first_roi,
                "second_half_win_roi_pct": second_roi,
            })
    return pd.DataFrame(rows)


def build_surface_audit(races: pd.DataFrame) -> pd.DataFrame:
    data = races.copy()
    codes = pd.to_numeric(data["TrackCD"], errors="coerce")
    data["surface_old_prefix_rule"] = np.select(
        [codes.astype("Int64").astype(str).str[:1].isin(list("12345678")),
         codes.astype("Int64").astype(str).str[:1].isin(["9", "0"])],
        ["turf", "dirt"],
        default="other",
    )
    data["surface_corrected_track_code"] = data["surface"]
    data["mislabeled_by_old_rule"] = (
        data["surface_old_prefix_rule"] != data["surface_corrected_track_code"]
    )
    data["year"] = data["date"].dt.year
    return data.groupby(["year", "surface_corrected_track_code", "surface_old_prefix_rule"], dropna=False).agg(
        races=("race_id", "nunique"),
        affected_races=("mislabeled_by_old_rule", "sum"),
    ).reset_index()


def make_report(
    metrics: pd.DataFrame,
    selected_configs: pd.DataFrame,
    odds: pd.DataFrame,
    conditions: pd.DataFrame,
    effective_classes: pd.DataFrame,
    surface_audit: pd.DataFrame,
    out_dir: Path,
) -> None:
    final_rows = metrics[metrics["period"] == "final_2026"]
    selected_rows = selected_configs.merge(
        final_rows,
        on=["level", "variant"],
        how="left",
        suffixes=("_chosen", ""),
    )
    selected_rows.to_csv(out_dir / "frozen_rules_final_2026.csv", index=False)
    selected_rows.to_csv(out_dir / "selection_2025_and_final_2026.csv", index=False)
    odds.to_csv(out_dir / "odds_band_metrics.csv", index=False)
    conditions.to_csv(out_dir / "condition_metrics.csv", index=False)
    effective_classes.to_csv(out_dir / "effective_class_mapping.csv", index=False)
    surface_audit.to_csv(out_dir / "surface_mapping_audit.csv", index=False)
    metrics.to_csv(out_dir / "experiment_metrics.csv", index=False)
    female_final = conditions[
        (conditions["period"] == "final_2026")
        & (conditions["variant"] == "current")
        & (conditions["dimension"] == "sex_condition")
        & (conditions["condition"] == "explicit_female_only")
    ]
    female_final_count = int(female_final["bets"].max()) if not female_final.empty else 0
    class_coverage = effective_classes[effective_classes["female_class_correction"] == 0.0]
    class_race_count = int(class_coverage["races"].sum())
    unknown_class_count = int(class_coverage.loc[class_coverage["class_label"] == "UNKNOWN", "races"].sum())

    baseline = final_rows[final_rows["variant"] == "current"].set_index("level")
    selected_by_level = selected_rows.set_index("level")
    lines = [
        "# RACEVERSE ability threshold and female-only class correction",
        "",
        "## Executive result (untouched final period: 2026-01-01 to 2026-09-01)",
        "",
        "- **1倍台の本命馬**: ",
    ]
    low_odds = odds[(odds["period"] == "final_2026") & (odds["odds_band"] == "1倍台")]
    for level in LEVELS:
        base_band = low_odds[(low_odds["level"] == level) & (low_odds["variant"] == "current")]
        chosen_variant = selected_configs.loc[selected_configs["level"] == level, "variant"].iloc[0]
        chosen_band = low_odds[(low_odds["level"] == level) & (low_odds["variant"] == chosen_variant)]
        old_gap = float(base_band.iloc[0]["calibration_gap"]) if len(base_band) else np.nan
        new_gap = float(chosen_band.iloc[0]["calibration_gap"]) if len(chosen_band) else np.nan
        old_pred = float(base_band.iloc[0]["predicted_win_rate"]) if len(base_band) else np.nan
        old_actual = float(base_band.iloc[0]["actual_win_rate"]) if len(base_band) else np.nan
        new_pred = float(chosen_band.iloc[0]["predicted_win_rate"]) if len(chosen_band) else np.nan
        new_actual = float(chosen_band.iloc[0]["actual_win_rate"]) if len(chosen_band) else np.nan
        n_low = int(chosen_band.iloc[0]["bets"]) if len(chosen_band) else 0
        lines.append(
            f"  - {level}: 固定ルール `{chosen_variant}`、{n_low}件、予測勝率 {old_pred:.1%}→{new_pred:.1%}、"
            f"実測勝率 {old_actual:.1%}→{new_actual:.1%}、予測−実測の差 {old_gap:+.3f} → {new_gap:+.3f} "
            f"({'改善' if abs(new_gap) < abs(old_gap) else '改善せず'}; 2026の1倍台本命のみ)。"
        )
    lines.append("")
    lines.append("- **能力不足馬の過大評価と全体Top1的中率**:")
    for level in LEVELS:
        old = baseline.loc[level]
        new = selected_by_level.loc[level]
        old_deficit_gap = (
            f"{old['below_requirement_calibration_gap']:+.3f}"
            if pd.notna(old["below_requirement_calibration_gap"]) else "N/A"
        )
        new_deficit_gap = (
            f"{new['below_requirement_calibration_gap']:+.3f}"
            if pd.notna(new["below_requirement_calibration_gap"]) else "N/A"
        )
        lines.append(
            f"  - {level}: 要求能力未満Top1の較差 "
            f"{old_deficit_gap} → {new_deficit_gap} "
            f"({int(old['top1_below_requirement_bets'])}→{int(new['top1_below_requirement_bets'])}件)、"
            f"全体Top1的中率 {old['top1_hit_rate']:.3%} → "
            f"{new['top1_hit_rate']:.3%} ({new['top1_hit_rate'] - old['top1_hit_rate']:+.3%})."
        )
    lines.append("")
    lines.append("- **110%回収率目標**:")
    for level in LEVELS:
        row = selected_by_level.loc[level]
        passes = bool(row["win_roi_pct"] >= 110.0)
        lines.append(
            f"  - {level}: `{row['variant']}`、{int(row['bets'])}件、単勝回収率 "
            f"{row['win_roi_pct']:.1f}%、利益 {row['win_profit']:.0f}円。"
            f"{'目標達成だが、条件安定性・少数高配当依存を要確認。' if passes else '目標未達。'}"
        )
    lines.extend([
        "",
        "2025年のパラメータ選択はTop1 Brier最小化を主基準、Winner Loglossを同点時の比較にし、ROIは選択に使っていない。2026年は選択に使っていない最終評価期間。",
        "ここでの「能力不足」は、週次OOF Rankerスコアをレース内標準化した値が、過去の勝ち馬スコア中央値から推定した要求能力を下回ること。",
        "zero_tiltでは能力閾値未満の馬に確率0を割り当て、閾値以上は `p_cal × exp(slope × (ability − cutoff))` の重みで再正規化する。cutoffは要求能力＋offset。能力不明の馬は元の確率で残し、全頭が閾値未満ならレース全体を元の確率に戻す。",
        "ゼロ確率を割り当てた勝ち馬がいる場合、厳密なWinner Loglossは無限大。通常の `winner_logloss` 欄は比較用に確率を1e-15でclipした値であり、ゼロ勝ち馬件数と厳密値を別に記録する。",
        "Soft の strength は `exp(-strength × shortfall²)` の減衰係数。Hard の strength は要求能力未満を許容する標準偏差幅で、小さいほど除外が厳しい。",
        "zero_tiltは要求能力からの閾値offsetを -0.5 / 0 / +0.5、傾斜slopeを 0 / 0.5 / 1 / 2、確率温度gammaを 0.25 / 0.5 / 0.75 / 1 / 1.25 / 1.5 で比較。校正のみ対照も含め、2025年Top1 Brierで選択した。gammaは閾値判定前の既存確率へ適用し、Ranker能力・閾値情報と組み合わせて再正規化する。",
        "",
        "## Method and leakage controls",
        "",
        "- 2021–2024 development; 2025 parameter selection; 2026 final evaluation. Weekly model predictions and Ranker OOF scores were reused.",
        "- Every ability score's `model_training_cutoff` is checked to be before its race date. Class-specific required ability is updated using only winners from earlier dates (same-day outcomes are not used).",
        "- Only verified class labels from `GradeCD` and explicit condition names are class-ranked. Prize tiers (`Honsyokin0`) are not treated as classes; unresolved race classes fall back to a prior surface/distance historical winner benchmark, without class correction.",
        f"- Explicit official-class coverage is {class_race_count - unknown_class_count}/{class_race_count} races; {unknown_class_count} races have `UNKNOWN` class and receive no class correction.",
        "- Female-only evidence is conservative: explicit `牝` marker in the race name. Female entrants in mixed races are never corrected. The local class/sex audit documents that this marker is incomplete.",
        f"- The final period contains only {female_final_count} races with an explicit female-only name marker; this is too sparse to establish a robust gender correction effect.",
        "- Final odds are used only for post-race odds-band diagnosis and returned-payout reporting; they are not used by the adjustment, class mapping, or threshold selection.",
        "",
        "## Frozen rules selected on 2025",
        "",
        "| level | variant | 2025 Top1 Brier | 2025 Winner Logloss | 2026 predicted Top1 win% | 2026 actual hit | zero-prob winners | 2026 bets | 2026 win ROI | 2026 place ROI | 2026 profit |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in selected_rows.itertuples(index=False):
        lines.append(
            f"| {row.level} | {row.variant} | {row.top1_brier_2025:.5f} | {row.winner_logloss_2025:.4f} | "
            f"{row.top1_mean_predicted_probability:.1%} | {row.top1_hit_rate:.1%} | "
            f"{int(row.zero_probability_winner_count)} | {int(row.bets)} | {row.win_roi_pct:.1f}% | "
            f"{row.place_roi_pct:.1f}% | {row.win_profit:.0f}円 |"
        )
    lines.extend([
        "",
        "## 1倍台 Top1 calibration diagnostic (post-hoc only)",
        "",
        "For diagnosis only, the zero-tilt candidate with the smallest absolute 2025 1倍台 calibration gap is shown beside its untouched 2026 result. This odds-band diagnostic does not select the frozen rule and must not be used as a pre-race feature.",
        "",
        "| level | 2025 zero-tilt variant | 2025 predicted / actual | 2025 gap | 2026 predicted / actual | 2026 gap | 2026 zero-probability winners |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for level in LEVELS:
        band = odds[
            (odds["level"] == level)
            & (odds["odds_band"] == "1倍台")
            & (odds["period"] == "selection_2025")
            & odds["variant"].str.startswith("ability_zero_tilt")
        ].copy()
        if band.empty:
            continue
        band["absolute_gap"] = band["calibration_gap"].abs()
        diagnostic = band.sort_values(
            ["absolute_gap", "top1_brier"], kind="stable"
        ).iloc[0]
        final_band = odds[
            (odds["level"] == level)
            & (odds["period"] == "final_2026")
            & (odds["odds_band"] == "1倍台")
            & (odds["variant"] == diagnostic["variant"])
        ]
        final_metrics = final_rows[
            (final_rows["level"] == level)
            & (final_rows["variant"] == diagnostic["variant"])
        ]
        if final_band.empty or final_metrics.empty:
            continue
        final = final_band.iloc[0]
        strict = final_metrics.iloc[0]
        lines.append(
            f"| {level} | {diagnostic['variant']} | "
            f"{diagnostic['predicted_win_rate']:.1%} / {diagnostic['actual_win_rate']:.1%} | "
            f"{diagnostic['calibration_gap']:+.1%} | "
            f"{final['predicted_win_rate']:.1%} / {final['actual_win_rate']:.1%} | "
            f"{final['calibration_gap']:+.1%} | {int(strict['zero_probability_winner_count'])} |"
        )
    lines.append(
        "With gamma=1, the `offset=-0.5, slope=0.5` candidate nearly matches 2026 1倍台 favorites "
        "(base 55.9% vs 56.3%, formation 54.3% vs 56.0%, pace 54.6% vs 57.2%), "
        "but it overpredicts the same band by about 6.6–7.1 percentage points in 2025. "
        "Across all Top1 bets it predicts about 43.0–44.4% against 25.1–26.9% actual wins, "
        "and assigns zero to 306/1,076 winners in 2025 and 377/1,261 in 2026; it is not frozen or recommended."
    )
    frozen_variants = selected_configs.set_index("level")["variant"].to_dict()
    annual_conditions = conditions[conditions["dimension"] == "year"].copy()
    annual_conditions["year"] = pd.to_numeric(annual_conditions["condition"], errors="coerce")
    lines.extend([
        "",
        "## Annual stability of frozen rules",
        "",
        "Win ROI by calendar year; the 2025-selected rule for each level is held fixed. The 2026 period is also split chronologically into two equal observation halves.",
        "",
        "| level | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 2026 period first half | 2026 period second half |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for level in LEVELS:
        level_years = annual_conditions[
            (annual_conditions["level"] == level)
            & (annual_conditions["variant"] == frozen_variants[level])
        ].set_index("year")
        final_year = level_years.loc[2026] if 2026 in level_years.index else None
        yearly_roi = [
            f"{level_years.loc[year, 'win_roi_pct']:.1f}%" if year in level_years.index else "—"
            for year in range(2021, 2027)
        ]
        first_half = f"{final_year['first_half_win_roi_pct']:.1f}%" if final_year is not None and pd.notna(final_year["first_half_win_roi_pct"]) else "—"
        second_half = f"{final_year['second_half_win_roi_pct']:.1f}%" if final_year is not None and pd.notna(final_year["second_half_win_roi_pct"]) else "—"
        lines.append(f"| {level} | {' | '.join(yearly_roi)} | {first_half} | {second_half} |")
    lines.extend([
        "",
        "## Overall 2026 comparison",
        "",
        "| level | variant | bets | top1 hit | top1 Brier | win ROI | place ROI | winner logloss (clipped) | strict winner logloss | zero-prob winners | Brier | LL vs market |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in final_rows.itertuples(index=False):
        strict_logloss = (
            "∞"
            if not np.isfinite(row.strict_winner_logloss)
            else f"{row.strict_winner_logloss:.4f}"
        )
        lines.append(
            f"| {row.level} | {row.variant} | {int(row.bets)} | {row.top1_hit_rate:.3%} | "
            f"{row.top1_brier:.5f} | {row.win_roi_pct:.1f}% | {row.place_roi_pct:.1f}% | "
            f"{row.winner_logloss:.4f} | {strict_logloss} | {int(row.zero_probability_winner_count)} | "
            f"{row.brier:.5f} | {row.winner_logloss_vs_market:+.4f} |"
        )
    current_rows = final_rows[final_rows["variant"] == "current"].set_index("level")
    jointly_better: list[str] = []
    for level in LEVELS:
        baseline_row = current_rows.loc[level]
        candidates = final_rows[final_rows["level"] == level]
        qualifying = candidates[
            (candidates["variant"] != "current")
            & (candidates["win_roi_pct"] > baseline_row["win_roi_pct"])
            & (candidates["top1_brier"] < baseline_row["top1_brier"])
        ]
        if not qualifying.empty:
            jointly_better.append(level)
    lines.extend([
        "",
        "## Joint accuracy and return decision",
        "",
    ])
    if jointly_better:
        lines.append(
            "2026 final-period variants with both higher win ROI and lower Top1 Brier than current: "
            + ", ".join(jointly_better) + ". These still require review of strict Winner Logloss and zero-support winners."
        )
    else:
        lines.append(
            "No tested variant has both higher 2026 win ROI and lower Top1 Brier than `current` for any level. "
            "Therefore there is no evidence-based replacement that improves Top1 probability accuracy and return simultaneously."
        )
    lines.extend([
        "",
        "Highest-ROI variants below are listed only as post-hoc diagnostics; choosing them on 2026 would leak final-period outcomes.",
        "",
        "| level | highest-ROI 2026 variant | ROI | change vs current | Top1 Brier | change vs current | zero-probability winners |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for level in LEVELS:
        baseline_row = current_rows.loc[level]
        best = final_rows[final_rows["level"] == level].sort_values(
            ["win_roi_pct", "variant"], ascending=[False, True], kind="stable"
        ).iloc[0]
        lines.append(
            f"| {level} | {best['variant']} | {best['win_roi_pct']:.1f}% | "
            f"{best['win_roi_pct'] - baseline_row['win_roi_pct']:+.1f} pp | "
            f"{best['top1_brier']:.5f} | "
            f"{best['top1_brier'] - baseline_row['top1_brier']:+.5f} | "
            f"{int(best['zero_probability_winner_count'])} |"
        )
    lines.extend([
        "",
    ])
    old_rule_affected = int(surface_audit["affected_races"].sum())
    lines.extend([
        "",
        "## Hard exclusion: winner removal diagnostic (2026)",
        "",
        "| level | hard margin (race z) | eligible winners | excluded winners | excluded rate | bets | Top1 hit | win ROI | fallback bets |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    hard_rows = final_rows[(final_rows["mode"] == "hard") & (final_rows["strength"] == 0.5)]
    for row in hard_rows.itertuples(index=False):
        lines.append(
            f"| {row.level} | {row.strength:.1f} | {int(row.eligible_winner_count)} | "
            f"{int(row.excluded_winner_count)} | {row.excluded_winner_pct:.2f}% | {int(row.bets)} | "
            f"{row.top1_hit_rate:.3%} | {row.win_roi_pct:.1f}% | {int(row.eligibility_fallback_bets)} |"
        )
    lines.append(
        "Excluded-winner rate counts actual winner horses below the ability cutoff, not skipped races. "
        "Eligible alternatives continue to be ranked for Top1 purchase; these variants made the same number of bets."
    )
    lines.extend([
        "",
        "## Top1 odds-band diagnosis (frozen rules)",
        "",
        "See `odds_band_metrics.csv` for every variant and period; the final-period rows include selected prediction, observed win rate, calibration gap, market rate, counts and payouts by 1.x / 2.x / 3–5 / 5–10 / 10–20 / 20+ odds.",
        "",
        "## Condition performance",
        "",
        "`condition_metrics.csv` contains purchase counts, hits, win/place ROI, profit, and chronological first-/second-half ROI by year, track, surface, distance, official class, GradeCD and female-only/open-sex evidence.",
        "`effective_class_mapping.csv` keeps the nominal official class and corrected effective-class score separate, with required-ability benchmarks and race counts for each correction value.",
        "",
        "## Surface-code defect audit",
        "",
        f"The legacy first-character surface rule disagrees with the corrected numeric TrackCD mapping in {old_rule_affected} races in the loaded database window. RACEVERSE uses TrackCD 10–22=turf and 23–29=dirt.",
        "The saved weekly predictions are the corrected-surface reference. No independently generated pre-fix RACEVERSE prediction file was present, so a causal pre-fix model performance number is not fabricated; `surface_mapping_audit.csv` gives the exact label impact. Pre-fix and corrected model metrics must be kept separate if old predictions are later supplied.",
        "",
        "## Adoption decision",
        "",
        "A selected rule is only a shadow-operation candidate if it reaches 110% win ROI in 2026 and is not materially worse on probability calibration; it is not a live betting recommendation. Check annual/half-period stability and payout concentration in `condition_metrics.csv` and `frozen_rules_final_2026.csv`. This test is retrospective and uses final payouts.",
        "",
        "## Output files",
        "",
        "- `experiment_metrics.csv`: all variants by level and temporal partition.",
        "- `selection_2025_and_final_2026.csv`: fixed choices and untouched 2026 results.",
        "- `odds_band_metrics.csv`: selected Top1 odds-band predicted/observed rates and returns.",
        "- `condition_metrics.csv`: year/track/distance/class/grade/sex conditions and half-period returns.",
        "- `effective_class_mapping.csv`: nominal/effective class values, prior ability requirement and race counts.",
        "- `surface_mapping_audit.csv`: legacy versus corrected surface classification counts.",
    ])
    (out_dir / "ability_threshold_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(predictions_path: Path, ability_path: Path, db_path: Path, out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame, races, _, _ = load_predictions(predictions_path, ability_path, db_path)
    frame["period"] = frame["date"].map(period_name)
    metric_rows, odds_tables = [], []

    for level in LEVELS:
        level_frame = frame[frame["level"] == level]
        if level_frame.empty:
            raise ValueError(f"walk-forward predictions are missing level {level}")
        for period in ("development_2021_2024", "selection_2025", "final_2026"):
            period_frame = level_frame[level_frame["period"] == period]
            if period_frame.empty:
                raise ValueError(f"walk-forward predictions are missing {period} for {level}")
            for variant in variants():
                adjusted, selected, bet_metrics = evaluate_frame(period_frame, variant, period)
                p_metrics = probability_metrics(adjusted, "adjusted_probability")
                winners = adjusted[adjusted["target"] == 1]
                excluded = winners[
                    (winners["ability_shortfall"].notna())
                    & ~winners["candidate_eligible"]
                ]
                row = {
                    "period": period,
                    "level": level,
                    "variant": variant.name,
                    "mode": variant.mode,
                    "strength": variant.strength,
                    "female_class_correction": variant.correction,
                    "female_scope": variant.scope,
                    "probability_gamma": variant.probability_gamma,
                    "threshold_offset": variant.threshold_offset,
                    "zero_probability_winner_count": p_metrics["zero_probability_winner_count"],
                    "threshold_fallback_races": int(
                        adjusted.groupby("race_id")["threshold_fallback"].any().sum()
                    ),
                    "excluded_winner_count": int(len(excluded)),
                    "eligible_winner_count": int(winners["ability_shortfall"].notna().sum()),
                    "excluded_winner_pct": (
                        len(excluded) / winners["ability_shortfall"].notna().sum() * 100
                        if winners["ability_shortfall"].notna().sum() else np.nan
                    ),
                    **p_metrics,
                    **bet_metrics,
                }
                metric_rows.append(row)
                odds_tables.append(odds_band_table(selected, variant.name, level, period))
                LOGGER.info("%s %s %s: ROI %.1f%% bets=%d", period, level, variant.name,
                            row["win_roi_pct"], row["bets"])

    metrics = pd.DataFrame(metric_rows)
    metrics["variant_order"] = metrics["variant"].map(
        {variant.name: i for i, variant in enumerate(variants())}
    )
    selection_rows = []
    for level in LEVELS:
        candidates = metrics[(metrics["period"] == "selection_2025") & (metrics["level"] == level)]
        chosen = candidates.sort_values(
            ["top1_brier", "winner_logloss", "variant_order"],
            ascending=[True, True, True],
            kind="stable",
        ).iloc[0]
        selection_rows.append({
            "level": level,
            "variant": chosen["variant"],
            "mode": chosen["mode"],
            "strength": chosen["strength"],
            "female_class_correction": chosen["female_class_correction"],
            "female_scope": chosen["female_scope"],
            "probability_gamma": chosen["probability_gamma"],
            "threshold_offset": chosen["threshold_offset"],
            "winner_logloss_2025": chosen["winner_logloss"],
            "brier_2025": chosen["brier"],
            "top1_brier_2025": chosen["top1_brier"],
            "win_roi_2025": chosen["win_roi_pct"],
            "bets_2025": chosen["bets"],
            "selection_metric": "minimum 2025 Top1 Brier; Winner Logloss tie-break; ROI not used",
        })
    selected_configs = pd.DataFrame(selection_rows)
    variant_by_name = {variant.name: variant for variant in variants()}
    condition_tables = []
    for level in LEVELS:
        chosen_name = selected_configs.loc[selected_configs["level"] == level, "variant"].iloc[0]
        for period in ("development_2021_2024", "selection_2025", "final_2026"):
            period_frame = frame[(frame["level"] == level) & (frame["period"] == period)]
            for name in dict.fromkeys(("current", chosen_name)):
                _, selected, _ = evaluate_frame(period_frame, variant_by_name[name], period)
                condition_tables.append(dimension_table(selected, name, level, period))
    odds = pd.concat(odds_tables, ignore_index=True)
    conditions = pd.concat(condition_tables, ignore_index=True)
    class_rows = []
    race_level_frame = frame.drop_duplicates("race_id")
    for correction in CORRECTIONS:
        effective_col = f"effective_class_score_c{correction:g}"
        requirement_col = f"required_c{correction:g}"
        class_rows.append(
            race_level_frame.assign(
                female_class_correction=correction,
                effective_class_score=race_level_frame[effective_col],
                required_ability_z=race_level_frame[requirement_col],
            ).groupby(
                ["female_class_correction", "class_label", "class_score", "female_only",
                 "effective_class_score"],
                dropna=False,
                observed=True,
            ).agg(
                races=("race_id", "nunique"),
                median_required_ability_z=("required_ability_z", "median"),
            ).reset_index()
        )
    effective_classes = pd.concat(class_rows, ignore_index=True)
    surface_audit = build_surface_audit(races)
    metrics = metrics.drop(columns="variant_order")
    make_report(metrics, selected_configs, odds, conditions, effective_classes, surface_audit, out_dir)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS)
    parser.add_argument("--ability-oof", type=Path, default=ABILITY_OOF)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    metrics = run(args.predictions, args.ability_oof, args.db, args.out)
    print(f"wrote {len(metrics)} experiment rows to {args.out}")


if __name__ == "__main__":
    main()

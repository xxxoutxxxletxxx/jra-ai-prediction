#!/usr/bin/env python3
"""Feature audit for the existing monthly Ranker walk-forward baseline.

Uses LightGBM pred_contrib (TreeSHAP contributions) while preserving the exact
monthly target filtering and prior-only training used by the saved baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker

try:
    from src import ranker_walk_forward_backtest as wf
except ModuleNotFoundError:
    import ranker_walk_forward_backtest as wf

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "reports" / "ranker_feature_audit"
TOP_FEATURES = 50
DIRECTION_FEATURES = 30


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def feature_group(feature: str) -> str:
    if feature.startswith(("career_", "recent", "races_last")):
        return "career_recent_form"
    if "margin" in feature or "finish" in feature or "performance" in feature:
        return "finish_margin_performance"
    if "winner_strength" in feature or "field_strength" in feature or "opponent" in feature:
        return "opponent_field_strength"
    if "prize" in feature or "class" in feature:
        return "race_class_prize"
    if any(token in feature for token in ("pace", "position", "front", "rail", "draw", "gate", "setup")):
        return "pace_position_draw"
    if any(token in feature for token in ("distance", "course", "track_condition", "season", "interval", "weight")):
        return "course_distance_fit"
    if feature.startswith("jockey"):
        return "jockey"
    return "other"


def fit_model(train: pd.DataFrame, test: pd.DataFrame, features: list[str]):
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)
    train_x, test_x = wf.encode_train_test(ordered, test, features)
    groups = ordered.groupby("race_id", sort=False).size().tolist()
    relevance = ordered.groupby("race_id")["actual_rank"].transform("max") - ordered["actual_rank"] + 1
    model = LGBMRanker(objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3], n_estimators=180,
                       learning_rate=0.04, num_leaves=15, max_depth=5, min_child_samples=80,
                       reg_lambda=2.0, random_state=wf.SEED, verbosity=-1)
    model.fit(train_x, relevance.to_numpy(), group=groups)
    return model, train_x, test_x


def encoded_mapping(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> list[str]:
    """Reconstruct the encoded feature names in the same deterministic order."""
    ordered = train.sort_values(["race_id", "actual_rank", "horse_id"]).reset_index(drop=True)
    train_raw, test_raw = ordered[features].copy(), test[features].copy()
    categories = [column for column in features if train_raw[column].dtype.name in {"object", "category"}]
    numerics = [column for column in features if column not in categories]
    for column in numerics:
        train_raw[column] = pd.to_numeric(train_raw[column], errors="coerce").fillna(train_raw[column].median()).fillna(0.0)
        test_raw[column] = pd.to_numeric(test_raw[column], errors="coerce").fillna(train_raw[column].median()).fillna(0.0)
    for column in categories:
        train_raw[column] = train_raw[column].fillna("UNKNOWN").astype(str)
        test_raw[column] = test_raw[column].fillna("UNKNOWN").astype(str)
    names = pd.get_dummies(train_raw, columns=categories, dummy_na=True, dtype=float).columns.tolist()
    longest_first = sorted(features, key=len, reverse=True)
    return [next((feature for feature in longest_first if name == feature or name.startswith(feature + "_")), name) for name in names]


def aggregate_vector(values: np.ndarray, mapping: list[str]) -> dict[str, float]:
    result = defaultdict(float)
    for value, feature in zip(values, mapping):
        result[feature] += float(value)
    return dict(result)


def top_contributions(shap_values: np.ndarray, mapping: list[str], raw_row: dict, direction: str, count: int = 10) -> list[dict]:
    aggregated = aggregate_vector(shap_values, mapping)
    items = [(feature, value) for feature, value in aggregated.items() if (value > 0 if direction == "positive" else value < 0)]
    items.sort(key=lambda item: item[1], reverse=(direction == "positive"))
    return [{"feature": feature, "shap": value, "feature_value": raw_row.get(feature)} for feature, value in items[:count]]


def percentile_summary(values: pd.Series) -> dict:
    numeric = pd.to_numeric(values, errors="coerce")
    return {"min": numeric.min(), "p1": numeric.quantile(.01), "p10": numeric.quantile(.10), "p25": numeric.quantile(.25),
            "median": numeric.quantile(.50), "p75": numeric.quantile(.75), "p90": numeric.quantile(.90),
            "p99": numeric.quantile(.99), "max": numeric.max(), "mean": numeric.mean(), "std": numeric.std(),
            "missing_rate": numeric.isna().mean(), "zero_rate": (numeric.fillna(0) == 0).mean(), "unique_count": numeric.nunique(dropna=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit why Ranker raises market-disagreeing horses")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--enrich-examples", action="store_true", help="Fill existing representative examples with cached feature values without retraining models.")
    args = parser.parse_args()
    if args.enrich_examples:
        examples_path = args.out / "market_correct_ranker_wrong_examples.csv"
        importance_path = args.out / "feature_importance_comparison.csv"
        examples = list(csv.DictReader(examples_path.open(encoding="utf-8", newline="")))
        top_features = [row["feature"] for row in csv.DictReader(importance_path.open(encoding="utf-8", newline=""))]
        source = pd.read_parquet(wf.CACHE, columns=["race_id", "horse_id"] + top_features)
        values = {(str(row.race_id), str(row.horse_id)): row._asdict() for row in source.itertuples(index=False)}
        for row in examples:
            feature_values = values.get((row["race_id"], row.get("ranker_top1_horse_id", "")), {})
            # Historical output did not retain the ID; resolve it from the baseline prediction file.
            if not feature_values:
                predictions = pd.read_csv(ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv")
                match = predictions[(predictions["race_id"] == row["race_id"]) & (predictions["horse_name"] == row["ranker_top1_horse"])]
                if len(match):
                    feature_values = values.get((row["race_id"], str(match.iloc[0]["horse_id"])), {})
            contributions = json.loads(row["top10_positive_shap"])
            for contribution in contributions:
                contribution["feature_value"] = feature_values.get(contribution["feature"])
            row["top10_positive_shap"] = json.dumps(contributions, ensure_ascii=False)
        write_csv(examples_path, examples)
        print(json.dumps({"enriched_examples": len(examples), "output": str(examples_path)}, ensure_ascii=False))
        return
    frame, features = wf.load_frame()
    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    stored = pd.read_csv(ROOT / "reports" / "ranker_walk_forward_12m" / "walk_forward_predictions.csv")
    stored["date"] = pd.to_datetime(stored["date"])
    stored_key = {(str(row.race_id), str(row.horse_id)): row for row in stored.itertuples()}
    all_rows, shap_records, monthly_shap = [], [], []
    importance_gain, importance_split = defaultdict(float), defaultdict(float)
    permutation_impact = defaultdict(list)
    encoded_names_seen = set()
    for prediction_month in months:
        prediction_end = prediction_month + pd.DateOffset(months=1)
        train = frame[frame["date"] < prediction_month]
        test = frame[(frame["date"] >= prediction_month) & (frame["date"] < prediction_end)].copy().reset_index(drop=True)
        model, _, test_x = fit_model(train, test, features)
        mapping = encoded_mapping(train, test, features)
        encoded_names_seen.update(mapping)
        scores = model.predict(test_x, raw_score=True)
        stored_month = stored[(stored["date"] >= prediction_month) & (stored["date"] < prediction_end)]
        temperature = float(stored_month["ranker_win_probability"].iloc[0])
        # Pull the fixed per-month T from the training log instead of any evaluation-derived fit.
        log = pd.read_csv(ROOT / "reports" / "ranker_walk_forward_12m" / "monthly_training_log.csv")
        temperature = float(log.loc[log["prediction_month"] == prediction_month.strftime("%Y-%m"), "temperature"].iloc[0])
        probabilities = wf.softmax_by_race(scores, test["race_id"], temperature)
        contributions = model.booster_.predict(test_x, pred_contrib=True)[:, :-1]
        gain = aggregate_vector(model.booster_.feature_importance("gain"), mapping)
        split = aggregate_vector(model.booster_.feature_importance("split"), mapping)
        for feature, value in gain.items(): importance_gain[feature] += value
        for feature, value in split.items(): importance_split[feature] += value
        baseline_brier = np.mean((test["target"].to_numpy() - probabilities) ** 2)
        # Permute each source feature within this month and measure Brier degradation after its race softmax.
        for feature in features:
            indexes = [index for index, mapped in enumerate(mapping) if mapped == feature]
            if not indexes:
                continue
            rng = np.random.default_rng(wf.SEED + months.index(prediction_month))
            permuted = test_x.copy()
            permuted[:, indexes] = permuted[rng.permutation(len(permuted))][:, indexes]
            perturbed = wf.softmax_by_race(model.predict(permuted, raw_score=True), test["race_id"], temperature)
            permutation_impact[feature].append(float(np.mean((test["target"].to_numpy() - perturbed) ** 2) - baseline_brier))
        for index, row in test.iterrows():
            key = (str(row["race_id"]), str(row["horse_id"]))
            saved = stored_key[key]
            shap = aggregate_vector(contributions[index], mapping)
            record = {"date": row["date"], "race_id": row["race_id"], "horse_id": row["horse_id"], "horse_name": row["horse_name"],
                      "actual_rank": int(row["actual_rank"]), "target": int(row["target"]), "popularity": int(row["popularity"]),
                      "odds": float(row["odds"]) / 10.0, "ranker_score": float(saved.ranker_score),
                      "ranker_win_probability": float(saved.ranker_win_probability), "prediction_rank": int(saved.prediction_rank),
                      "top1_ev": float(saved.ranker_win_probability) * float(row["odds"]) / 10.0,
                      "win_payout": float(row["win_payout"])}
            record.update({f"shap_{feature}": value for feature, value in shap.items()})
            all_rows.append(record)
            for feature, value in shap.items():
                shap_records.append({"feature": feature, "shap": value, "abs_shap": abs(value), "date": row["date"], "race_id": row["race_id"],
                                     "horse_id": row["horse_id"], "top1": int(saved.prediction_rank == 1), "ev_fail": int(saved.prediction_rank == 1 and record["top1_ev"] >= 1 and row["target"] == 0),
                                     "nonfavorite_top1": int(saved.prediction_rank == 1 and row["popularity"] >= 4)})
        month_abs = defaultdict(list)
        for index in range(len(test)):
            for feature, value in aggregate_vector(contributions[index], mapping).items(): month_abs[feature].append(abs(value))
        for feature, values in month_abs.items():
            monthly_shap.append({"month": prediction_month.strftime("%Y-%m"), "feature": feature, "mean_abs_shap": mean(values)})
    records = pd.DataFrame(all_rows)
    shap_frame = pd.DataFrame(shap_records)
    mean_abs = shap_frame.groupby("feature")["abs_shap"].mean().to_dict()
    all_features = sorted(set(features) | set(importance_gain) | set(mean_abs))
    importance = []
    for feature in all_features:
        importance.append({"feature": feature, "feature_group": feature_group(feature), "gain_importance": importance_gain.get(feature, 0.0),
                           "split_importance": importance_split.get(feature, 0.0), "permutation_importance": mean(permutation_impact.get(feature, [0.0])),
                           "mean_abs_shap": mean_abs.get(feature, 0.0)})
    importance = sorted(importance, key=lambda row: row["mean_abs_shap"], reverse=True)
    for metric in ("gain_importance", "split_importance", "permutation_importance", "mean_abs_shap"):
        for rank, row in enumerate(sorted(importance, key=lambda value: value[metric], reverse=True), 1): row[f"{metric}_rank"] = rank
    top_features = [row["feature"] for row in importance[:TOP_FEATURES]]
    directions, calibration = [], []
    raw = frame.merge(records[["race_id", "horse_id", "ranker_score", "ranker_win_probability", "prediction_rank", "target", "popularity", "odds", "top1_ev"]], on=["race_id", "horse_id", "target", "popularity"], how="inner")
    for feature in top_features[:DIRECTION_FEATURES]:
        values = pd.to_numeric(raw[feature], errors="coerce")
        try:
            bins = pd.qcut(values, 10, duplicates="drop")
        except ValueError:
            continue
        for label, subset in raw.groupby(bins, observed=True):
            shap_column = f"shap_{feature}"
            directions.append({"feature": feature, "feature_group": feature_group(feature), "decile": str(label), "sample_size": len(subset),
                               "feature_mean": pd.to_numeric(subset[feature], errors="coerce").mean(), "ranker_score_mean": subset["ranker_score"].mean(),
                               "ranker_win_probability_mean": subset["ranker_win_probability"].mean(), "actual_win_rate": subset["target"].mean(),
                               "actual_place_rate": (subset["actual_rank"] <= 3).mean(), "top1_rate": (subset["prediction_rank"] == 1).mean(),
                               "average_shap": subset[shap_column].mean() if shap_column in subset else None})
            top1 = subset[subset["prediction_rank"] == 1]
            calibration.append({"feature": feature, "decile": str(label), "sample_size": len(subset),
                                "predicted_win_probability": subset["ranker_win_probability"].mean(), "actual_win_rate": subset["target"].mean(),
                                "calibration_gap": subset["ranker_win_probability"].mean() - subset["target"].mean(),
                                "top1_roi": top1["win_payout"].sum() / (len(top1) * 100) * 100 if len(top1) else None})
    top1 = records[records["prediction_rank"] == 1].copy()
    top1["market_group"] = pd.cut(top1["popularity"], bins=[0, 1, 3, 6, float("inf")], labels=["A_favorite", "B_2_3", "C_4_6", "D_7_plus"])
    market_summary, market_shap = [], []
    for label, group in top1.groupby("market_group", observed=True):
        market_summary.append({"market_group": str(label), "races": len(group), "predicted_win_probability": group["ranker_win_probability"].mean(),
                               "actual_win_rate": group["target"].mean(), "average_odds": group["odds"].mean(),
                               "win_roi": group["win_payout"].sum() / (len(group) * 100) * 100, "profit": group["win_payout"].sum() - len(group) * 100})
        for feature in top_features[:20]:
            market_shap.append({"market_group": str(label), "feature": feature, "mean_abs_shap": group[f"shap_{feature}"].abs().mean()})
    ev_fail = top1[(top1["top1_ev"] >= 1.0) & (top1["target"] == 0)]
    ev_win = top1[(top1["top1_ev"] >= 1.0) & (top1["target"] == 1)]
    ev_failure_rows = []
    for feature in top_features:
        column = f"shap_{feature}"
        ev_failure_rows.append({"feature": feature, "feature_group": feature_group(feature), "appearance_count": int((ev_fail[column] > 0).sum()),
                                "mean_shap": ev_fail[column].mean(), "median_shap": ev_fail[column].median(),
                                "mean_feature_value": pd.to_numeric(raw.loc[raw.set_index(["race_id", "horse_id"]).index.isin(ev_fail.set_index(["race_id", "horse_id"]).index), feature], errors="coerce").mean(),
                                "loss_cases": len(ev_fail), "win_cases": len(ev_win), "mean_shap_win_cases": ev_win[column].mean()})
    favorites = records[records["popularity"] == 1]
    favorite_under = favorites[favorites["prediction_rank"] >= 2]
    favorite_summary, favorite_shap = [], []
    for condition, subset in (("rank_2", favorite_under[favorite_under["prediction_rank"] == 2]), ("rank_3_plus", favorite_under[favorite_under["prediction_rank"] >= 3])):
        favorite_summary.append({"condition": condition, "race_count": len(subset), "favorite_actual_win_rate": subset["target"].mean(),
                                 "ranker_win_probability": subset["ranker_win_probability"].mean(), "mean_actual_rank": subset["actual_rank"].mean()})
        for feature in top_features[:20]: favorite_shap.append({"condition": condition, "feature": feature, "mean_shap": subset[f"shap_{feature}"].mean()})
    counterexamples = []
    for race_id, group in records.groupby("race_id"):
        model_top = group[group["prediction_rank"] == 1].iloc[0]
        favorite = group[group["popularity"] == 1]
        if model_top["popularity"] >= 4 and model_top["target"] == 0 and len(favorite) and int(favorite.iloc[0]["target"]) == 1:
            winner = group[group["target"] == 1].iloc[0]
            positive = top_contributions(np.array([model_top[f"shap_{feature}"] for feature in all_features]), all_features, model_top, "positive")
            counterexamples.append({"date": model_top["date"], "race_id": race_id, "ranker_top1_horse": model_top["horse_name"], "ranker_rank": model_top["prediction_rank"],
                                    "ranker_probability": model_top["ranker_win_probability"], "ranker_popularity": model_top["popularity"], "ranker_odds": model_top["odds"], "ranker_actual_rank": model_top["actual_rank"],
                                    "winner_horse": winner["horse_name"], "winner_popularity": winner["popularity"], "winner_odds": winner["odds"],
                                    "top10_positive_shap": json.dumps(positive, ensure_ascii=False)})
    quality = []
    for feature in top_features:
        summary = percentile_summary(frame[feature])
        quality.append({"feature": feature, "feature_group": feature_group(feature), "dtype": str(frame[feature].dtype), **summary})
    correlation = raw[top_features].apply(pd.to_numeric, errors="coerce").corr()
    duplicate_rows = []
    for left in range(len(top_features)):
        for right in range(left + 1, len(top_features)):
            value = correlation.iloc[left, right]
            if pd.notna(value) and abs(value) >= 0.85:
                duplicate_rows.append({"feature_a": top_features[left], "feature_b": top_features[right], "correlation": value,
                                       "group_a": feature_group(top_features[left]), "group_b": feature_group(top_features[right])})
    group_rows = []
    for group in sorted({feature_group(feature) for feature in top_features}):
        group_features = [feature for feature in top_features if feature_group(feature) == group]
        columns = [f"shap_{feature}" for feature in group_features]
        group_rows.append({"feature_group": group, "features": ";".join(group_features), "total_mean_abs_shap": records[columns].abs().sum(axis=1).mean(),
                           "top1_mean_shap": top1[columns].sum(axis=1).mean(), "ev_ge_1_failure_mean_shap": ev_fail[columns].sum(axis=1).mean(),
                           "market_4plus_top1_mean_shap": top1[top1["popularity"] >= 4][columns].sum(axis=1).mean()})
    month_stability = pd.DataFrame(monthly_shap)
    stability = []
    for feature, group in month_stability.groupby("feature"):
        top20_months = sum(group["mean_abs_shap"].rank(ascending=False, method="min") <= 20)
        stability.append({"feature": feature, "months_in_top20": top20_months, "mean_abs_shap": group["mean_abs_shap"].mean(),
                          "max_month_abs_shap": group["mean_abs_shap"].max(), "min_month_abs_shap": group["mean_abs_shap"].min()})
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "feature_importance_comparison.csv", importance[:TOP_FEATURES])
    write_csv(args.out / "feature_direction_deciles.csv", directions)
    write_csv(args.out / "feature_calibration_deciles.csv", calibration)
    write_csv(args.out / "ev_top1_loss_positive_shap.csv", sorted(ev_failure_rows, key=lambda row: row["mean_shap"], reverse=True))
    write_csv(args.out / "market_disagreement_summary.csv", market_summary)
    write_csv(args.out / "market_group_shap_top20.csv", market_shap)
    write_csv(args.out / "favorite_underrating_summary.csv", favorite_summary)
    write_csv(args.out / "favorite_underrating_shap.csv", favorite_shap)
    write_csv(args.out / "market_correct_ranker_wrong_examples.csv", counterexamples[:30])
    write_csv(args.out / "feature_data_quality.csv", quality)
    write_csv(args.out / "high_correlation_feature_pairs.csv", sorted(duplicate_rows, key=lambda row: abs(row["correlation"]), reverse=True))
    write_csv(args.out / "feature_group_shap_summary.csv", group_rows)
    write_csv(args.out / "monthly_shap_stability.csv", sorted(stability, key=lambda row: (-row["months_in_top20"], -row["mean_abs_shap"])))
    (args.out / "audit_metadata.json").write_text(json.dumps({"months": [month.strftime("%Y-%m") for month in months], "top1_rows": len(top1),
        "ev_ge_1_losses": len(ev_fail), "counterexamples": len(counterexamples), "shap_method": "LightGBM pred_contrib TreeSHAP", "features": len(features)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.out), "top_features": top_features[:20], "ev_failures": len(ev_fail), "counterexamples": len(counterexamples)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

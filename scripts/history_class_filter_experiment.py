#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import (
    DEFAULT_DB, JYO_NAMES, PHASE5_FEATURES, PRIZE_FEATURES, RACE_CONDITION_FEATURES,
    build_v1_features, history_class_score, history_policy_allows, limit_evaluation_races, load_data,
    race_id, evaluate_stage, write_report, date,
)

FEATURES = PHASE5_FEATURES + RACE_CONDITION_FEATURES + PRIZE_FEATURES
POLICIES = {"baseline": "BASELINE", "filter-a": "FILTER-A", "filter-b": "FILTER-B"}

def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
    else:
        path.write_text("\n", encoding="utf-8")

def source_class(row):
    score = history_class_score(row)
    return {None: "UNKNOWN", 0: "初期/未勝利相当", 1: "1勝以上", 2: "2勝以上", 3: "3勝以上", 4: "OP以上", 5: "L", 6: "G3", 7: "G2", 8: "G1"}.get(score, "UNKNOWN")

def audit_sources(data, target_ids, out):
    target_dates = {race_id(row): row["date"] for row in data if race_id(row) in target_ids}
    target_horses = {(row.get("KettoNum"), rid) for rid in target_ids for row in data if race_id(row) == rid}
    rows = []
    for source in data:
        sid = race_id(source)
        if sid in target_ids:
            continue
        horse = source.get("KettoNum")
        for target_id, target_date in target_dates.items():
            if source["date"] < target_date and (horse, target_id) in target_horses:
                score = history_class_score(source)
                if score == 0:
                    assert not history_policy_allows(source, "filter-a") and not history_policy_allows(source, "filter-b")
                elif score == 1:
                    assert history_policy_allows(source, "filter-a") and not history_policy_allows(source, "filter-b")
                elif score >= 2:
                    assert history_policy_allows(source, "filter-a") and history_policy_allows(source, "filter-b")
                rows.append({"horse_id": horse, "target_race_id": target_id, "source_race_id": sid,
                             "source_date": source["date"], "race_first_prize": source.get("race_Honsyokin0"),
                             "normalized_source_class": source_class(source),
                             "baseline_used": int(history_policy_allows(source, "baseline")),
                             "filter_a_used": int(history_policy_allows(source, "filter-a")),
                             "filter_b_used": int(history_policy_allows(source, "filter-b")),
                             "reason": "explicit/experimental prize tier" if score is not None else "unclassified"})
                if len(rows) >= 5000:
                    write_rows(out, rows)
                    return
    write_rows(out, rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-eval-races", type=int, default=10)
    parser.add_argument("--start-month", default="2026-07")
    parser.add_argument("--end-month", default="2026-09")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    parser.add_argument("--policies", nargs="+", choices=tuple(POLICIES), default=tuple(POLICIES))
    parser.add_argument("--feature-only", action="store_true")
    args = parser.parse_args()
    data, pays, source = load_data(args.db)
    data = [row for row in data if str(row.get("idJyoCD", "")).zfill(2) in JYO_NAMES]
    start = date.fromisoformat(args.start_month + "-01")
    end = date.fromisoformat(args.end_month + "-01")
    limited = limit_evaluation_races(data, start, end, args.max_eval_races)
    target_ids = {race_id(row) for row in limited if start <= row["date"] < end}
    audit_sources(limited, target_ids, args.out / "history_class_filter_audit.csv")
    if args.feature_only:
        feature_maps = {}
        for policy in args.policies:
            feature_maps[policy] = pd.DataFrame(build_v1_features(limited, history_policy=policy, feature_target_ids=target_ids))
        base = feature_maps["baseline"]
        cols = ["horse_expected_position", "position_stability", "last1_raw_performance", "last1_adjusted_performance", "hidden_strength_last1", "last1_winner_strength", "last1_field_strength", "last1_margin", "usable_history_count"]
        changes = []
        for policy in args.policies:
            if policy == "baseline":
                continue
            merged = base[["race_id", "horse_id"] + [c for c in cols if c in base]].merge(feature_maps[policy][["race_id", "horse_id"] + [c for c in cols if c in feature_maps[policy]]], on=["race_id", "horse_id"], suffixes=("_baseline", f"_{policy.replace('-', '_')}"))
            for _, row in merged.iterrows():
                item = {"policy": policy, "race_id": row["race_id"], "horse_id": row["horse_id"]}
                for col in cols:
                    left, right = f"{col}_baseline", f"{col}_{policy.replace('-', '_')}"
                    if left in row and right in row:
                        item[f"{col}_delta"] = row[right] - row[left]
                changes.append(item)
        write_rows(args.out / "history_class_filter_feature_changes.csv", changes)
        audit = pd.read_csv(args.out / "history_class_filter_audit.csv")
        grouped = audit.groupby(["horse_id", "target_race_id"])["normalized_source_class"].agg(set)
        candidate = next(((horse, target) for (horse, target), classes in grouped.items()
                          if {"初期/未勝利相当", "1勝以上", "2勝以上"}.issubset(classes)), None)
        if candidate is None:
            raise RuntimeError("代表馬候補（初期/未勝利相当・1勝以上・2勝以上）が見つかりません")
        trace_rows = []
        horse, target = candidate
        horse_rows = [row for row in limited if str(row.get("KettoNum")) == str(horse)]
        target_rows = [row for row in limited if race_id(row) == target]
        reduced = horse_rows + [row for row in target_rows if str(row.get("KettoNum")) != str(horse)]
        for policy, label in POLICIES.items():
            trace = {"horse_id": str(horse), "target_race_id": target, "source": [], "appended": []}
            built = build_v1_features(reduced, history_policy=policy, feature_target_ids={target}, history_trace=trace)
            source_by_id = {race_id(row): row for row in horse_rows}
            for source in trace.get("source", []):
                sid = source["source_race_id"]
                source_row = source_by_id.get(sid, {})
                trace_rows.append({"policy": label, "stage": source["event"], "source_race_id": sid,
                    "source_date": source_row.get("date"), "race_first_prize": source_row.get("race_Honsyokin0"),
                    "normalized_source_class": source_class(source_row), "history_allowed": source["history_allowed"],
                    "used_for_state_append": int(sid in trace.get("appended", [])), "used_for_performance": int(sid in trace.get("performance_used", [])),
                    "used_for_position": int(sid in trace.get("position_used", [])), "used_as_last1_3": int(sid in trace.get("last_used", []))})
            for stage, ids in (("performance_used", trace.get("performance_used", [])), ("position_used", trace.get("position_used", [])), ("last1_last2_last3", trace.get("last_used", []))):
                for sid in ids:
                    trace_rows.append({"policy": label, "stage": stage, "source_race_id": sid, "normalized_source_class": source_class(source_by_id.get(sid, {})), "history_allowed": True})
            for name, value in trace.get("final_features", {}).items():
                trace_rows.append({"policy": label, "stage": "final_feature", "source_race_id": name, "final_feature_value": value})
        write_rows(args.out / "history_class_filter_representative_trace.csv", trace_rows)
        print({"feature_only": True, "target_races": len(target_ids), "rows": len(changes)})
        return
    summaries = []
    feature_maps = {}
    for policy in args.policies:
        label = POLICIES[policy]
        if policy == "baseline":
            baseline_path = ROOT / "reports" / "backtest_phase5_F_cached_df_432" / "predictions.csv"
            baseline = pd.read_csv(baseline_path)
            rows = baseline[baseline["race_id"].isin(target_ids)].to_dict("records")
            importance = []
        else:
            rows, importance = evaluate_stage(limited, pays, start, end, "F", history_policy=policy)
        output = args.out / f"history_class_filter_{policy.replace('-', '_')}_{args.max_eval_races}"
        write_report(rows, output, {"model": label, "history_policy": policy, "target_races": len(target_ids), "source_rows": len(limited)}, importance)
        frame = pd.DataFrame(rows)
        feature_maps[policy] = frame
        top = frame[frame["prediction_rank"] == 1] if not frame.empty else frame
        investment = len(top) * 100
        probabilities = np.clip(frame["predicted_probability"].to_numpy(), 1e-15, 1 - 1e-15) if not frame.empty else np.array([])
        labels = frame["is_win"].to_numpy() if not frame.empty else np.array([])
        summaries.append({"model": label, "policy": policy, "races": frame["race_id"].nunique(),
                  "logloss": float(-(labels*np.log(probabilities)+(1-labels)*np.log(1-probabilities)).mean()) if len(frame) else None,
                          "brier": ((frame["is_win"]-frame["predicted_probability"])**2).mean() if not frame.empty else None,
                          "top1_accuracy": top["is_win"].mean() if len(top) else None,
                          "top3_accuracy": frame.assign(hit=(frame["prediction_rank"] <= 3) & (frame["is_win"] == 1)).groupby("race_id")["hit"].any().mean() if not frame.empty else None,
                          "win_roi": top["win_payout"].sum()/investment*100 if investment else None,
                          "place_roi": top["place_payout"].sum()/investment*100 if investment else None,
                          "top1_mean_odds": top["odds"].mean() if len(top) else None,
                          "top1_median_odds": top["odds"].median() if len(top) else None,
                          "hit_mean_odds": top.loc[top["is_win"] == 1, "odds"].mean() if (top["is_win"] == 1).any() else None})
    write_rows(args.out / f"history_class_filter_{args.max_eval_races}_comparison.csv", summaries)
    base = feature_maps["baseline"]
    changes = []
    if not base.empty:
        keys = ["race_id", "horse_id"]
        cols = ["horse_expected_position", "position_stability", "last1_raw_performance", "last1_adjusted_performance", "hidden_strength_last1", "last1_winner_strength", "last1_field_strength", "last1_margin", "usable_history_count"]
        for policy in ("filter-a", "filter-b"):
            other = feature_maps[policy]
            merged = base[keys + [c for c in cols if c in base]].merge(other[keys + [c for c in cols if c in other]], on=keys, suffixes=("_baseline", f"_{policy.replace('-', '_')}"))
            for _, row in merged.iterrows():
                item = {"policy": policy, **{key: row[key] for key in keys}}
                for col in cols:
                    left, right = f"{col}_baseline", f"{col}_{policy.replace('-', '_')}"
                    if left in row and right in row:
                        item[f"{col}_delta"] = row[right] - row[left]
                changes.append(item)
    write_rows(args.out / f"history_class_filter_{args.max_eval_races}_feature_changes.csv", changes)
    print({"target_races": len(target_ids), "max_eval_races": args.max_eval_races, "outputs": [str(args.out / f"history_class_filter_{args.max_eval_races}_comparison.csv")]})

if __name__ == "__main__":
    main()

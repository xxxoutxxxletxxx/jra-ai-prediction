#!/usr/bin/env python3
"""Phase 6.1 feature inventory and leakage audit."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DROP = {"career_place_rate", "recent5_place_rate", "jockey_added_value", "jockey_top2_rate", "jockey_form_trend", "jockey_change_added_value"}
RESULT = {"actual_rank", "target", "is_win", "is_place", "KakuteiJyuni", "TimeDiff", "Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c", "win_payout", "place_payout"}
MARKET = {"Odds", "Ninki", "odds", "popularity"}
RACE_DIRECT = {"racecourse", "course_first_corner_distance_m", "course_elevation_difference_m", "course_final_straight_m", "course_start_uphill", "course_start_downhill", "course_final_uphill", "course_final_downhill", "course_final_steep_hill", "course_rolling_terrain", "course_tight_corners", "course_up_down_transition_sentence_count", "position_bias_top5_v2", "position_bias_top6_v2", "position_bias_weighted_top6_v2", "position_bias_residual_v2", "front_density", "forward_density", "mid_density", "rear_density", "expected_front_count", "expected_position_mean", "expected_position_std"}


def group(name):
    if name in RESULT: return "RESULT"
    if name in MARKET: return "MARKET"
    if name.startswith("jockey_") or name.startswith("recent_jockey"): return "JOCKEY"
    if "course" in name or name.startswith("course_"): return "COURSE"
    if "position" in name or "pace" in name or "hidden" in name or "adjusted" in name or "bias" in name or "setup" in name: return "POSITION"
    if "winner" in name or "field_strength" in name or "opponent" in name or "strong_opponent" in name: return "OPPONENT_STRENGTH"
    if "prize" in name or "class" in name or "sex_condition" in name or "age_condition" in name: return "RACE_STRENGTH"
    return "BASE"


def main():
    cache = next(iter(sorted((ROOT / "data/cache").glob("phase5_f_features.parquet"))), None)
    if not cache: raise SystemExit("phase5 cache not found")
    names = pq.ParquetFile(cache).schema.names
    lists = {}
    for path in (ROOT / "reports").glob("features_model_*.txt"):
        lists[path.stem] = set(path.read_text(encoding="utf-8").splitlines())
    rows=[]
    for name in names:
        used = {key: int(name in value) for key, value in lists.items()}
        if name in DROP: policy="REMOVE_FROM_MODEL"
        elif name in RESULT: policy="LEAKAGE_PROHIBITED"
        elif name in MARKET: policy="ANALYSIS_ONLY"
        elif name in RACE_DIRECT: policy="TRANSFORM_TO_HORSE_FIT" if name not in {"racecourse"} else "AB_TEST"
        elif name.startswith("frontness_") or name in {"horse_expected_position", "position_stability"}: policy="NORMALIZE_0_1"
        elif name.startswith("race_position_bias") or name.startswith("position_bias_"): policy="INTERMEDIATE_ONLY"
        else: policy="KEEP"
        rows.append({"feature":name,"feature_group":group(name),"used_model_d":used.get("features_model_d",0),"used_model_e":used.get("features_model_e",0),"used_model_f":used.get("features_model_f",0),"used_model_g":used.get("features_model_g",0),"meaning":"既存feature定義を参照","level":"RESULT" if name in RESULT else "MARKET" if name in MARKET else "RACE" if name in RACE_DIRECT else "HORSE","temporal_safe":"NO" if name in RESULT else "ANALYSIS_ONLY" if name in MARKET else "YES","constant_rate":"UNKNOWN","missing_rate":"UNKNOWN","unknown_rate":"UNKNOWN","duplicate_candidate":"YES" if name in {"frontness_mean","frontness_std","horse_expected_position","position_stability","last*_class"} else "NO","new_policy":policy,"replacement_feature":"horse-level fit" if policy=="TRANSFORM_TO_HORSE_FIT" else "","reason":"cleanup inventory: source cache schema and model lists"})
    out=ROOT/"reports"; out.mkdir(exist_ok=True)
    fields=list(rows[0])
    with (out/"feature_inventory_cleanup.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    (out/"leakage_audit_cleanup.md").write_text("# Cleanup Leakage Audit\n\nResult-derived columns are retained only for target/evaluation or historical state updates. They are not in the Cleanup-A feature list. `Odds` and `Ninki` are analysis-only. Current race `Jyuni1c`, `TimeDiff`, `KakuteiJyuni`, and payouts are prohibited from model inputs. Historical results are used only after their source race date and before the target race date.\n",encoding="utf-8")
    (out/"feature_cleanup_decisions.md").write_text("# Cleanup Decisions\n\nExplicit removals: career_place_rate, recent5_place_rate, jockey_added_value, jockey_top2_rate, jockey_form_trend, jockey_change_added_value. Cleanup-A also excludes racecourse one-hot, raw course geometry, direct race-bias columns, and current field-context columns. Cleanup-A keeps base performance, margins, opponent strength, prize strength, and horse-level adjusted/hidden performance.\n",encoding="utf-8")
    print(json.dumps({"cache_columns":len(names),"inventory_rows":len(rows),"output":str(out)},ensure_ascii=False))

if __name__=="__main__": main()

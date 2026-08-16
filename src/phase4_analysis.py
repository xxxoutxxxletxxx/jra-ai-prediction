#!/usr/bin/env python3
"""Phase 4: D/E展開補正とHidden Strengthの事後分析。"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent

def num(value, default=0.0):
    try: return float(str(value or default))
    except (TypeError, ValueError): return default

def integer(value, default=0):
    try: return int(float(str(value or default)))
    except (TypeError, ValueError): return default

def load(path):
    with path.open(encoding="utf-8", newline="") as f:
        rows=list(csv.DictReader(f))
    for r in rows:
        for k in ("prediction_rank","actual_rank","popularity","is_win","is_place"):
            r[k]=integer(r.get(k))
        for k in ("predicted_probability","odds","win_payout","place_payout","hidden_strength_last1","setup_improvement","max_hidden_strength_last3","max_strong_against_bias_last3","last1_raw_performance","last1_adjusted_performance"):
            r[k]=num(r.get(k))
    return rows

def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields: fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def summary(rows):
    if not rows: return {"races":0}
    return {"races":len(rows),"win_rate":mean(r["is_win"] for r in rows),"top2_rate":mean(r["actual_rank"]<=2 for r in rows),"top3_rate":mean(r["is_place"] for r in rows),"win_roi":sum(r["win_payout"] for r in rows)/(len(rows)*100)*100,"place_roi":sum(r["place_payout"] for r in rows)/(len(rows)*100)*100}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--d",type=Path,default=ROOT/"reports/backtest_prize_D_verified/predictions.csv"); p.add_argument("--e",type=Path,default=ROOT/"reports/backtest_phase4_E_current/predictions.csv"); p.add_argument("--out",type=Path,default=ROOT/"reports/phase4_analysis"); a=p.parse_args()
    d=load(a.d); e=load(a.e); dmap={(r["race_id"],r["horse_id"]):r for r in d}; changes=[]
    for r in e:
        old=dmap.get((r["race_id"],r["horse_id"]));
        if not old: continue
        changes.append({"race_id":r["race_id"],"horse_name":r["horse_name"],"actual_finish":r["actual_rank"],"odds":r["odds"],"model_d_rank":old["prediction_rank"],"model_e_rank":r["prediction_rank"],"model_d_score":old["predicted_probability"],"model_e_score":r["predicted_probability"],"rank_change":old["prediction_rank"]-r["prediction_rank"],"last1_finish":r["last1_finish"],"last1_margin":r["last1_margin"],"last1_raw_performance":r["last1_raw_performance"],"last1_adjusted_performance":r["last1_adjusted_performance"],"hidden_strength_last1":r["hidden_strength_last1"],"max_hidden_strength_last3":r["max_hidden_strength_last3"],"max_strong_against_bias_last3":r["max_strong_against_bias_last3"],"setup_improvement":r["setup_improvement"],"last1_race_position_bias":r.get("last1_race_position_bias",0),"last1_position_advantage":r.get("last1_position_advantage",0)})
    changes.sort(key=lambda r:(r["rank_change"],-r["hidden_strength_last1"]), reverse=True)
    popular=[r for r in e if r["odds"]>=5 and r["prediction_rank"]==1]
    hidden=[r for r in e if r["odds"]>=5 and r["hidden_strength_last1"]>0 and r["setup_improvement"]>=0]
    bins=[]
    for label, selected in (("odds_5_plus",popular),("odds_10_plus",[r for r in e if r["odds"]>=10 and r["prediction_rank"]==1]),("hidden_and_setup",hidden)):
        bins.append({"group":label,**summary(selected)})
    a_out=a.out; a_out.mkdir(parents=True,exist_ok=True)
    write(a_out/"model_d_to_e_changes.csv",changes[:200]); write(a_out/"phase4_popular_hidden_analysis.csv",bins)
    write(a_out/"hidden_strength_horses.csv",[r for r in e if r["hidden_strength_last1"]>0])
    (a_out/"phase4_summary.md").write_text("# Phase 4\n\nModel E adds raw/adjusted performance, position advantage, race position bias, hidden strength, strong-against-bias, and setup improvement to Model D.\n\n"+"\n".join(f"- {b['group']}: races {b['races']}, win {b['win_rate']:.2%}, top2 {b['top2_rate']:.2%}, top3 {b['top3_rate']:.2%}, win ROI {b['win_roi']:.1f}%, place ROI {b['place_roi']:.1f}%" for b in bins)+"\n\n展開補正だけで穴馬と断定せず、着差・賞金・相手強度と併用する。オッズは評価専用で、Model E特徴量には使用しない。\n",encoding="utf-8")
    print({"d_rows":len(d),"e_rows":len(e),"changes":len(changes),"output":str(a_out)})
if __name__=="__main__": main()

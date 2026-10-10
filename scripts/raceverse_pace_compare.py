"""ペース予測改修の新旧比較レポートを作る。旧=ペースを乱数抽選していた版、新=全頭隊列+Pace Impactの回帰のみ。

  PYTHONPATH=. .venv/bin/python scripts/raceverse_pace_compare.py \
      --old reports/raceverse/backtest_202509_202609 --new reports/raceverse/backtest_202509_202609_pace_v2
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from raceverse.config import PACE_BUCKETS, REPORT_DIR, load_config
from raceverse.pace_display import fit_display_thresholds, pace_display_bucket_index, thresholds_for
from raceverse.pace_features import CATEGORICAL_FEATURES, FEATURE_NAMES, LEGACY_NUMERIC, NEW_HISTORY, NEW_IMPACT, NEW_STRUCT
from raceverse.pipeline import prepare

LABEL = {"VERY_FAST": "超ハイ", "FAST": "ハイ", "MIDDLE": "ミドル", "SLOW": "スロー", "VERY_SLOW": "超スロー"}
LEVELS = ["base", "formation", "pace"]  # full は比較対象外(ユーザー方針)
PROB_COLS = [f"pace_prob_{b}" for b in PACE_BUCKETS]


def class_metrics(actual: np.ndarray, pred: np.ndarray) -> Dict[str, object]:
    out: Dict[str, object] = {"n": int(len(actual)), "accuracy": float((actual == pred).mean())}
    recalls, precisions, f1s = [], [], []
    for c in range(5):
        tp = float(((actual == c) & (pred == c)).sum())
        rec = tp / max((actual == c).sum(), 1)
        prec = tp / (pred == c).sum() if (pred == c).sum() else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
        recalls.append(rec)
        precisions.append(prec)
        f1s.append(f1)
    out.update({"macro_f1": float(np.mean(f1s)), "recall": recalls, "precision": precisions,
                "high_pace_recall": float(np.isin(pred[np.isin(actual, [0, 1])], [0, 1]).mean()),
                "super_high_recall": recalls[0]})
    out["predicted_counts"] = [int((pred == c).sum()) for c in range(5)]
    return out


def mean_bucket(P, races: pd.DataFrame, column: str) -> np.ndarray:
    """平均ペース予測を、月初時点の訓練期データだけで決めた境界値で5分類する。"""
    table = P.store.race_table
    cfg = P.cfg
    cache: Dict[pd.Timestamp, dict] = {}
    result = np.zeros(len(races), dtype=int)
    for i, (date, surface, dist, value) in enumerate(zip(races["date"], races["surface"], races["distance_m"], races[column])):
        month = pd.Timestamp(date).to_period("M").to_timestamp()
        if month not in cache:
            before = table[table["date"] < month]
            cache[month] = fit_display_thresholds(before["group"].to_numpy(), before["y"].to_numpy(),
                                                  cfg.pace.display_quantiles)
        th = thresholds_for(cache[month], surface, int(dist))
        result[i] = int(pace_display_bucket_index(np.array([value]), th)[0])
    return result


def bootstrap_ci(values_fn, n: int, reps: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    draws = np.array([values_fn(rng.integers(0, n, n)) for _ in range(reps)])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def load_run(path: Path) -> Dict[str, pd.DataFrame]:
    return {"race": pd.read_csv(path / "race_level.csv", parse_dates=["date"]),
            "prob": pd.read_csv(path / "probability_metrics.csv"), "roi": pd.read_csv(path / "roi_reference.csv"),
            "summary": json.loads((path / "summary.json").read_text(encoding="utf-8"))}


def pct(x: float, digits: int = 2) -> str:
    return f"{100 * x:.{digits}f}%"


def md_table(header: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def coefficient_table(P, as_of: pd.Timestamp, top: int = 25) -> pd.DataFrame:
    bundle = P.bundle(as_of)
    scaler, ridge = bundle.pace_model.named_steps["scale"], bundle.pace_model.named_steps["ridge"]
    frame = pd.DataFrame({"feature": FEATURE_NAMES, "standardized_coef_sec": ridge.coef_,
                          "coef_sec_per_raw_unit": ridge.coef_ / scaler.scale_})
    frame["group"] = ["impact" if f in NEW_IMPACT else "history" if f in NEW_HISTORY else "structure"
                      if f in NEW_STRUCT else "legacy" for f in frame["feature"]]
    frame["abs"] = frame["standardized_coef_sec"].abs()
    return frame.sort_values("abs", ascending=False).drop(columns="abs")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, default=REPORT_DIR / "backtest_202509_202609")
    parser.add_argument("--new", type=Path, default=REPORT_DIR / "backtest_202509_202609_pace_v2")
    parser.add_argument("--diag", type=Path, default=REPORT_DIR / "pace_v2")
    args = parser.parse_args()
    cfg = load_config()
    P = prepare(cfg)
    old, new = load_run(args.old), load_run(args.new)
    ro, rn = old["race"], new["race"]
    common = sorted(set(ro["race_id"]) & set(rn["race_id"]))
    ro = ro[ro["race_id"].isin(common)].set_index("race_id").loc[common].reset_index()
    rn = rn[rn["race_id"].isin(common)].set_index("race_id").loc[common].reset_index()
    ok = (ro["actual_pace_bucket"].to_numpy() >= 0)
    actual = ro["actual_pace_bucket"].to_numpy()[ok]
    assert (actual == rn["actual_pace_bucket"].to_numpy()[ok]).all(), "actual pace class must be identical (model independent)"
    n = int(ok.sum())

    # 前半ラップ誤差
    err_old = (ro["pace_delta_pred_mean"] - ro["pace_delta_actual"]).to_numpy()[ok]
    err_new = (rn["pace_delta_pred_mean"] - rn["pace_delta_actual"]).to_numpy()[ok]
    zero_err = ro["pace_delta_actual"].to_numpy()[ok]
    mae = lambda e: float(np.abs(e).mean())
    rmse = lambda e: float(np.sqrt((e ** 2).mean()))
    mae_ci = bootstrap_ci(lambda i: mae(err_new[i]) - mae(err_old[i]), n)
    rmse_ci = bootstrap_ci(lambda i: rmse(err_new[i]) - rmse(err_old[i]), n)

    # 5分類
    preds = {}
    for tag, frame in (("old", ro), ("new", rn)):
        preds[(tag, "mode")] = frame[PROB_COLS].to_numpy().argmax(axis=1)[ok]
        preds[(tag, "mean")] = mean_bucket(P, frame, "pace_delta_pred_mean")[ok]
    middle_baseline = np.full(n, 2)
    most_common = int(np.bincount(actual, minlength=5).argmax())
    metrics = {k: class_metrics(actual, v) for k, v in preds.items()}
    metrics[("baseline", "always MIDDLE (学習期の分位点設計で最大の区分)")] = class_metrics(actual, middle_baseline)
    metrics[("baseline", f"評価期間の最頻クラス固定({LABEL[PACE_BUCKETS[most_common]]}, 事後的な上限)")] = class_metrics(
        actual, np.full(n, most_common))
    acc_base = float((actual == most_common).mean())
    acc_ci = {}
    for key in (("old", "mode"), ("new", "mode"), ("old", "mean"), ("new", "mean")):
        p = preds[key]
        acc_ci[key] = bootstrap_ci(lambda i, p=p: float((actual[i] == p[i]).mean() - (actual[i] == most_common).mean()), n)
    acc_gain_ci = bootstrap_ci(lambda i: float((actual[i] == preds[("new", "mode")][i]).mean()
                                               - (actual[i] == preds[("old", "mode")][i]).mean()), n)

    lines: List[str] = []
    w = lines.append
    w("# RACEVERSE ペース予測モデル改修 報告(Pace Impact + 全頭隊列回帰)\n")
    w(f"- 評価: {cfg.backtest.test_start}〜{cfg.backtest.test_end} の Walk-Forward、共通 {len(common)} レース"
      f"(ペース分類は実測が取れた {n} レース)。旧と新は同一レース・同一馬・10,000回・seed 42。")
    w("- 旧: 隊列からの回帰平均に、OOF残差プールからのペース乱択を上乗せ。新: 乱択を廃止し、確定した全頭隊列と馬・騎手の"
      "Pace Impactから回帰した値をそのままペースとする(分布は隊列の抽選だけから生まれる)。")
    w("- 5分類の境界値は各月の学習期データの分位点(10/30/70/90%)で固定。評価期間に合わせた調整はしていない。")
    w("- 回収率は確定オッズによる参考値(発走前スナップショットではない)。`full`は比較対象外(コード上は維持)。\n")

    w("## 1. 結論\n")
    new_mode, old_mode, new_mean = metrics[("new", "mode")], metrics[("old", "mode")], metrics[("new", "mean")]
    sig = lambda ci: "95%CIが0をまたぐため有意差なし" if ci[0] <= 0 <= ci[1] else "95%CIが0を含まず有意"
    w(f"- 前半ラップMAEは {mae(err_old):.4f}秒 → {mae(err_new):.4f}秒(差 {mae(err_new) - mae(err_old):+.4f}, 95%CI "
      f"[{mae_ci[0]:+.4f}, {mae_ci[1]:+.4f}]、{sig(mae_ci)})。RMSEは {rmse(err_old):.4f} → {rmse(err_new):.4f}"
      f"(差 {rmse(err_new) - rmse(err_old):+.4f}、{sig(rmse_ci)})。バイアスは {err_old.mean():+.4f} → {err_new.mean():+.4f}。"
      f"基準前半ラップのみ(偏差0)のMAEは {mae(zero_err):.4f}。")
    w(f"- 5分類完全一致率は 旧 {pct(old_mode['accuracy'])} → 新 {pct(new_mode['accuracy'])}(分布最頻区分で判定)、"
      f"平均ペースで分類すると 旧 {pct(metrics[('old', 'mean')]['accuracy'])} → 新 {pct(new_mean['accuracy'])}。"
      f"**開発目標の60〜70%は未達**。最頻クラス固定({pct(acc_base)})に対しても新(a)は {100 * (new_mode['accuracy'] - acc_base):+.2f}pt"
      f"(95%CI [{100 * acc_ci[('new', 'mode')][0]:+.2f}, {100 * acc_ci[('new', 'mode')][1]:+.2f}]pt)で、上回っていない。")
    w(f"- 旧モデルは予測の {old_mode['predicted_counts'][2]}/{n} 件をミドルにしていたため、完全一致率が最頻クラス固定に近く見えていた。"
      f"新モデルはミドル以外を予測する件数が増え、Macro F1 {old_mode['macro_f1']:.3f} → {new_mode['macro_f1']:.3f}、"
      f"ハイペースRecall {pct(old_mode['high_pace_recall'])} → {pct(new_mode['high_pace_recall'])}と見逃しは減ったが、"
      f"超ハイRecallは {pct(old_mode['super_high_recall'])} → {pct(new_mode['super_high_recall'])}で、極端な展開は検出できていない。")
    w("- 馬・騎手のPace Impactは、月より前のデータだけで作っても未知レースのepsの向きを説明でき(3章の表)、"
      "ペース回帰の特徴に加えると検証窓のMAEが下がった(8章)。ただし改善幅は小さく、5分類で60%を超える識別力にはなっていない。")
    w("- 完全一致率を上げるためにミドルへ偏らせる調整や、評価期間に合わせた境界値の変更は行っていない。\n")

    w("## 2. 追加した特徴量\n")
    w(f"全{len(FEATURE_NAMES)}特徴(旧{len(LEGACY_NUMERIC) + len(CATEGORICAL_FEATURES)} + 新規{len(NEW_STRUCT) + len(NEW_HISTORY) + len(NEW_IMPACT)})。"
      "頭数に依存する値は頭数で割るか比率にして比較可能にしている。先行集団=前方から ceil(25%) 頭(最低3頭)。")
    w(md_table(["区分", "特徴量"], [
        ["A 先頭馬", "leader_horse_lead_impact, leader_lead_experience, leader_jockey_lead_impact, leader_horse_x_jockey_lead"],
        ["B 2〜3番手", "chase2/3_horse_chase_impact, chase2/3_jockey_chase_impact, chase2/3_q_gap(先頭との位置差), "
                      "chase2/3_frontness_gap(先頭との先行能力差), contest_lead_rate_index, contest_pressure_index(競り合い)"],
        ["C 先行集団", "front_impact_mean/sum/min/max, front_impact_fast2_mean(上位2頭), front_impact_neg_sum/pos_sum, "
                      "front_jockey_impact_mean/sum/min, front_cluster_q_range/q_std/density, front_lead_rate_sum/max"],
        ["D 内外", "outside_front_ratio, outside/inside_front_impact_pressure, inout_pressure_diff, fast_pressure_outside_share, "
                  "outside/inside_front_impact_mean, 最初のコーナー距離との交互作用(outside_front_ratio_x_first_turn, "
                  "outside_front_ratio_x_short_first_turn, inout_pressure_diff_x_first_turn)"],
        ["E 全頭分布", "q_p10/p25/p50/p75, q_std_all, front/second_group_ratio, n_groups_ratio, q_gap_front_to_rest, "
                      "lead_candidates_ratio, n_q_le25/50_ratio, topfront3_mean_q/min_q(先行力上位馬の位置), "
                      "field_presence_impact_sum/min(出走のみの影響)"],
    ]))
    w("")

    w("## 3. Pace Impact の計算方法\n")
    pi = cfg.pace_impact
    w("1. 実隊列(過去レースの実際の序盤順位)から、隊列の形・コース・馬場だけの構造特徴を作る(馬・騎手の個体情報は入れない)。")
    w(f"2. この構造回帰(Ridge α={pi.base_alpha})を月次ローリング・オリジンの**時系列OOF**で予測し、"
      "`eps = 実ペース偏差 - OOF予測`(秒, 負=予測より速い)を各レースで得る。")
    w("3. 実際の序盤順位で役割を決める: lead=1番手、chase=2〜3番手、front=先行集団(ceil(25%)頭)。"
      "先行集団以外で出走した馬は presence(出走のみ)として別に評価する。")
    w("4. 役割ごとに、馬と騎手を交互に引き算する(バックフィッティング、30回)。"
      "`impact = n / (n + λ) * mean(eps - 相手側のimpact)` で全体平均0へ縮小。")
    w(md_table(["役割", "馬 λ", "騎手 λ"], [[r, f"{pi.horse_lambda[r]:g}", f"{pi.jockey_lambda[r]:g}"] for r in ("lead", "chase", "front")]))
    w(f"\nλは検証窓(2023-09〜2025-08、テスト期間より前)で、月より前のイベントだけで作ったimpactが当月のepsをどれだけ説明するかで選んだ。"
      f"presence は n>={pi.presence_min_n} の馬だけ(λ={pi.presence_lambda:g})。impactは±{pi.impact_clip_sec:g}秒でクリップ。")
    w("5. 月mのスナップショットは「月mより前の月」のレースだけから作る(同月内も見ない)。"
      "Pace Impactは因果効果ではなく、他条件を調整した後の統計的関連度として扱う。\n")

    diag = args.diag
    if (diag / "lambda_grid.csv").exists():
        grid = pd.read_csv(diag / "lambda_grid.csv")
        rows = []
        for role in ("lead", "chase", "front"):
            sub = grid[grid["role"] == role]
            best = sub.loc[sub["gain"].idxmax()]
            used = sub[(sub["lambda_horse"] == pi.horse_lambda[role]) & (sub["lambda_jockey"] == pi.jockey_lambda[role])]
            used_gain = float(used["gain"].iloc[0]) if len(used) else float("nan")
            nojock = sub[(sub["lambda_horse"] == pi.horse_lambda[role]) & (sub["lambda_jockey"] == 100)]
            rows.append([role, str(int(best["n"])), pct(used_gain), f"λ_horse={best['lambda_horse']:g}, λ_jockey={best['lambda_jockey']:g}: {pct(best['gain'])}",
                         pct(float(nojock['gain'].iloc[0])) if len(nojock) else "-"])
        w("### 検証窓での未知レースeps説明力(1 - MSE比, 正なら有効)\n")
        w(md_table(["役割", "イベント数", "採用λ", "グリッド最良", "騎手λ=100(分離弱)"], rows))
        w("")

    w("## 4. ペース相関係数・保持テーブル\n")
    w("- 対象はPace Impactと同じ構造残差eps。単純なペースとの相関は使わない。")
    w("- 母集団: その馬/騎手が走ったコース群(芝/ダ×距離帯)ごとに、初出走〜最終出走の間に行われた同コース群の全レース。"
      "存在フラグ=1(該当役割で走った)と0(走らなかった・別の位置)が必ず混ざる。群ごとにepsを標準化して合算。")
    w(f"- 該当件数 < {pi.corr_min_events} または 非該当件数 < {pi.corr_min_other} は数値を出さず `insufficient_sample`。")
    w("- フラグは presence(出走のみ) / lead / chase / front を別々に評価。馬と騎手のimpactはバックフィッティングで分離。")
    w("- 保持項目: pace_impact_sec, pace_corr, t_stat, n_events, n_population, reliability(=n/(n+20)), status, as_of(最終更新時点)。")
    if (diag / "profile_summary.json").exists():
        summ = json.loads((diag / "profile_summary.json").read_text(encoding="utf-8"))
        rows = [[k.replace("_", " "), f"{v['estimated']:,} / {v['total']:,}",
                 pct(v["share_abs_t_gt_2"], 1) if v["share_abs_t_gt_2"] is not None else "-",
                 f"{v['impact_sd_sec']:.3f}" if v["impact_sd_sec"] is not None and not pd.isna(v["impact_sd_sec"]) else "-"]
                for k, v in summ.items()]
        w("\n2026-10-01時点(`reports/raceverse/pace_v2/pace_profiles_asof_20261001.csv.gz`):\n")
        w(md_table(["対象 役割", "推定できた数 / 全数", "|t|>2の割合(帰無なら約5%)", "impact SD(秒)"], rows))
    w("")

    w("## 5. 学習済みペース回帰モデル\n")
    coef = coefficient_table(P, pd.Timestamp(cfg.backtest.test_start))
    coef_latest = coefficient_table(P, pd.Timestamp("2026-10-01"))
    coef.to_csv(diag / "pace_model_coefficients_asof_20250901.csv", index=False)
    coef_latest.to_csv(diag / "pace_model_coefficients_asof_20261001.csv", index=False)
    w(f"- StandardScaler + Ridge(α={cfg.pace.ridge_alpha:g}) の線形回帰。目的変数は `実前半ラップ - コース標準前半ラップ`(秒)。"
      f"疑似隊列{cfg.pace.training_formation_draws}通り/レースで学習(1レースの重み合計=1)。毎月、その月より前のデータだけで再学習。")
    w(f"- 係数(標準化後, 秒/1SD)の絶対値上位。全係数: `reports/raceverse/pace_v2/pace_model_coefficients_asof_20250901.csv`(評価開始時点)。\n")
    w(md_table(["特徴量", "区分", "標準化係数(秒/SD)", "生単位あたり(秒)"], [
        [r.feature, r.group, f"{r.standardized_coef_sec:+.4f}", f"{r.coef_sec_per_raw_unit:+.4f}"] for r in coef.head(20).itertuples()]))
    imp = coef[coef["group"] == "impact"].head(8)
    w("\nPace Impact系の係数(上位):\n")
    w(md_table(["特徴量", "標準化係数(秒/SD)", "生単位あたり(秒)"], [
        [r.feature, f"{r.standardized_coef_sec:+.4f}", f"{r.coef_sec_per_raw_unit:+.4f}"] for r in imp.itertuples()]))
    w("")

    w("## 6. 予測精度(新旧比較)\n")
    w("### 前半ラップ誤差(秒)\n")
    w(md_table(["", "MAE", "RMSE", "バイアス"], [
        ["基準前半ラップのみ(偏差0)", f"{mae(zero_err):.4f}", f"{rmse(zero_err):.4f}", f"{-zero_err.mean():+.4f}"],
        ["旧(乱択あり)", f"{mae(err_old):.4f}", f"{rmse(err_old):.4f}", f"{err_old.mean():+.4f}"],
        ["新(回帰のみ)", f"{mae(err_new):.4f}", f"{rmse(err_new):.4f}", f"{err_new.mean():+.4f}"]]))
    w(f"\n新-旧の差(ブートストラップ95%CI): MAE {mae(err_new) - mae(err_old):+.4f} [{mae_ci[0]:+.4f}, {mae_ci[1]:+.4f}]、"
      f"RMSE {rmse(err_new) - rmse(err_old):+.4f} [{rmse_ci[0]:+.4f}, {rmse_ci[1]:+.4f}]\n")
    w("### 5分類(ハイペース=超ハイ+ハイ)\n")
    w("予測区分は2通り: (a)10,000回のシミュレーションで最も多かった区分、(b)平均ペース予測を同じ境界値で分類。\n")
    rows = []
    names = {("old", "mode"): "旧 (a)最頻区分", ("new", "mode"): "新 (a)最頻区分", ("old", "mean"): "旧 (b)平均で分類",
             ("new", "mean"): "新 (b)平均で分類"}
    for key, label in names.items():
        m = metrics[key]
        rows.append([label, pct(m["accuracy"]), f"{m['macro_f1']:.4f}", pct(m["high_pace_recall"]), pct(m["super_high_recall"]),
                     "/".join(str(c) for c in m["predicted_counts"])])
    for key, m in metrics.items():
        if key[0] == "baseline":
            rows.append([f"基準: {key[1]}", pct(m["accuracy"]), f"{m['macro_f1']:.4f}", pct(m["high_pace_recall"]),
                         pct(m["super_high_recall"]), "/".join(str(c) for c in m["predicted_counts"])])
    w(md_table(["予測", "完全一致率", "Macro F1", "ハイペースRecall", "超ハイRecall", "予測件数(超ハイ/ハイ/ミドル/スロー/超スロー)"], rows))
    w(f"\n実測件数(超ハイ/ハイ/ミドル/スロー/超スロー): {'/'.join(str(c) for c in np.bincount(actual, minlength=5))}")
    w(f"\n開発目標(完全一致率60〜70%): 新 (a) {pct(metrics[('new', 'mode')]['accuracy'])} / (b) {pct(metrics[('new', 'mean')]['accuracy'])} → **未達**。")
    w("最頻クラス固定との差(95%CI): " + "、".join(
        f"{names[k]} {100 * (metrics[k]['accuracy'] - acc_base):+.2f}pt [{100 * acc_ci[k][0]:+.2f}, {100 * acc_ci[k][1]:+.2f}]" for k in names))
    w(f"\n新(a)−旧(a)の完全一致率差: {100 * (metrics[('new', 'mode')]['accuracy'] - metrics[('old', 'mode')]['accuracy']):+.2f}pt "
      f"[{100 * acc_gain_ci[0]:+.2f}, {100 * acc_gain_ci[1]:+.2f}]\n")
    w("新 (a) の混同行列(行=実測, 列=予測):\n")
    cm = pd.crosstab(pd.Series(actual, name="actual"), pd.Series(preds[("new", "mode")], name="pred")).reindex(
        index=range(5), columns=range(5), fill_value=0)
    w(md_table(["実測＼予測"] + [LABEL[b] for b in PACE_BUCKETS], [[LABEL[PACE_BUCKETS[i]]] + [str(v) for v in cm.iloc[i]] for i in range(5)]))
    w("")
    cm2 = pd.crosstab(pd.Series(actual, name="actual"), pd.Series(preds[("new", "mean")], name="pred")).reindex(
        index=range(5), columns=range(5), fill_value=0)
    w("新 (b) 平均ペースで分類した場合の混同行列:\n")
    w(md_table(["実測＼予測"] + [LABEL[b] for b in PACE_BUCKETS], [[LABEL[PACE_BUCKETS[i]]] + [str(v) for v in cm2.iloc[i]] for i in range(5)]))
    w("")

    w("## 7. 勝率予測・回収率(同一レース・校正後)\n")
    rows = []
    for tag, run in (("旧", old), ("新", new)):
        prob, roi = run["prob"], run["roi"]
        for level in LEVELS:
            p = prob[(prob["model"] == f"raceverse_{level}") & (prob["calibrated"])].iloc[0]
            r = roi[(roi["model"] == f"raceverse_{level}_calibrated") & (roi["buy_rule"] == "top1")].iloc[0]
            rows.append([f"{tag} {level}", f"{p['logloss_binary']:.4f}", f"{p['brier_binary']:.5f}", f"{p['winner_logloss']:.4f}",
                         pct(p["top1_hit_rate"]), f"{r['roi_pct']:.2f}%"])
    p0 = new["prob"][(new["prob"]["model"] == "existing_ranker")].iloc[0]
    r0 = new["roi"][(new["roi"]["model"] == "existing_ranker") & (new["roi"]["buy_rule"] == "top1")].iloc[0]
    rows.append(["既存Ranker", f"{p0['logloss_binary']:.4f}", f"{p0['brier_binary']:.5f}", f"{p0['winner_logloss']:.4f}",
                 pct(p0["top1_hit_rate"]), f"{r0['roi_pct']:.2f}%"])
    w(md_table(["モデル", "LogLoss(二値)", "Brier", "勝ち馬LogLoss", "勝率1位の的中率", "単勝回収率(top1, 確定オッズ)"], rows))
    w("\n回収率は確定オッズによる参考値で、発走前に買える条件の再現ではない。\n")

    w("## 8. 検証\n")
    if (diag / "feature_ablation.csv").exists():
        ab = pd.read_csv(diag / "feature_ablation.csv")
        w("### 特徴群ごとの前半ラップ誤差(検証窓 2023-09〜2025-08、時系列OOF、テスト期間は不使用)\n")
        w(md_table(["特徴", "MAE", "RMSE", "レース数"], [[r.features, f"{r.mae:.4f}", f"{r.rmse:.4f}", str(r.n_races)] for r in ab.itertuples()]))
        w("")
    if (diag / "formation_gap.csv").exists():
        gap = pd.read_csv(diag / "formation_gap.csv")
        w("### 学習に使う隊列と予測に使う隊列の差(検証窓)\n")
        w("実隊列=過去レースの実際の序盤順位、疑似隊列=過去走の抽選(本番と同じ作り方)。"
          "本番は疑似隊列で予測するため、`pseudo->pseudo`が実運用に対応する。\n")
        w(md_table(["学習の隊列", "予測の隊列", "MAE", "RMSE", "レース数"],
                   [[r.train_formation, r.predict_formation, f"{r.mae:.4f}", f"{r.rmse:.4f}", str(r.n_races)] for r in gap.itertuples()]))
        w("")
    if (diag / "outside_front_hypothesis.csv").exists():
        hyp = pd.read_csv(diag / "outside_front_hypothesis.csv")
        w("### 仮説「外枠に先行馬が多いとペースが速くなる」(実隊列, 2018〜2025-08, 頑健標準誤差)\n")
        w("係数は `outside_front_ratio`(先行集団のうち外側(馬番後半)の割合)が1増えたときの前半ラップ偏差(秒、負=速い)。"
          "頭数・距離・コース・馬場・最初のコーナー距離などを調整。\n")
        w(md_table(["モデル", "項", "係数(秒/単位)", "標準誤差", "t", "レース数", "割合0.25→0.75の効果(秒)"], [
            [r.model, r.term, f"{r.coef_sec_per_unit:+.4f}", f"{r.se_hc1:.4f}", f"{r.t:+.2f}", str(r.n_races),
             "-" if pd.isna(r.effect_of_0_25_to_0_75) else f"{r.effect_of_0_25_to_0_75:+.3f}"] for r in
            hyp.rename(columns={"effect_of_0.25_to_0.75": "effect_of_0_25_to_0_75"}).itertuples()]))
        main = hyp[(hyp["model"] == "all races") & (hyp["term"] == "outside_front_ratio")].iloc[0]
        effect = main["effect_of_0.25_to_0.75"]
        if main["t"] > 2:
            verdict = ("外側の先行馬が多いほどペースは**遅く**なる向きで有意(仮説の逆)。"
                       f"割合0.25→0.75で{effect:+.3f}秒と小さく、仮説(速くなる)は支持されない。")
        elif main["t"] < -2:
            verdict = f"外側の先行馬が多いほどペースは速くなる向きで有意(割合0.25→0.75で{effect:+.3f}秒)。"
        else:
            verdict = "有意な関連は見られない(|t|<2)。"
        t_diff = float(hyp[hyp["term"] == "inout_pressure_diff"]["t"].iloc[0])
        t_neg = float(hyp[hyp["term"] == "front_impact_neg_sum"]["t"].iloc[0])
        w(f"\n判定: {verdict} Pace Impactで重みづけした内外の圧力差(inout_pressure_diff)は t={t_diff:+.2f}、"
          f"先行集団の速い馬の合計(front_impact_neg_sum)は t={t_neg:+.2f}(正の係数=負のimpactが大きいほど速い、向きは想定どおり)。")
        w("")

    w("## 9. 制約\n")
    w("- 序盤順位は最初に有効なコーナー通過順(短距離は3角など)で、真の序盤通過順とは一致しない場合がある。馬ごとの区間ラップはDBにない。")
    w("- Pace Impactの個体値はサンプルが少ない馬では0へ縮小される。効果は統計的関連度で、因果の断定ではない。")
    w("- 評価期間の結果を見てモデル設計・λ・境界値を変えていない。診断はすべて 2025-09-01 より前のデータで行った。")
    out_path = diag / "pace_model_v2_report.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report written to {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate CSV/Markdown deliverables for the Ranker feature-group ablation.

Stages (run in this order):
  metrics --period selection|final   assemble scores, compute additive metrics (npz)
  select                             analyse the selection period (full 4095 grid) and write candidates.json
  final                              evaluate the pre-registered candidates on the untouched final period
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src import ranker_group_ablation as ab
    from src import ranker_group_ablation_analysis as an
except ModuleNotFoundError:
    import ranker_group_ablation as ab
    import ranker_group_ablation_analysis as an

ROOT = ab.ROOT
REPORT = ab.OUT_DIR
PERIODS = {
    "selection": ("2024-09-01", "2025-09-01"),
    "final": ("2025-09-01", "2026-09-01"),
}
BASELINE = ab.ALL_ON_INDEX
N_RANDOM_CANDIDATES = 40
N_TOP_CANDIDATES = 30
RANDOM_SEED = 20261011


def md_table(frame: pd.DataFrame, digits: int = 4) -> str:
    def cell(value) -> str:
        if isinstance(value, (float, np.floating)):
            return "" if np.isnan(value) else f"{value:.{digits}f}"
        return str(value)

    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def write_pair(frame: pd.DataFrame, stem: str, directory: Path, title: str, note: str = "", digits: int = 4) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / f"{stem}.csv", index=False, encoding="utf-8")
    text = f"# {title}\n\n{note}\n\n{md_table(frame, digits)}\n" if note else f"# {title}\n\n{md_table(frame, digits)}\n"
    (directory / f"{stem}.md").write_text(text, encoding="utf-8")


def load_context(period: str) -> tuple[an.Context, dict]:
    start, end = PERIODS[period]
    assembled = ab.assemble(REPORT / period, start, end)
    return an.Context(assembled["frame"], assembled["months"]), assembled


def metrics_path(period: str) -> Path:
    return REPORT / period / "metrics.npz"


def cmd_metrics(args: argparse.Namespace) -> None:
    ctx, assembled = load_context(args.period)
    print(f"{args.period}: rows={len(ctx.frame)} races={ctx.n_races} complete combos={int(assembled['complete'].sum())}")
    store = an.compute_all_metrics(ctx, assembled)
    an.save_metrics(metrics_path(args.period), store, ctx.month_labels)


# ---------------------------------------------------------------- 01 classification

def classification_frame() -> pd.DataFrame:
    rows = []
    for key in ab.GROUP_KEYS:
        for name in ab.GROUPS[key]:
            rows.append({"group": key, "group_name": ab.GROUP_NAMES[key], "feature": name,
                         "production_position": ab.COLUMN_INDEX[name] + 1, "bit_position_in_mask": ab.GROUP_KEYS.index(key) + 1})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- select stage

def greedy_backward(values: np.ndarray) -> list[int]:
    """Backward elimination from all-ON on selection logloss (path of combination ids)."""
    current, path = ab.ALL_ON_INDEX, [ab.ALL_ON_INDEX]
    while bin(current).count("1") > 1:
        options = [(values[current & ~(1 << i)], current & ~(1 << i)) for i in range(ab.N_GROUPS) if current & (1 << i)]
        best_value, best = min(options)
        if not best_value < values[current]:
            break
        current = best
        path.append(current)
    return path


def per_group_condition_effect(store: dict, months: np.ndarray) -> pd.DataFrame:
    ll = store["condition_ll"][:, months].sum(axis=1)
    values = ll[..., 0] / ll[..., 1]
    rows = []
    for position, key in enumerate(ab.GROUP_KEYS):
        row = {"group": key, "group_name": ab.GROUP_NAMES[key]}
        for index, label in enumerate(an.CONDITIONS):
            delta = an.marginal_effects(values[:, index], position)["delta"]
            row[f"{label}:mean_delta"] = delta.mean()
        rows.append(row)
    return pd.DataFrame(rows)


def diagnose_groups(contribution: pd.DataFrame, monthly: pd.DataFrame, conditions: pd.DataFrame, noise: float,
                    winners_total: float, winners_by_condition: np.ndarray, winners_by_month: np.ndarray) -> pd.DataFrame:
    """Labels use the bootstrap noise level scaled to the sample size of each slice (noise ~ 1/sqrt(winners))."""
    rows = []
    condition_columns = [c for c in conditions.columns if c.endswith(":mean_delta")]
    condition_noise = noise * np.sqrt(winners_total / winners_by_condition)
    month_noise = noise * np.sqrt(winners_total / winners_by_month)
    for _, row in contribution.iterrows():
        key = row["group"]
        month_values = monthly.loc[key].to_numpy()
        months_improved = int((month_values < 0).sum())
        condition_values = conditions.loc[conditions["group"] == key, condition_columns].iloc[0].to_numpy()
        labels = []
        if row["mean_delta"] > noise and row["share_improved"] < 0.4:
            labels.append("多くの組み合わせで悪化")
        if abs(row["mean_delta"]) <= noise:
            labels.append("追加してもほぼ変化なし")
        if row["mean_delta"] < -noise and row["share_improved"] > 0.6:
            labels.append("安定して改善")
        if row["mean_delta_small_backgrounds_1to3"] > 0 and row["mean_delta_large_backgrounds_8to11"] < 0:
            labels.append("少数構成では悪いが大構成で改善")
        if (month_values < -month_noise).sum() >= 2 and (month_values > month_noise).sum() >= 2:
            labels.append("月により効果が逆転")
        if (condition_values < -condition_noise).any() and (condition_values > condition_noise).any():
            labels.append("レース条件により効果が逆転")
        rows.append({"group": key, "group_name": row["group_name"], "mean_delta_logloss": row["mean_delta"],
                     "share_improved": row["share_improved"], "months_improved": months_improved,
                     "months_total": len(month_values), "noise_threshold": noise,
                     "diagnosis": " / ".join(labels) if labels else "判定なし"})
    return pd.DataFrame(rows)


def overconfidence_group_effect(over: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = {
        "top1_longshot_share": "人気4位以下をTop1にする割合",
        "top1_longshot_actual": "同・実勝率",
        "top1_longshot_pred": "同・予測勝率",
        "top1_longshot_gap": "同・予測−実績",
        "top1_gap_4-6位": "4-6位Top1 予測−実績",
        "top1_gap_7位以下": "7位以下Top1 予測−実績",
        "all_gap_4-6位": "4-6位全馬 予測−実績",
        "all_gap_7位以下": "7位以下全馬 予測−実績",
    }
    for column, label in metrics.items():
        values = an._values_with_pad(pd.Series(over[column].to_numpy(), index=over.index.to_numpy()))
        for position, key in enumerate(ab.GROUP_KEYS):
            effects = an.marginal_effects(values, position)["delta"]
            rows.append({"metric": label, "column": column, "group": key, "group_name": ab.GROUP_NAMES[key],
                         "mean_delta_when_group_added": effects.mean(), "share_increase": (effects > 0).mean(),
                         "n_pairs": len(effects)})
    return pd.DataFrame(rows)


def cmd_select(args: argparse.Namespace) -> None:
    out = REPORT / "selection"
    store = an.load_metrics(metrics_path("selection"))
    labels = [str(x) for x in store["month_labels"]]
    all_months = an.month_mask(store, None)
    scalar = an.scalar_metrics(store, all_months)
    n_done = len(scalar)
    print(f"selection combinations evaluated: {n_done}")
    table = an.metric_table_with_labels(scalar)
    over = an.overconfidence_metrics(store, all_months)
    monthly_ll = an.monthly_metric(store, "winner_logloss")
    for position, label in enumerate(labels):
        table[f"winner_logloss_{label}"] = monthly_ll[table.index.to_numpy(), position]
    for column in ("top1_longshot_share", "top1_longshot_actual", "top1_longshot_pred", "top1_longshot_gap", "all_longshot_gap",
                   "top1_share_4-6位", "top1_actual_4-6位", "top1_pred_4-6位", "top1_share_7位以下", "top1_actual_7位以下", "top1_pred_7位以下"):
        table[column] = over.loc[table.index, column].to_numpy()
    table.insert(0, "combo_id", table.index.to_numpy())
    baseline = table.loc[BASELINE]
    table["delta_logloss_vs_all_on"] = table["winner_logloss"] - baseline["winner_logloss"]
    table["delta_top1_vs_all_on"] = table["top1_hit_rate"] - baseline["top1_hit_rate"]
    table["rank_winner_logloss"] = table["winner_logloss"].rank(method="min").astype(int)
    full = table.sort_values("winner_logloss").reset_index(drop=True)
    full.to_csv(out / "02_all_combinations_selection.csv", index=False, encoding="utf-8")

    cols = ["combo_id", "mask", "groups", "n_features", "winner_logloss", "delta_logloss_vs_all_on", "brier", "top1_hit_rate",
            "top3_recall", "ndcg3", "top1_roi_pct", "top1_longshot_gap"]
    note = (f"選択期間 {labels[0]}〜{labels[-1]}、評価組み合わせ数 {n_done}。多数の組み合わせから最良を選ぶため、"
            "表の上位は選択バイアス（勝者の呪い）で楽観的になる。最終期間の独立検証と併せて解釈すること。")
    write_pair(full[cols].head(20), "03_top20_winner_logloss", out, "Winner logloss 上位20構成（選択期間）", note)
    by_hit = table.sort_values(["top1_hit_rate", "winner_logloss"], ascending=[False, True]).reset_index(drop=True)
    write_pair(by_hit[cols].head(20), "04_top20_top1_hit_rate", out, "Top1的中率 上位20構成（選択期間）", note)

    # 05 contributions
    objective = an._values_with_pad(table["winner_logloss"].set_axis(table.index))
    contribution = an.group_contribution_table(objective, lower_is_better=True)
    for metric, lower in (("top1_hit_rate", False), ("brier", True)):
        values = an._values_with_pad(table[metric].set_axis(table.index))
        extra = an.group_contribution_table(values, lower_is_better=lower)[["group", "mean_delta", "share_improved"]]
        extra.columns = ["group", f"{metric}_mean_delta", f"{metric}_share_improved"]
        contribution = contribution.merge(extra, on="group")
    monthly = an.monthly_contribution(monthly_ll, labels)
    conditions = per_group_condition_effect(store, all_months)

    # noise level: race-bootstrap SE of the leave-one-group-out logloss differences
    ctx, assembled = load_context("selection")
    reference = race_vectors_for(ctx, assembled, BASELINE)
    standard_errors = []
    for position in range(ab.N_GROUPS):
        loo = BASELINE & ~(1 << position)
        boot = an.paired_bootstrap(race_vectors_for(ctx, assembled, loo), reference, n_boot=500)
        standard_errors.append((boot["ci_high"] - boot["ci_low"]) / (2 * 1.96))
    noise = float(np.mean(standard_errors))
    contribution["leave_one_out_bootstrap_se"] = contribution["group"].map(dict(zip(ab.GROUP_KEYS, standard_errors)))
    write_pair(contribution, "05_group_contribution", out, "特徴量グループの平均貢献度（Winner logloss変化、負=改善）",
               "各グループを追加した場合/しなかった場合を、他グループ構成が同一の組で比較（空集合は未評価のため背景から除外）。"
               "delta = value(S+G) − value(S)。", digits=5)
    write_pair(monthly.reset_index().rename(columns={"index": "group"}), "05b_group_contribution_monthly", out,
               "グループ追加の月別平均Δ Winner logloss（負=改善）")
    winners_by_condition = store["condition_ll"][BASELINE][..., 1].sum(axis=0)
    diagnosis = diagnose_groups(contribution, monthly, conditions, noise, store["month_winners"].sum(),
                                winners_by_condition, store["month_winners"])
    write_pair(diagnosis, "05c_group_diagnosis", out, "不要・不安定グループの診断",
               f"中立判定の閾値は、全グループON構成からの1グループ除外差のレース単位bootstrap標準誤差平均 = {noise:.5f}（月・条件別はサンプル数で拡大）。", digits=5)
    write_pair(conditions, "05d_group_by_condition", out, "レース条件別のグループ平均Δ Winner logloss（負=改善）", digits=5)

    # 06 interactions
    interactions = an.interaction_table(objective, monthly_ll, labels)
    write_pair(interactions, "06_group_interactions", out, "グループ間相互作用（Winner logloss、負=相乗改善・正=打ち消し）",
               "I = [v(S+A+B) − v(S+B)] − [v(S+A) − v(S)]。Sは A,B を含まない非空構成。focal=Trueは指定の重点ペア。", digits=5)

    # 07 popularity calibration
    over_table = an.metric_table_with_labels(scalar).join(over)
    pop_rows = []
    for name, combo in (("現行Ranker(全ON)", BASELINE), ("選択期間 Winner logloss 最良", int(full.loc[0, "combo_id"]))):
        for band in an.POP_BANDS:
            pop_rows.append({"構成": name, "combo_id": combo, "mask": ab.combo_index_to_mask(combo), "人気帯": band,
                             "Top1に選ぶ割合": over.loc[combo, f"top1_share_{band}"], "Top1選択数": over.loc[combo, f"top1_n_{band}"],
                             "Top1予測勝率": over.loc[combo, f"top1_pred_{band}"], "Top1実勝率": over.loc[combo, f"top1_actual_{band}"],
                             "Top1予測−実績": over.loc[combo, f"top1_gap_{band}"], "全馬平均予測勝率": over.loc[combo, f"all_pred_{band}"],
                             "全馬実勝率": over.loc[combo, f"all_actual_{band}"], "全馬予測−実績": over.loc[combo, f"all_gap_{band}"]})
    write_pair(pd.DataFrame(pop_rows), "07_popularity_calibration", out, "人気帯別の予測勝率と実勝率（選択期間）",
               "人気帯は確定人気による事後集計であり、モデル入力・温度校正には使っていない。")
    write_pair(overconfidence_group_effect(over), "07b_overconfidence_group_effect", out, "グループ追加による人気薄過信指標の変化",
               "mean_delta_when_group_added は同一背景でのグループ追加差の平均。「予測−実績」が正方向に増えれば過信拡大。", digits=5)
    prob_bin = store["prob_bin"][:, all_months].sum(axis=1)
    rows = []
    for name, combo in (("現行Ranker(全ON)", BASELINE), ("選択期間 Winner logloss 最良", int(full.loc[0, "combo_id"]))):
        for index, label in enumerate(an.PROB_BIN_LABELS):
            n, pred, win = prob_bin[combo, index]
            rows.append({"構成": name, "確率帯": label, "頭数": n, "平均予測勝率": pred / n if n else np.nan, "実勝率": win / n if n else np.nan,
                         "予測−実績": pred / n - win / n if n else np.nan})
    write_pair(pd.DataFrame(rows), "07c_probability_bin_calibration", out, "予測確率帯別キャリブレーション（選択期間）")

    # 08 monthly comparison, baseline vs best
    best = int(full.loc[0, "combo_id"])
    monthly_rows = []
    for position, label in enumerate(labels):
        monthly_rows.append({"month": label, "races": int(store["month_races"][position]),
                             "baseline_winner_logloss": monthly_ll[BASELINE, position], "best_winner_logloss": monthly_ll[best, position],
                             "delta": monthly_ll[best, position] - monthly_ll[BASELINE, position],
                             "baseline_top1": store["top1_hit"][BASELINE, position] / store["month_races"][position],
                             "best_top1": store["top1_hit"][best, position] / store["month_races"][position]})
    write_pair(pd.DataFrame(monthly_rows), "08_monthly_improvement", out, f"月別改善度（選択期間、最良={ab.combo_index_to_mask(best)} vs 全ON）", digits=5)

    # candidates for the untouched final period (decided from selection data only)
    rng = np.random.default_rng(RANDOM_SEED)
    candidates = {BASELINE: "baseline_all_on"}
    for position in range(ab.N_GROUPS):
        candidates.setdefault(BASELINE & ~(1 << position), f"leave_out_{ab.GROUP_KEYS[position]}")
    for combo in full["combo_id"].head(N_TOP_CANDIDATES):
        candidates.setdefault(int(combo), "selection_top_logloss")
    for combo in by_hit["combo_id"].head(10):
        candidates.setdefault(int(combo), "selection_top_top1")
    for size in range(1, ab.N_GROUPS):
        best_of_size = table[table["n_groups"] == size].sort_values("winner_logloss").iloc[0]
        candidates.setdefault(int(best_of_size["combo_id"]), f"best_of_size_{size}")
    for combo in greedy_backward(objective):
        candidates.setdefault(int(combo), "greedy_backward_path")
    pool = [c for c in table["combo_id"] if int(c) not in candidates]
    for combo in rng.choice(pool, size=N_RANDOM_CANDIDATES, replace=False):
        candidates.setdefault(int(combo), "random_for_selection_bias")
    (out / "candidates.json").write_text(json.dumps(sorted(candidates)), encoding="utf-8")
    pd.DataFrame([{"combo_id": c, "mask": ab.combo_index_to_mask(c), "reason": r} for c, r in candidates.items()]).to_csv(
        out / "candidates.csv", index=False, encoding="utf-8")
    print(f"candidates for final period: {len(candidates)}")


def race_vectors_for(ctx: an.Context, assembled: dict, combo: int) -> dict:
    probability = ab.combo_probabilities(ctx.frame, assembled["scores"][combo - 1], assembled["temperature"][combo - 1], ctx.months)
    return an.race_loss_vectors(ctx, probability)


# ---------------------------------------------------------------- final stage

def cmd_final(args: argparse.Namespace) -> None:
    out = REPORT / "final"
    sel_store = an.load_metrics(metrics_path("selection"))
    fin_store = an.load_metrics(metrics_path("final"))
    sel_labels = [str(x) for x in sel_store["month_labels"]]
    fin_labels = [str(x) for x in fin_store["month_labels"]]
    sel_scalar = an.scalar_metrics(sel_store, an.month_mask(sel_store, None))
    fin_scalar = an.scalar_metrics(fin_store, an.month_mask(fin_store, None))
    sel_over = an.overconfidence_metrics(sel_store, an.month_mask(sel_store, None))
    fin_over = an.overconfidence_metrics(fin_store, an.month_mask(fin_store, None))
    fin_monthly = an.monthly_metric(fin_store, "winner_logloss")
    sel_monthly = an.monthly_metric(sel_store, "winner_logloss")
    candidates = pd.read_csv(REPORT / "selection" / "candidates.csv", dtype={"mask": str})
    ctx, assembled = load_context("final")
    reference = race_vectors_for(ctx, assembled, BASELINE)
    rows = []
    for _, candidate in candidates.iterrows():
        combo = int(candidate["combo_id"])
        if combo not in fin_scalar.index:
            continue
        boot = an.paired_bootstrap(race_vectors_for(ctx, assembled, combo), reference, n_boot=args.bootstrap)
        monthly_delta = fin_monthly[combo] - fin_monthly[BASELINE]
        row = {"combo_id": combo, "mask": candidate["mask"], "groups": "+".join(ab.mask_to_groups(candidate["mask"])),
               "n_features": len(ab.mask_to_features(candidate["mask"])), "reason": candidate["reason"],
               "selection_delta_logloss": sel_scalar.loc[combo, "winner_logloss"] - sel_scalar.loc[BASELINE, "winner_logloss"],
               "selection_delta_top1": sel_scalar.loc[combo, "top1_hit_rate"] - sel_scalar.loc[BASELINE, "top1_hit_rate"],
               "final_winner_logloss": fin_scalar.loc[combo, "winner_logloss"],
               "final_delta_logloss": boot["delta_logloss"], "final_delta_ci_low": boot["ci_low"], "final_delta_ci_high": boot["ci_high"],
               "final_p_improve": boot["p_improve"],
               "final_months_improved": int((monthly_delta < 0).sum()), "final_months_total": len(fin_labels),
               "final_brier": fin_scalar.loc[combo, "brier"],
               "final_delta_brier": fin_scalar.loc[combo, "brier"] - fin_scalar.loc[BASELINE, "brier"],
               "final_top1_hit": fin_scalar.loc[combo, "top1_hit_rate"], "final_delta_top1": boot["delta_top1"],
               "final_delta_top1_ci_low": boot["top1_ci_low"], "final_delta_top1_ci_high": boot["top1_ci_high"],
               "final_top3_recall": fin_scalar.loc[combo, "top3_recall"], "final_ndcg3": fin_scalar.loc[combo, "ndcg3"],
               "final_top1_roi_pct(参考)": fin_scalar.loc[combo, "top1_roi_pct"],
               "final_longshot_top1_share": fin_over.loc[combo, "top1_longshot_share"],
               "final_longshot_gap": fin_over.loc[combo, "top1_longshot_gap"],
               "final_delta_longshot_gap": fin_over.loc[combo, "top1_longshot_gap"] - fin_over.loc[BASELINE, "top1_longshot_gap"],
               "final_gap_4-6": fin_over.loc[combo, "top1_gap_4-6位"], "final_gap_7+": fin_over.loc[combo, "top1_gap_7位以下"],
               "final_all_longshot_gap": fin_over.loc[combo, "all_longshot_gap"],
               "final_delta_all_longshot_gap": fin_over.loc[combo, "all_longshot_gap"] - fin_over.loc[BASELINE, "all_longshot_gap"]}
        # pre-declared adoption screens (section 11)
        row["c1_logloss_improved_ci_excludes_0"] = bool(boot["ci_high"] < 0)
        row["c2_top1_not_much_worse(>-1.0pt)"] = bool(boot["delta_top1"] > -0.01)
        row["c3_months_improved>=8of12"] = bool(row["final_months_improved"] >= 8)
        row["c4_longshot_gap_not_worse(<+1.0pt)"] = bool(row["final_delta_longshot_gap"] < 0.01 and row["final_delta_all_longshot_gap"] < 0.005)
        row["c5_selection_period_improved"] = bool(row["selection_delta_logloss"] < 0)
        row["adoption_screens_passed(c1-c5)"] = sum(bool(row[k]) for k in row if k.startswith("c") and k[1].isdigit() and k[2] == "_")
        rows.append(row)
    result = pd.DataFrame(rows).sort_values("final_delta_logloss").reset_index(drop=True)
    result.to_csv(out / "10_final_period_validation.csv", index=False, encoding="utf-8")
    short = result[["combo_id", "mask", "n_features", "reason", "selection_delta_logloss", "final_delta_logloss", "final_delta_ci_low",
                    "final_delta_ci_high", "final_months_improved", "final_delta_top1", "final_delta_longshot_gap",
                    "adoption_screens_passed(c1-c5)"]]
    (out / "10_final_period_validation.md").write_text(
        "# 最終期間の独立検証（Δは候補−現行Ranker、負=改善）\n\n"
        "選択期間の結果だけで決めた候補を、一度も選択に使っていない期間で評価。"
        "CIはレース単位bootstrap(95%)。\n\n" + md_table(short, 5) + "\n", encoding="utf-8")

    # selection-bias diagnostics
    bias_rows = []
    both = result.copy()
    for reason, subset in both.groupby("reason"):
        bias_rows.append({"candidate_group": reason, "n": len(subset), "mean_selection_delta": subset["selection_delta_logloss"].mean(),
                          "mean_final_delta": subset["final_delta_logloss"].mean(),
                          "share_final_improved": (subset["final_delta_logloss"] < 0).mean()})
    rank_corr = both["selection_delta_logloss"].corr(both["final_delta_logloss"], method="spearman")
    top = both[both["reason"] == "selection_top_logloss"]
    write_pair(pd.DataFrame(bias_rows), "10b_selection_bias", out, "選択バイアスの診断",
               f"選択期間と最終期間のΔ logloss のSpearman順位相関（全候補）= {rank_corr:.3f}。"
               f"選択期間上位{len(top)}構成の平均Δ: 選択 {top['selection_delta_logloss'].mean():.5f} → 最終 {top['final_delta_logloss'].mean():.5f}。", digits=5)

    # 09 baseline vs best candidate (best = best selection logloss among candidates, not best final)
    selected = result[result["reason"] == "selection_top_logloss"].sort_values("selection_delta_logloss").iloc[0]
    best = int(selected["combo_id"])
    rows = []
    for label, combo in (("現行Ranker(全ON)", BASELINE), ("選択期間で最良(事前選択)", best)):
        for period_label, scalar, over_frame in (("選択期間", sel_scalar, sel_over), ("最終期間", fin_scalar, fin_over)):
            rows.append({"構成": label, "期間": period_label, "combo_id": combo, "mask": ab.combo_index_to_mask(combo),
                         "n_features": len(ab.mask_to_features(ab.combo_index_to_mask(combo))),
                         **scalar.loc[combo].to_dict(), "top1_longshot_gap": over_frame.loc[combo, "top1_longshot_gap"],
                         "top1_gap_4-6位": over_frame.loc[combo, "top1_gap_4-6位"], "top1_gap_7位以下": over_frame.loc[combo, "top1_gap_7位以下"]})
    write_pair(pd.DataFrame(rows), "09_baseline_vs_best", out, "現行Rankerと選択期間最良構成の比較", digits=5)
    month_rows = []
    for position, label in enumerate(fin_labels):
        month_rows.append({"month": label, "races": int(fin_store["month_races"][position]),
                           "baseline_winner_logloss": fin_monthly[BASELINE, position], "best_winner_logloss": fin_monthly[best, position],
                           "delta": fin_monthly[best, position] - fin_monthly[BASELINE, position],
                           "baseline_top1": fin_store["top1_hit"][BASELINE, position] / fin_store["month_races"][position],
                           "best_top1": fin_store["top1_hit"][best, position] / fin_store["month_races"][position]})
    write_pair(pd.DataFrame(month_rows), "08b_monthly_improvement_final", out, f"月別改善度（最終期間、構成 {ab.combo_index_to_mask(best)} vs 全ON）", digits=5)
    bands = []
    for label, combo in (("現行Ranker(全ON)", BASELINE), ("選択期間最良", best)):
        for band in an.POP_BANDS:
            bands.append({"構成": label, "人気帯": band, "Top1選択割合": fin_over.loc[combo, f"top1_share_{band}"],
                          "Top1選択数": fin_over.loc[combo, f"top1_n_{band}"], "Top1予測勝率": fin_over.loc[combo, f"top1_pred_{band}"],
                          "Top1実勝率": fin_over.loc[combo, f"top1_actual_{band}"], "Top1予測−実績": fin_over.loc[combo, f"top1_gap_{band}"]})
    write_pair(pd.DataFrame(bands), "07d_popularity_calibration_final", out, "人気帯別の予測勝率と実勝率（最終期間）", digits=4)
    print("final stage written")


def cmd_classification(args: argparse.Namespace) -> None:
    write_pair(classification_frame(), "01_group_classification", REPORT, "86特徴量の12グループ分類",
               "グループ分類は全て本番 RANKER_MARGIN_CORRECTION_FEATURES (86) と完全一致（重複・未分類・過不足なし）。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["classification", "metrics", "select", "final"])
    parser.add_argument("--period", choices=list(PERIODS), default="selection")
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    {"classification": cmd_classification, "metrics": cmd_metrics, "select": cmd_select, "final": cmd_final}[args.command](args)


if __name__ == "__main__":
    main()

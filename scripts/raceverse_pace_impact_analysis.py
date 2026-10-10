"""RACEVERSE ペース改修の訓練側診断。テスト期間(2025-09以降)のデータは一切使わない。

  1. 縮小係数lambdaの選定表(検証窓 2023-09〜2025-08 の未知レースでeps説明力を比較)
  2. 特徴群ごとの時系列OOF誤差(旧特徴 → +構造 → +履歴 → +Pace Impact → 全部)
  3. 学習に使う隊列(実隊列 / 疑似隊列)と本番予測に使う隊列の差の検証
  4. 「外枠に先行馬が多いとペースが速くなる」仮説の検証(実隊列, OLS + HC1頑健標準誤差)
  5. 馬・騎手のPace Impact / ペース相関テーブル(最終更新時点つき)

  PYTHONPATH=. .venv/bin/python scripts/raceverse_pace_impact_analysis.py
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from raceverse.config import REPORT_DIR, load_config
from raceverse.pace_correlation import pace_profile_table
from raceverse.pace_features import (CATEGORICAL_FEATURES, FEATURE_INDEX, FEATURE_NAMES, LEGACY_COLUMNS,
                                     LEGACY_NUMERIC, NEW_HISTORY, NEW_IMPACT, NEW_STRUCT)
from raceverse.pace_impact import actual_formation_table, out_of_sample_gain
from raceverse.pace_regression import fit_pace_regressor, rolling_oof_predictions
from raceverse.pipeline import prepare

VAL_START = pd.Timestamp("2023-09-01")
VAL_END = pd.Timestamp("2025-09-01")   # テスト開始日。これ以降は参照しない
PROFILE_AS_OF = pd.Timestamp("2026-10-01")


def _idx(names):
    return [FEATURE_INDEX[n] for n in names]


def lambda_grid(P) -> pd.DataFrame:
    rows = []
    for role in ("lead", "chase", "front"):
        for lam_h in (4, 8, 16, 24, 32, 64):
            for lam_j in (10, 20, 30, 100):
                g = out_of_sample_gain(P.ds.impacts, role, VAL_START, VAL_END, P.ds.base_month, lam_h, lam_j)
                rows.append({"role": role, "lambda_horse": lam_h, "lambda_jockey": lam_j, **g})
    return pd.DataFrame(rows)


def feature_ablation(P, alpha: float) -> pd.DataFrame:
    st = P.store
    d = st.draws
    dates = pd.Series(pd.to_datetime(st.date))
    y = st.y.reshape(-1, d)[:, 0]
    race_dates = pd.to_datetime(st.race_table["date"])
    mask = ((race_dates >= VAL_START) & (race_dates < VAL_END)).to_numpy()
    sets = {
        "old features": LEGACY_COLUMNS,
        "+ formation structure": _idx(LEGACY_NUMERIC + NEW_STRUCT + CATEGORICAL_FEATURES),
        "+ structure + horse history": _idx(LEGACY_NUMERIC + NEW_STRUCT + NEW_HISTORY + CATEGORICAL_FEATURES),
        "+ structure + Pace Impact": _idx(LEGACY_NUMERIC + NEW_STRUCT + NEW_IMPACT + CATEGORICAL_FEATURES),
        "all (adopted)": list(range(len(FEATURE_NAMES))),
    }
    rows = [{"features": "constant mean (validation mean)", "mae": float(np.abs(y[mask] - y[mask].mean()).mean()),
             "rmse": float(y[mask].std()), "n_races": int(mask.sum())},
            {"features": "reference baseline only (pace_delta=0)", "mae": float(np.abs(y[mask]).mean()),
             "rmse": float(np.sqrt((y[mask] ** 2).mean())), "n_races": int(mask.sum())}]
    for name, cols in sets.items():
        pred = rolling_oof_predictions(st.X[:, cols], st.y, st.w, dates, alpha, VAL_START, min_rows=2000 * d // 2)
        p = pred.reshape(-1, d).mean(axis=1)
        ok = mask & np.isfinite(p)
        e = y[ok] - p[ok]
        rows.append({"features": name, "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())),
                     "n_races": int(ok.sum())})
    return pd.DataFrame(rows)


def formation_gap(P, alpha: float) -> pd.DataFrame:
    """学習・予測に使う隊列(実隊列 / 疑似隊列)の組み合わせごとの検証窓の誤差。"""
    st, ds, cfg = P.store, P.ds, P.cfg
    d = st.draws
    positions, xa, ya, da, _, _ = actual_formation_table(ds, cfg, with_impacts=True)
    tbl = st.race_table
    row_of = {int(p): i for i, p in enumerate(tbl["race_pos"])}
    keep = np.array([int(p) in row_of for p in positions])
    positions, xa, ya, da = positions[keep], xa[keep], ya[keep], pd.to_datetime(da[keep]).reset_index(drop=True)
    order = np.array([row_of[int(p)] for p in positions])
    xp = st.X.reshape(-1, d, st.X.shape[1])[order]
    months = pd.date_range(VAL_START, VAL_END - pd.offsets.MonthBegin(1), freq="MS")
    preds = {k: [] for k in ("actual->actual", "pseudo->pseudo", "actual->pseudo", "pseudo->actual")}
    truth = []
    start = pd.Timestamp(cfg.pace.train_start) + pd.DateOffset(years=2)
    for month in months:
        train = (da < month) & (da >= start)
        test = ((da >= month) & (da < month + pd.offsets.MonthBegin(1))).to_numpy()
        if not test.any() or train.sum() < 2000:
            continue
        tr = train.to_numpy()
        m_act = fit_pace_regressor(xa[tr], ya[tr], np.ones(tr.sum()), alpha)
        m_pse = fit_pace_regressor(xp[tr].reshape(-1, xp.shape[2]), np.repeat(ya[tr], d),
                                   np.full(tr.sum() * d, 1.0 / d), alpha)
        xp_test = xp[test].reshape(-1, xp.shape[2])
        preds["actual->actual"].append(m_act.predict(xa[test]))
        preds["pseudo->actual"].append(m_pse.predict(xa[test]))
        preds["actual->pseudo"].append(m_act.predict(xp_test).reshape(-1, d).mean(axis=1))
        preds["pseudo->pseudo"].append(m_pse.predict(xp_test).reshape(-1, d).mean(axis=1))
        truth.append(ya[test])
    y = np.concatenate(truth)
    rows = []
    for name, parts in preds.items():
        e = y - np.concatenate(parts)
        train_kind, test_kind = name.split("->")
        rows.append({"train_formation": train_kind, "predict_formation": test_kind,
                     "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "n_races": int(len(y))})
    return pd.DataFrame(rows)


def ols_hc1(x: np.ndarray, y: np.ndarray):
    n = len(y)
    x1 = np.column_stack([np.ones(n), x])
    beta = np.linalg.lstsq(x1, y, rcond=None)[0]
    resid = y - x1 @ beta
    bread = np.linalg.pinv(x1.T @ x1)
    meat = x1.T @ (x1 * (resid ** 2)[:, None])
    cov = bread @ meat @ bread * n / (n - x1.shape[1])
    return beta, np.sqrt(np.diag(cov))


def outside_front_hypothesis(P) -> pd.DataFrame:
    """外枠(馬番後半)の先行馬が多いほどペースが速くなるか。実隊列・テスト前の期間だけ。"""
    positions, x, y, dates, _, _ = actual_formation_table(P.ds, P.cfg, with_impacts=True)
    dates = pd.to_datetime(dates)
    sel = ((dates >= pd.Timestamp("2018-01-01")) & (dates < VAL_END)).to_numpy()
    x, y = x[sel], y[sel]
    names = ["field_size", "distance_km", "is_turf", "first_turn_distance_100m", "short_first_turn", "front_group_ratio",
             "course_week"] + [n for n in CATEGORICAL_FEATURES if not n.endswith("_01") and n != "going_turf_1"
                               and n != "going_dirt_1"]
    controls = x[:, _idx(names)]
    short = x[:, FEATURE_INDEX["short_first_turn"]] > 0
    rows = []

    def fit(label, columns, mask=None, scale=1.0):
        sub = np.ones(len(y), dtype=bool) if mask is None else mask
        design = np.column_stack([x[sub][:, _idx(columns)], controls[sub]])
        keep = design.std(axis=0) > 0
        keep[: len(columns)] = True
        beta, se = ols_hc1(design[:, keep], y[sub])
        for k, col in enumerate(np.array(columns)):
            rows.append({"model": label, "term": col, "coef_sec_per_unit": float(beta[1 + k]),
                         "se_hc1": float(se[1 + k]), "t": float(beta[1 + k] / se[1 + k]), "n_races": int(sub.sum()),
                         "effect_of_0.25_to_0.75": float(beta[1 + k] * 0.5) if col == "outside_front_ratio" else np.nan})

    fit("all races", ["outside_front_ratio"])
    fit("short first turn (<350m)", ["outside_front_ratio"], short)
    fit("long first turn (>=350m)", ["outside_front_ratio"], ~short)
    fit("impact-weighted (all races)", ["outside_front_ratio", "inout_pressure_diff", "front_impact_neg_sum"])
    return pd.DataFrame(rows)


def profile_outputs(P, out: Path) -> dict:
    table = pace_profile_table(P.ds, PROFILE_AS_OF)
    keep = table[(table["n_events"] >= 5) | (table["flag"] == "presence") & (table["status"] == "estimated")]
    keep.to_csv(out / "pace_profiles_asof_20261001.csv.gz", index=False)
    est = table[table["status"] == "estimated"]
    summary = {}
    for kind in ("horse", "jockey"):
        for flag in ("lead", "chase", "front", "presence"):
            sub = est[(est["entity_type"] == kind) & (est["flag"] == flag)]
            summary[f"{kind}_{flag}"] = {
                "estimated": int(len(sub)), "total": int(((table["entity_type"] == kind) & (table["flag"] == flag)).sum()),
                "share_abs_t_gt_2": float((sub["t_stat"].abs() > 2).mean()) if len(sub) else None,
                "impact_sd_sec": float(sub["pace_impact_sec"].std()) if len(sub) else None,
            }
    fast = est[(est["entity_type"] == "jockey") & (est["flag"] == "lead")].nsmallest(8, "pace_impact_sec")
    slow = est[(est["entity_type"] == "jockey") & (est["flag"] == "lead")].nlargest(5, "pace_impact_sec")
    fast.to_csv(out / "jockey_lead_fastest.csv", index=False)
    slow.to_csv(out / "jockey_lead_slowest.csv", index=False)
    horses = est[(est["entity_type"] == "horse") & (est["flag"] == "lead") & (est["n_events"] >= 8)]
    horses.nsmallest(10, "pace_impact_sec").to_csv(out / "horse_lead_fastest.csv", index=False)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT_DIR / "pace_v2")
    parser.add_argument("--skip-gap", action="store_true")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    P = prepare(cfg)
    alpha = cfg.pace.ridge_alpha
    lambda_grid(P).to_csv(out / "lambda_grid.csv", index=False)
    feature_ablation(P, alpha).to_csv(out / "feature_ablation.csv", index=False)
    if not args.skip_gap:
        formation_gap(P, alpha).to_csv(out / "formation_gap.csv", index=False)
    outside_front_hypothesis(P).to_csv(out / "outside_front_hypothesis.csv", index=False)
    summary = profile_outputs(P, out)
    (out / "profile_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"diagnostics written to {out}")


if __name__ == "__main__":
    main()

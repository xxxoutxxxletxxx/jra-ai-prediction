"""コースバイアス追加版の評価: 相対走破時計のMAE/RMSE、コース別・脚質別・枠番別の改善度。

脚質・枠番の区分は評価専用で、実際の序盤位置(結果)から付ける。予測入力には使わない。
差分は「追加版 - 既存」。logloss・Brier・MAEは負なら改善、Top1的中率・単勝回収率は正なら改善。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from raceverse.config import CourseBiasConfig
from raceverse.course_bias import STYLE_NAMES, style_from_q

EPS = 1e-6
MIN_GROUP_RUNNERS = 300


def actual_relative_time(df: pd.DataFrame) -> pd.Series:
    """実際の相対走破時計 = 走破時計 - 同レース完走馬の平均走破時計(秒)。"""
    t = df["time_sec"].where((df["finish"] > 0) & df["time_sec"].notna())
    return t - t.groupby(df["race_id"]).transform("mean")


def relative_time_metrics(df: pd.DataFrame) -> Dict[str, float]:
    z = actual_relative_time(df)
    ok = z.notna() & df["mean_rel_time_sec"].notna()
    err = (df.loc[ok, "mean_rel_time_sec"] - z[ok]).to_numpy()
    zero = z[ok].to_numpy()
    return {"n": int(ok.sum()), "mae": float(np.abs(err).mean()), "rmse": float(np.sqrt((err ** 2).mean())),
            "corr": float(np.corrcoef(df.loc[ok, "mean_rel_time_sec"], z[ok])[0, 1]),
            "mae_zero_pred": float(np.abs(zero).mean()), "rmse_zero_pred": float(np.sqrt((zero ** 2).mean()))}


def _race_top1(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.loc[df.groupby("race_id")[col].idxmax()]


def _group_metrics(g: pd.DataFrame, race_level: bool) -> Dict[str, float]:
    y = g["target"].to_numpy(dtype=float)
    out: Dict[str, float] = {"n_runners": int(len(g)), "n_races": int(g["race_id"].nunique()), "win_rate": float(y.mean())}
    for tag in ("b", "v"):
        p = np.clip(g[f"p_{tag}"].to_numpy(dtype=float), EPS, 1 - EPS)
        out[f"logloss_{tag}"] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
        out[f"brier_{tag}"] = float(((p - y) ** 2).mean())
        out[f"mean_p_{tag}"] = float(p.mean())
        ok = g["z"].notna()
        out[f"mae_time_{tag}"] = float((g.loc[ok, f"rel_{tag}"] - g.loc[ok, "z"]).abs().mean()) if ok.any() else np.nan
        if race_level:
            top = _race_top1(g, f"p_{tag}")
            out[f"top1_hit_{tag}"] = float(top["target"].mean())
            out[f"top1_roi_{tag}"] = float(top["win_payout"].fillna(0.0).sum() / (100.0 * len(top)) * 100.0)
            winners = g[g["target"] == 1]
            out[f"winner_logloss_{tag}"] = float(-np.log(np.clip(winners[f"p_{tag}"].to_numpy(dtype=float), EPS, 1.0)).mean())
    for key in ("logloss", "brier", "mae_time"):
        out[f"d_{key}"] = out[f"{key}_v"] - out[f"{key}_b"]
    if race_level:
        for key in ("top1_hit", "top1_roi"):
            out[f"d_{key}"] = out[f"{key}_v"] - out[f"{key}_b"]
        out["d_winner_logloss"] = out["winner_logloss_v"] - out["winner_logloss_b"]
    out["calib_gap_b"] = out["mean_p_b"] - out["win_rate"]
    out["calib_gap_v"] = out["mean_p_v"] - out["win_rate"]
    return out


def course_bias_comparison(subs: Dict[str, pd.DataFrame], races: pd.DataFrame,
                           pairs: List[Tuple[str, str]], out_dir: Path) -> Dict:
    cfg = CourseBiasConfig()
    rows = []
    overview = {}
    for base, var in pairs:
        if base not in subs or var not in subs:
            continue
        keep = ["race_id", "horse_id", "wakuban", "target", "p_cal", "mean_rel_time_sec", "win_payout", "q_early_actual",
                "early_rank_actual", "time_sec", "finish"]
        b, v = subs[base][keep], subs[var][["race_id", "horse_id", "p_cal", "mean_rel_time_sec"]]
        m = b.merge(v, on=["race_id", "horse_id"], suffixes=("_b", "_v"))
        m = m.rename(columns={"p_cal_b": "p_b", "p_cal_v": "p_v", "mean_rel_time_sec_b": "rel_b",
                              "mean_rel_time_sec_v": "rel_v"})
        m["z"] = actual_relative_time(m)
        attrs = races[["race_id", "track", "surface", "distance_m"]].drop_duplicates("race_id")
        m = m.merge(attrs, on="race_id", how="left")
        m["distance_band"] = pd.cut(m["distance_m"], [0, 1300, 1600, 2000, 9999],
                                    labels=["~1300", "1400-1600", "1700-2000", "2100+"]).astype(str)
        q = m["q_early_actual"].to_numpy(dtype=float)
        style = style_from_q(np.nan_to_num(q, nan=1.0), m["early_rank_actual"].to_numpy() == 1, cfg.front_q, cfg.stalk_q)
        m["style"] = np.where(np.isfinite(q), np.array(STYLE_NAMES, dtype=object)[style], "unknown")
        m["wakuban_k"] = m["wakuban"].astype("Int64").astype(str)
        m["all"] = "all"
        dims = [("all", True), ("surface", True), ("track", True), ("distance_band", True), ("style", False), ("wakuban_k", False)]
        start = len(rows)
        for dim, race_level in dims:
            for value, g in m.groupby(dim):
                if dim != "all" and len(g) < MIN_GROUP_RUNNERS:
                    continue
                rows.append({"pair": f"{base}->{var}", "dimension": dim, "value": str(value), **_group_metrics(g, race_level)})
        table = pd.DataFrame(rows[start:])
        ov = {}
        for dim, g in table[table["dimension"] != "all"].groupby("dimension"):
            ov[dim] = {"groups": int(len(g)), "logloss_improved": int((g["d_logloss"] < 0).sum()),
                       "mae_time_improved": int((g["d_mae_time"] < 0).sum())}
        overview[f"{base}->{var}"] = ov
    if not rows:
        return {}
    pd.DataFrame(rows).to_csv(out_dir / "course_bias_group_gains.csv", index=False)
    return {"course_bias_overview": overview}

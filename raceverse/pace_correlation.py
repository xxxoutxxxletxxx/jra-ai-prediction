"""馬・騎手ごとの「先頭/先行集団にいること」と前半ペース残差の相関(Pace Impactとは別の指標)。

- 相関の対象は構造要因を除いたOOF残差 eps(raceverse.pace_impact)。単純なペースとの相関は使わない。
- 母集団: その馬/騎手が走った各コース群(芝/ダ x 距離帯)ごとに、初出走日〜最終出走日の間に行われた同コース群の全レース。
  存在フラグ=1(該当役割で走った)と0(走らなかった・別の位置で走った)の両方が必ず入るので、常に1になる設計を避けられる。
- 群ごとにepsを標準化してから合算する(群ごとの分散の違いで相関が歪まないように)。
- サンプルが足りない(該当件数 < corr_min_events または 非該当件数 < corr_min_other)は相関を出さず status=insufficient_sample。
- フラグ: presence(出走しただけ) / lead(逃げ) / chase(2〜3番手) / front(先行集団)。presenceと役割は別々に評価する。
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from raceverse.config import PaceImpactConfig
from raceverse.pace_features import front_count_array
from raceverse.periods import timestamp_period_index

FLAGS = ("presence", "lead", "chase", "front")


def _population_sums(eps_g: pd.DataFrame, first: np.ndarray, last: np.ndarray):
    """群gのレース(日付昇順)に対し、各エンティティの [first, last] 区間の件数・Σz・Σz^2。"""
    eps_g = eps_g.sort_values("date")
    day = eps_g["date"].to_numpy().astype("datetime64[D]").astype(np.int64)
    z = eps_g["z"].to_numpy()
    c1 = np.concatenate([[0.0], np.cumsum(z)])
    c2 = np.concatenate([[0.0], np.cumsum(z * z)])
    lo = np.searchsorted(day, first, side="left")
    hi = np.searchsorted(day, last, side="right")
    return hi - lo, c1[hi] - c1[lo], c2[hi] - c2[lo]


def correlation_table(runs: pd.DataFrame, race_eps: pd.DataFrame, as_of: pd.Timestamp, key: str,
                      cfg: PaceImpactConfig) -> pd.DataFrame:
    """key='horse_idx' または 'jockey_idx'。as_of より前のレースだけを使う。"""
    eps = race_eps[(race_eps["date"] < as_of) & race_eps["eps"].notna()].copy()
    stats = eps.groupby("group")["eps"].agg(["mean", "std"])
    eps["z"] = (eps["eps"] - eps["group"].map(stats["mean"])) / eps["group"].map(stats["std"])
    z_by_race = eps.set_index("race_id")["z"]
    group_by_race = eps.set_index("race_id")["group"]
    frame = runs[["race_id", "date", key, "early_rank", "field_size"]].copy()
    frame["z"] = frame["race_id"].map(z_by_race)
    frame["group"] = frame["race_id"].map(group_by_race)
    frame = frame[frame["z"].notna() & (frame[key] >= 0)]
    rank = frame["early_rank"].to_numpy()
    kf = front_count_array(frame["field_size"].to_numpy(dtype=float))
    flags = {
        "presence": np.ones(len(frame), dtype=bool),
        "lead": rank == 1,
        "chase": (rank >= 2) & (rank <= 3),
        "front": (rank >= 1) & (rank <= kf),
    }
    pop_parts: List[pd.DataFrame] = []
    flag_parts: Dict[str, List[pd.DataFrame]] = {f: [] for f in FLAGS}
    for g, eps_g in eps.groupby("group"):
        runs_g = frame[frame["group"] == g]
        span = runs_g.groupby(key)["date"].agg(["min", "max"])
        n_pop, s1, s2 = _population_sums(eps_g, span["min"].to_numpy().astype("datetime64[D]").astype(np.int64),
                                         span["max"].to_numpy().astype("datetime64[D]").astype(np.int64))
        pop_parts.append(pd.DataFrame({"n_pop": n_pop, "s1": s1, "s2": s2}, index=span.index))
        for name in FLAGS:
            sub = runs_g[flags[name][frame["group"].to_numpy() == g]]
            agg = sub.groupby(key)["z"].agg(n1="count", sum1="sum")
            flag_parts[name].append(agg)
    pop = pd.concat(pop_parts).groupby(level=0).sum()
    rows = []
    for name in FLAGS:
        agg = pd.concat(flag_parts[name]).groupby(level=0).sum() if flag_parts[name] else pd.DataFrame()
        joined = pop.join(agg, how="left").fillna({"n1": 0.0, "sum1": 0.0})
        n_all, n1 = joined["n_pop"].to_numpy(dtype=float), joined["n1"].to_numpy(dtype=float)
        n0 = n_all - n1
        with np.errstate(divide="ignore", invalid="ignore"):
            m1 = joined["sum1"].to_numpy() / n1
            m0 = (joined["s1"].to_numpy() - joined["sum1"].to_numpy()) / n0
            var = joined["s2"].to_numpy() / n_all - (joined["s1"].to_numpy() / n_all) ** 2
            r = (m1 - m0) / np.sqrt(var) * np.sqrt((n1 / n_all) * (n0 / n_all))
            t = r * np.sqrt(np.maximum(n_all - 2, 1) / np.maximum(1 - r ** 2, 1e-12))
        enough = (n1 >= cfg.corr_min_events) & (n0 >= cfg.corr_min_other)
        rows.append(pd.DataFrame({
            key: joined.index.to_numpy(), "flag": name, "n_events": n1.astype(int), "n_population": n_all.astype(int),
            "pace_corr": np.where(enough, r, np.nan), "t_stat": np.where(enough, t, np.nan),
            "reliability": n1 / (n1 + cfg.corr_reliability_k),
            "status": np.where(enough, "estimated", "insufficient_sample"),
        }))
    return pd.concat(rows, ignore_index=True)


def pace_profile_table(ds, as_of: pd.Timestamp) -> pd.DataFrame:
    """馬・騎手ごとの Pace Impact(秒) / ペース相関 / サンプル数 / 信頼性 / 最終更新時点。"""
    profiles = ds.impacts
    cfg = profiles.cfg
    month = timestamp_period_index(as_of, ds.base_month, ds.cfg.refit_unit)
    impact: Dict[str, Dict[str, np.ndarray]] = {"horse": {}, "jockey": {}}
    for role in ("lead", "chase", "front"):
        a, b, _, _ = profiles.role_impacts(role, month)
        impact["horse"][role], impact["jockey"][role] = a, b
    impact["horse"]["presence"] = profiles.presence_impacts(month)[0]
    horse_ids = ds.runs.drop_duplicates("horse_idx").set_index("horse_idx")["horse_id"]
    jockey_codes = {idx: code for code, idx in ds.jockey_codes.items()}
    tables = []
    for kind, key in (("horse", "horse_idx"), ("jockey", "jockey_idx")):
        corr = correlation_table(ds.runs, profiles.race_eps, as_of, key, cfg)
        corr = corr.rename(columns={key: "entity_idx"})
        corr["entity_type"] = kind
        corr["entity_id"] = corr["entity_idx"].map(horse_ids if kind == "horse" else jockey_codes)
        values = []
        for idx, flag in zip(corr["entity_idx"].to_numpy(), corr["flag"].to_numpy()):
            arr = impact[kind].get(flag)
            values.append(float(arr[idx]) if arr is not None and idx < len(arr) else np.nan)
        corr["pace_impact_sec"] = np.clip(values, -cfg.impact_clip_sec, cfg.impact_clip_sec)
        tables.append(corr)
    out = pd.concat(tables, ignore_index=True)
    out["as_of"] = as_of.strftime("%Y-%m-%d")
    # 騎手のpresenceはPace Impactを推定しない(馬の出走自体の影響のみ別評価)
    out.loc[(out["entity_type"] == "jockey") & (out["flag"] == "presence"), "pace_impact_sec"] = np.nan
    return out[["entity_type", "entity_id", "flag", "pace_impact_sec", "pace_corr", "t_stat", "n_events",
                "n_population", "reliability", "status", "as_of"]]

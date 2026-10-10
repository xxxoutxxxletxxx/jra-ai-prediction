"""馬・騎手の Pace Impact(秒): 「その馬/騎手が逃げ・追走・先行集団にいたレースで、実際の前半ラップが構造要因だけの予測からどれだけ外れたか」。

手順
  1. 実隊列(過去レースの実際の序盤順位)から構造特徴(隊列の形・コース・馬場。馬・騎手の個体情報は入れない)を作り、
     月次ローリングの時系列OOFでペース偏差を回帰する。  eps = 実ペース偏差 - OOF予測   (負=予測より速かった)
  2. 役割(lead / chase / front)別に、該当順位で走った過去レースの eps を馬・騎手で集計する。
     馬と騎手が同じ要因を二重に説明しないよう、馬と騎手を交互に引き算するバックフィッティングで分離する。
       impact = n / (n + lambda) * mean(eps - 相手側の影響)     (負ほどペースを速くする。因果ではなく調整後の関連度)
  3. 月mのスナップショットは「月mより前の月のレース」だけを使う(同月内のレースも見ない=安全側)。
     epsそのものが時系列OOF由来なので、未来のラップはどの段階にも入らない。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from raceverse.config import CACHE_DIR, PaceImpactConfig, RaceverseConfig
from raceverse.formation_sampler import arrange_formation
from raceverse.jockey_profiles import month_index
from raceverse.pace_features import STRUCT_COLUMNS, front_count_array, pace_features
from raceverse.pace_regression import rolling_oof_predictions
from raceverse.pace_residuals import group_key
from raceverse.schemas import Formation

LOGGER = logging.getLogger(__name__)
ROLES = ("lead", "chase", "front")
CACHE_VERSION = 1


@dataclass
class RoleEvents:
    """月昇順に並んだ役割イベント。jockey=-1 は騎手不明。"""
    month: np.ndarray
    horse: np.ndarray
    jockey: np.ndarray
    eps: np.ndarray

    def upto(self, month: int) -> "RoleEvents":
        end = int(np.searchsorted(self.month, month, side="left"))
        return RoleEvents(self.month[:end], self.horse[:end], self.jockey[:end], self.eps[:end])


def backfit_impacts(events: RoleEvents, n_horses: int, n_jockeys: int, lam_horse: float, lam_jockey: float,
                    iters: int, separate_jockey: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """馬impact a_h と騎手impact b_j を交互に推定する。戻り値: (a, b, 馬の件数, 騎手の件数)。"""
    horse, eps = events.horse, events.eps
    jockey = np.where(events.jockey < 0, n_jockeys, events.jockey)
    cnt_h = np.bincount(horse, minlength=n_horses).astype(float)
    cnt_j = np.bincount(jockey, minlength=n_jockeys + 1).astype(float)[:n_jockeys]
    a = np.zeros(n_horses)
    b = np.zeros(n_jockeys + 1)
    for _ in range(max(iters, 1)):
        a = np.bincount(horse, weights=eps - b[jockey], minlength=n_horses) / (cnt_h + lam_horse)
        if separate_jockey:
            b = np.bincount(jockey, weights=eps - a[horse], minlength=n_jockeys + 1) / (
                np.append(cnt_j, 0.0) + lam_jockey)
            b[n_jockeys] = 0.0
    return a, b[:n_jockeys], cnt_h, cnt_j


@dataclass
class PaceImpactProfiles:
    cfg: PaceImpactConfig
    n_horses: int
    n_jockeys: int
    roles: Dict[str, RoleEvents]
    presence: RoleEvents
    run_month: np.ndarray
    run_horse: np.ndarray
    run_lead: np.ndarray
    race_eps: pd.DataFrame        # race_id, date, group, y, yhat, eps(時系列OOF)

    def role_impacts(self, role: str, month: int, lam_horse: Optional[float] = None,
                     lam_jockey: Optional[float] = None, separate_jockey: bool = True):
        lam_h = self.cfg.horse_lambda[role] if lam_horse is None else lam_horse
        lam_j = self.cfg.jockey_lambda[role] if lam_jockey is None else lam_jockey
        ev = self.roles[role].upto(month)
        return backfit_impacts(ev, self.n_horses, self.n_jockeys, lam_h, lam_j, self.cfg.backfit_iters, separate_jockey)

    def presence_impacts(self, month: int) -> Tuple[np.ndarray, np.ndarray]:
        ev = self.presence.upto(month)
        cnt = np.bincount(ev.horse, minlength=self.n_horses).astype(float)
        total = np.bincount(ev.horse, weights=ev.eps, minlength=self.n_horses)
        impact = total / (cnt + self.cfg.presence_lambda)
        return np.where(cnt >= self.cfg.presence_min_n, impact, 0.0), cnt

    def snapshot(self, month: int) -> Dict[str, np.ndarray]:
        """月 month 時点の馬別・騎手別 Pace Impact。末尾要素(index -1)は未知の馬・騎手(=0)。"""
        clip = self.cfg.impact_clip_sec
        out: Dict[str, np.ndarray] = {}
        for role in ROLES:
            a, b, _, _ = self.role_impacts(role, month)
            out[f"h_{role}"] = np.append(np.clip(a, -clip, clip), 0.0)
            out[f"j_{role}"] = np.append(np.clip(b, -clip, clip), 0.0)
        presence, _ = self.presence_impacts(month)
        out["h_presence"] = np.append(np.clip(presence, -clip, clip), 0.0)
        end = int(np.searchsorted(self.run_month, month, side="left"))
        out["h_n_runs"] = np.append(np.bincount(self.run_horse[:end], minlength=self.n_horses).astype(float), 0.0)
        out["h_n_lead"] = np.append(
            np.bincount(self.run_horse[:end], weights=self.run_lead[:end].astype(float), minlength=self.n_horses), 0.0)
        return out


def formation_from_actual_q(q: np.ndarray, threshold: float) -> Formation:
    """過去レースの実際の序盤相対位置 q[N] から Formation(S=1) を作る(馬番昇順の列)。"""
    q2 = np.asarray(q, dtype=float)[None, :]
    group, slot, early_order, order_q = arrange_formation(q2, threshold)
    n = q2.shape[1]
    return Formation(q2, q2, np.zeros((1, n), dtype=bool), group, slot, early_order, order_q,
                     np.zeros(n, dtype=bool), 0)


def actual_formation_table(ds, cfg: RaceverseConfig, with_impacts: bool = False):
    """実隊列の特徴行列。with_impacts=False は構造特徴だけ(個体情報なし)、True は月次スナップショットのPace Impactも入れる。
    戻り値: (race_pos配列, 特徴行列, 実ペース偏差, 日付, race_id, group)。"""
    races = ds.races
    start = pd.Timestamp(cfg.baseline_first_month)
    eligible = races[(~races["is_upcoming"]) & (races["date"] >= start) & races["pace_delta"].notna()
                     & races["early_ref"].notna()]
    rows, positions, ys, dates, ids, groups = [], [], [], [], [], []
    for pos in eligible.index:
        ctx = ds.make_context(int(pos), with_track_context=False, require_ability=False)
        if ctx is None:
            continue
        sl = ds.run_slices[ctx.race_id]
        sub = ds.runs.iloc[sl]
        sub = sub.iloc[np.argsort(sub["umaban"].to_numpy(), kind="stable")]
        q = sub["q_early"].to_numpy(dtype=float)
        q = np.where(np.isfinite(q), q, 0.5)
        form = formation_from_actual_q(q, cfg.formation.group_threshold)
        snap = ds.snapshot(ctx.month_idx) if with_impacts else {}
        rows.append(pace_features(ctx, form, snap, ds.first_turn_default)[0].astype(np.float32))
        positions.append(int(pos))
        ys.append(float(races.at[pos, "pace_delta"]))
        dates.append(races.at[pos, "date"])
        ids.append(ctx.race_id)
        groups.append(group_key(ctx.surface, ctx.distance_m))
    return (np.array(positions), np.stack(rows), np.array(ys), pd.Series(pd.to_datetime(dates)),
            np.array(ids), np.array(groups))


def _eps_cache_path(ds, cfg: RaceverseConfig):
    confirmed = ds.races[~ds.races["is_upcoming"]]
    pi = cfg.pace_impact
    tag = (f"v{CACHE_VERSION}_{len(confirmed)}_{confirmed['date'].max():%Y%m%d}_{pi.base_first_month}_"
           f"{pi.base_alpha}_{pi.base_min_races}_{cfg.baseline_first_month}_{cfg.formation.group_threshold}")
    return CACHE_DIR / f"pace_eps_{tag}.parquet"


def actual_formation_residuals(ds, cfg: RaceverseConfig, use_cache: bool = True) -> pd.DataFrame:
    """実隊列ベース回帰の時系列OOF残差。各レースは自分の月より前のレースだけで学習したモデルで予測する。"""
    path = _eps_cache_path(ds, cfg)
    if use_cache and path.exists():
        return pd.read_parquet(path)
    pi = cfg.pace_impact
    positions, x, y, dates, ids, groups = actual_formation_table(ds, cfg)
    pred = rolling_oof_predictions(x[:, STRUCT_COLUMNS], y, np.ones(len(y)), dates, pi.base_alpha,
                                   pd.Timestamp(pi.base_first_month), min_rows=pi.base_min_races)
    table = pd.DataFrame({"race_id": ids, "date": dates.to_numpy(), "group": groups, "y": y, "yhat": pred,
                          "eps": y - pred})
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        table.to_parquet(path)
    return table


def build_events(ds, race_eps: pd.DataFrame, cfg: PaceImpactConfig) -> Tuple[Dict[str, RoleEvents], RoleEvents]:
    """実際の序盤順位で役割を決め、レース単位の eps を馬・騎手に紐づける。"""
    runs = ds.runs
    eps_by_race = pd.Series(race_eps["eps"].to_numpy(), index=race_eps["race_id"].to_numpy())
    eps = runs["race_id"].map(eps_by_race).to_numpy(dtype=float)
    rank = runs["early_rank"].to_numpy()
    n_field = runs["field_size"].to_numpy(dtype=float)
    kf = front_count_array(n_field)
    ok = np.isfinite(eps) & (rank >= 1)
    month = month_index(runs["date"], ds.base_month)
    masks = {
        "lead": ok & (rank == 1),
        "chase": ok & (rank >= 2) & (rank <= 3),
        "front": ok & (rank <= kf),
    }
    horse = runs["horse_idx"].to_numpy()
    jockey = runs["jockey_idx"].to_numpy()

    def pack(mask: np.ndarray) -> RoleEvents:
        order = np.argsort(month[mask], kind="stable")
        return RoleEvents(month[mask][order], horse[mask][order], jockey[mask][order], eps[mask][order])

    return {r: pack(m) for r, m in masks.items()}, pack(ok & (rank > kf))


def build_pace_impacts(ds, cfg: RaceverseConfig, use_cache: bool = True) -> PaceImpactProfiles:
    race_eps = actual_formation_residuals(ds, cfg, use_cache)
    roles, presence = build_events(ds, race_eps, cfg.pace_impact)
    runs = ds.runs
    valid = (runs["early_rank"].to_numpy() >= 1)
    month = month_index(runs["date"], ds.base_month)
    order = np.argsort(month[valid], kind="stable")
    run_month = month[valid][order]
    run_horse = runs["horse_idx"].to_numpy()[valid][order]
    run_lead = (runs["early_rank"].to_numpy()[valid] == 1)[order]
    LOGGER.info("pace impact events: %s presence=%d", {r: len(e.eps) for r, e in roles.items()}, len(presence.eps))
    return PaceImpactProfiles(cfg.pace_impact, int(runs["horse_idx"].max()) + 1, len(ds.jockey_codes), roles,
                              presence, run_month, run_horse, run_lead, race_eps)


def out_of_sample_gain(profiles: PaceImpactProfiles, role: str, start: pd.Timestamp, end: pd.Timestamp,
                       base_month: pd.Timestamp, lam_horse: float, lam_jockey: float) -> Dict[str, float]:
    """[start, end) の各月について「月より前のイベントだけ」で作った impact が、その月の eps をどれだけ説明するか。
    gain = 1 - MSE(eps - impact) / MSE(eps)。正なら未知のレースでも向きが当たっている。"""
    ev = profiles.roles[role]
    m0 = int((start.year - base_month.year) * 12 + start.month - base_month.month)
    m1 = int((end.year - base_month.year) * 12 + end.month - base_month.month)
    sse0 = sse1 = 0.0
    n = 0
    for m in range(m0, m1):
        a, b, _, _ = profiles.role_impacts(role, m, lam_horse, lam_jockey)
        sel = ev.month == m
        if not sel.any():
            continue
        jock = np.where(ev.jockey[sel] < 0, 0, ev.jockey[sel])
        known_j = np.where(ev.jockey[sel] < 0, 0.0, b[jock])
        pred = a[ev.horse[sel]] + known_j
        e = ev.eps[sel]
        sse0 += float((e ** 2).sum())
        sse1 += float(((e - pred) ** 2).sum())
        n += int(sel.sum())
    return {"n": n, "mse_base": sse0 / max(n, 1), "mse_with_impact": sse1 / max(n, 1),
            "gain": 1.0 - sse1 / sse0 if sse0 > 0 else float("nan")}

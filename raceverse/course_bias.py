"""コース別の脚質・枠順バイアス(as-of統計)と走破性能モデル用の特徴量。

統計は「予測対象レースより前の日付」の確定結果だけから作る(同日のレースは使わない)。
各出走の期待値は勝利=1/頭数・複勝(3着以内)=3/頭数で、比率 r = 実績 / 期待 を階層的にベイズ縮約する:
    r_L = (実績_L + K_L * r_親) / (期待_L + K_L)
上位集計(馬場種別) -> コース(競馬場・距離・内外回り) -> 芝の使用コースA-D -> 開催時期x馬場状態 -> 同開催のこれまで、の順に
サンプルが少ない条件ほど親の値へ縮む。特徴量は対数比率で、勝敗確率には直接掛けず走破性能モデルの説明変数に使う。

過去走の脚質は「その過去レースの序盤位置(結果)」から付けるが、予測対象レース自身の結果は一切使わない。
予測側の脚質はシミュレーションで抽選した序盤位置から決める(逃げ=先頭1頭)。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from raceverse.config import CourseBiasConfig
from raceverse.schemas import RaceBias

LOGGER = logging.getLogger(__name__)
N_STYLE, N_DRAW, N_DG, N_PACE = 4, 8, 3, 3
STYLE_NAMES = ["lead", "front", "stalk", "closer"]
VALS = ["n", "e_win", "w", "e_place", "p"]

S0 = ["surface"]
S1 = ["track", "surface", "distance_m", "track_cd"]
S2 = S1 + ["course_kubun"]
S3 = S2 + ["stage", "ggrp"]
S4 = ["meet_id", "surface", "course_kubun"]
D0 = ["surface", "fb"]
D1 = S1 + ["fb"]
D2 = D1 + ["course_kubun"]
D3 = D2 + ["stage", "ggrp"]
D4 = ["meet_id", "surface", "course_kubun", "fb"]


def draw_group(wakuban: np.ndarray) -> np.ndarray:
    w = np.clip(np.asarray(wakuban), 1, 8)
    return np.where(w <= 3, 0, np.where(w <= 6, 1, 2))


def meet_stage(day: np.ndarray) -> np.ndarray:
    return np.where(day <= 4, 0, np.where(day <= 8, 1, 2))


def going_group(going: np.ndarray) -> np.ndarray:
    """0=未発表, 1=良, 2=稍重以上。"""
    return np.where(going <= 0, 0, np.where(going == 1, 1, 2))


def style_from_q(q: np.ndarray, is_lead: np.ndarray, front_q: float, stalk_q: float) -> np.ndarray:
    sid = np.where(q <= front_q, 1, np.where(q <= stalk_q, 2, 3))
    return np.where(is_lead, 0, sid)


def style_ids(q_adj: np.ndarray, front_q: float, stalk_q: float) -> np.ndarray:
    """シミュレーションの序盤位置[S,N]から脚質ID(0逃げ/1先行/2差し/3追込)。先頭の1頭だけが逃げ。"""
    lead = np.zeros(q_adj.shape, dtype=bool)
    np.put_along_axis(lead, q_adj.argmin(axis=1)[:, None], True, axis=1)
    return style_from_q(q_adj, lead, front_q, stalk_q)


def pace_bucket(pace: np.ndarray, edges: Sequence[float]) -> np.ndarray:
    return np.digitize(pace, np.asarray(edges, dtype=float))  # 0=速い, 1=ミドル, 2=遅い


def _log(x: np.ndarray) -> np.ndarray:
    return np.log(np.maximum(x, 1e-6))


class CourseBiasEngine:
    def __init__(self, races: pd.DataFrame, runs: pd.DataFrame, cfg: CourseBiasConfig):
        self.cfg = cfg
        self.races = races
        self.H = self._history(races, runs)
        self._cache: Dict[object, RaceBias] = {}

    def _derived(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame["stage"] = meet_stage(frame["meet_day"].to_numpy())
        frame["ggrp"] = going_group(frame["going"].to_numpy())
        frame["fb"] = (frame["field_size"].to_numpy() >= self.cfg.large_field).astype(int)
        return frame

    def _history(self, races: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
        cfg = self.cfg
        cols = ["race_id", "date", "surface", "track", "distance_m", "track_cd", "course_kubun", "meet_id", "meet_day",
                "going", "pace_delta", "field_size"]
        confirmed = races.loc[~races["is_upcoming"], cols]
        r = runs.loc[runs["finish"] > 0, ["race_id", "wakuban", "finish", "q_early", "early_rank"]]
        h = r.merge(confirmed, on="race_id", how="inner")
        h = h[h["field_size"] >= cfg.min_field].copy()
        h = self._derived(h)
        fs = h["field_size"].to_numpy(dtype=float)
        h["n"] = 1.0
        h["e_win"] = 1.0 / fs
        h["e_place"] = np.minimum(3.0, fs) / fs
        h["w"] = (h["finish"] == 1).astype(float)
        h["p"] = (h["finish"] <= 3).astype(float)
        q = h["q_early"].to_numpy(dtype=float)
        style = style_from_q(np.nan_to_num(q, nan=1.0), h["early_rank"].to_numpy() == 1, cfg.front_q, cfg.stalk_q)
        h["style"] = np.where(np.isfinite(q), style, -1)
        wk = h["wakuban"].to_numpy()
        h["wakuban_c"] = np.where((wk >= 1) & (wk <= 8), wk, -1)
        dg = np.where(h["wakuban_c"] > 0, draw_group(wk), -1)
        h["dg"] = dg
        h["sd"] = np.where((h["style"] >= 0) & (dg >= 0), h["style"] * N_DG + dg, -1)
        bucket = np.where(np.isfinite(h["pace_delta"]), pace_bucket(h["pace_delta"].fillna(0.0).to_numpy(), cfg.pace_edges_sec), -1)
        h["ps"] = np.where((bucket >= 0) & (h["style"] >= 0), bucket * N_STYLE + h["style"], -1)
        h["pd"] = np.where((bucket >= 0) & (dg >= 0), bucket * N_DG + dg, -1)
        return h

    @staticmethod
    def _codes(a: pd.DataFrame, b: pd.DataFrame, cols: List[str]):
        code_a = np.zeros(len(a), dtype=np.int64)
        code_b = np.zeros(len(b), dtype=np.int64)
        for c in cols:
            both = pd.concat([a[c], b[c]], ignore_index=True)
            codes, uniques = pd.factorize(both)
            card = max(len(uniques), 1)
            code_a = code_a * card + codes[:len(a)]
            code_b = code_b * card + codes[len(a):]
        return code_a, code_b

    def _asof(self, query: pd.DataFrame, cols: List[str], cat: str) -> pd.DataFrame:
        """query の各行について、同じ(条件, カテゴリ)の「日付が厳密に前」の累積実績・期待を返す。"""
        key = cols + [cat]
        h = self.H[self.H[cat] >= 0]
        agg = h.groupby(key + ["date"], sort=True)[VALS].sum().reset_index()
        agg[VALS] = agg.groupby(key)[VALS].cumsum()
        code_g, code_q = self._codes(agg, query, key)
        right = agg[["date"] + VALS].assign(k=code_g).sort_values("date", kind="stable")
        left = pd.DataFrame({"date": query["date"].to_numpy(), "k": code_q, "_row": np.arange(len(query))})
        merged = pd.merge_asof(left.sort_values("date", kind="stable"), right, on="date", by="k", allow_exact_matches=False)
        return merged.sort_values("_row")[VALS].fillna(0.0).reset_index(drop=True)

    def _chain(self, query: pd.DataFrame, levels: List[List[str]], cat: str, ks: List[float],
               prior_win: Optional[np.ndarray] = None, prior_place: Optional[np.ndarray] = None):
        rw = np.ones(len(query)) if prior_win is None else prior_win
        rp = np.ones(len(query)) if prior_place is None else prior_place
        mult = self.cfg.place_k_multiplier
        out = []
        for cols, k in zip(levels, ks):
            s = self._asof(query, cols, cat)
            rw = (s["w"].to_numpy() + k * rw) / (s["e_win"].to_numpy() + k)
            rp = (s["p"].to_numpy() + k * mult * rp) / (s["e_place"].to_numpy() + k * mult)
            out.append({"rw": rw, "rp": rp, "n": s["n"].to_numpy()})
        return out

    def _cross(self, races: pd.DataFrame, cat: str, count: int) -> pd.DataFrame:
        q = races.loc[races.index.repeat(count)].copy()
        q[cat] = np.tile(np.arange(count), len(races))
        return q.reset_index(drop=True)

    def compute(self, positions: Sequence[int], going_override: Optional[int] = None) -> None:
        todo = [int(p) for p in positions
                if ((int(p), int(going_override)) if going_override is not None else int(p)) not in self._cache]
        if not todo:
            return
        cols = ["race_id", "date", "surface", "track", "distance_m", "track_cd", "course_kubun", "meet_id", "meet_day",
                "going", "field_size"]
        races = self._derived(self.races.loc[todo, cols].copy())
        if going_override is not None:
            races["going"] = int(going_override)
            races = self._derived(races)
        races["field_size"] = races["field_size"].clip(lower=self.cfg.min_field)
        R, cfg = len(races), self.cfg

        def chain(levels, cat, count, ks, prior=None):
            q = self._cross(races, cat, count)
            res = self._chain(q, levels, cat, ks, None if prior is None else prior[0], None if prior is None else prior[1])
            return [{k: v.reshape(R, count) for k, v in r.items()} for r in res]

        style = chain([S0, S1, S2, S3, S4], "style", N_STYLE, cfg.k_win)
        draw = chain([D0, D1, D2, D3, D4], "wakuban_c", N_DRAW + 1, cfg.k_win)  # 先頭列(0)は未使用: 枠番1-8は列1-8
        draw = [{k: v[:, 1:] for k, v in r.items()} for r in draw]
        dgs = chain([D0, D1, D2], "dg", N_DG, cfg.k_dg)

        s2w, s2p = style[2]["rw"], style[2]["rp"]
        s0w, s0p = style[0]["rw"], style[0]["rp"]
        g2w, g2p = dgs[2]["rw"], dgs[2]["rp"]
        g0w, g0p = dgs[0]["rw"], dgs[0]["rp"]

        # 脚質 x 枠グループ(同コース): 周辺効果の積を事前に、積からの差分を交互作用とする
        pred_w = (s2w[:, :, None] * g2w[:, None, :]).reshape(R, N_STYLE * N_DG)
        pred_p = (s2p[:, :, None] * g2p[:, None, :]).reshape(R, N_STYLE * N_DG)
        joint = chain([D2], "sd", N_STYLE * N_DG, [cfg.k_joint], (pred_w.reshape(-1), pred_p.reshape(-1)))[0]
        inter = 0.5 * ((_log(joint["rw"]) - _log(pred_w)) + (_log(joint["rp"]) - _log(pred_p))).reshape(R, N_STYLE, N_DG)

        # ペース x 脚質: 全国のペース変調を事前に載せ、同コース脚質バイアスからの差分を特徴量にする
        ps0 = chain([S0], "ps", N_PACE * N_STYLE, [cfg.k_pace_root],
                    (np.repeat(s0w, N_PACE, axis=0).reshape(R, N_PACE, N_STYLE).reshape(-1),
                     np.repeat(s0p, N_PACE, axis=0).reshape(R, N_PACE, N_STYLE).reshape(-1)))[0]
        mod_w = (ps0["rw"].reshape(R, N_PACE, N_STYLE) / s0w[:, None, :])
        mod_p = (ps0["rp"].reshape(R, N_PACE, N_STYLE) / s0p[:, None, :])
        prior_w = (s2w[:, None, :] * mod_w).reshape(-1)
        prior_p = (s2p[:, None, :] * mod_p).reshape(-1)
        ps1 = chain([S2], "ps", N_PACE * N_STYLE, [cfg.k_pace_course], (prior_w, prior_p))[0]
        pstyle_w = (_log(ps1["rw"].reshape(R, N_PACE, N_STYLE)) - _log(s2w)[:, None, :])
        pstyle_p = (_log(ps1["rp"].reshape(R, N_PACE, N_STYLE)) - _log(s2p)[:, None, :])

        # ペース x 枠グループ
        pd0 = chain([D0], "pd", N_PACE * N_DG, [cfg.k_pace_root],
                    (np.tile(g0w[:, None, :], (1, N_PACE, 1)).reshape(-1), np.tile(g0p[:, None, :], (1, N_PACE, 1)).reshape(-1)))[0]
        dmod_w = pd0["rw"].reshape(R, N_PACE, N_DG) / g0w[:, None, :]
        dmod_p = pd0["rp"].reshape(R, N_PACE, N_DG) / g0p[:, None, :]
        pd1 = chain([D2], "pd", N_PACE * N_DG, [cfg.k_pace_course],
                    ((g2w[:, None, :] * dmod_w).reshape(-1), (g2p[:, None, :] * dmod_p).reshape(-1)))[0]
        pdraw = 0.5 * ((_log(pd1["rw"].reshape(R, N_PACE, N_DG)) - _log(g2w)[:, None, :])
                       + (_log(pd1["rp"].reshape(R, N_PACE, N_DG)) - _log(g2p)[:, None, :]))

        edges = np.asarray(cfg.pace_edges_sec, dtype=float)
        for i, pos in enumerate(races.index):
            key = (int(pos), int(going_override)) if going_override is not None else int(pos)
            self._cache[key] = RaceBias(
                style_win=_log(style[4]["rw"][i]), style_place=_log(style[4]["rp"][i]),
                style_n=style[2]["n"][i], style_n_meet=style[4]["n"][i],
                draw_win=_log(draw[4]["rw"][i]), draw_place=_log(draw[4]["rp"][i]),
                draw_n=draw[2]["n"][i], draw_n_meet=draw[4]["n"][i],
                inter=inter[i], pstyle_win=pstyle_w[i], pstyle_place=pstyle_p[i], pdraw=pdraw[i],
                front_q=cfg.front_q, stalk_q=cfg.stalk_q, pace_edges=edges,
            )

    def get(self, pos: int, going_override: Optional[int] = None) -> RaceBias:
        key = (int(pos), int(going_override)) if going_override is not None else int(pos)
        if key not in self._cache:
            self.compute([pos], going_override)
        return self._cache[key]


def bias_feature_block(bias: RaceBias, wakuban: np.ndarray, q_adj: np.ndarray, pace: np.ndarray) -> Dict[str, np.ndarray]:
    """[S,N]のバイアス特徴量(中心化前)。脚質・ペース区分はシミュレーションの値から決める。"""
    sid = style_ids(q_adj, bias.front_q, bias.stalk_q)
    wk = np.clip(np.asarray(wakuban, dtype=int), 1, 8)
    dg = draw_group(wk)
    pb = pace_bucket(pace, bias.pace_edges)[:, None]
    s, n = q_adj.shape
    draw_win = np.broadcast_to(bias.draw_win[wk - 1][None, :], (s, n))
    draw_place = np.broadcast_to(bias.draw_place[wk - 1][None, :], (s, n))
    return {
        "style_win_bias_c": bias.style_win[sid],
        "style_place_bias_c": bias.style_place[sid],
        "draw_win_bias_c": draw_win,
        "draw_place_bias_c": draw_place,
        "style_draw_interaction_c": bias.inter[sid, dg[None, :]],
        "pace_style_win_bias_c": bias.pstyle_win[pb, sid],
        "pace_style_place_bias_c": bias.pstyle_place[pb, sid],
        "pace_draw_interaction_c": bias.pdraw[pb, dg[None, :]],
    }

"""学習用ストア: 過去レースごとの擬似隊列(仕様6.5)・OOFペース予測・時計/走破性能の学習行。

- 各学習レースrについて、rより前の履歴・騎手統計だけで疑似隊列を D 回(既定16)生成し、実測ペース偏差を正解にする。
  各行の重みは 1/D(レース単位の重み合計=1)。同一レース由来の行は同じ日付なので学習と評価にまたがらない。
- 時計・走破性能の学習にはこのストアのOOF予測ペース(当時の情報だけ)を使い、実ラップは使わない。
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from raceverse.config import RaceverseConfig
from raceverse.dataset import Dataset
from raceverse.formation_sampler import sample_formation
from raceverse.pace_features import FEATURE_INDEX, pace_features
from raceverse.pace_regression import rolling_oof_predictions
from raceverse.pace_residuals import group_key
from raceverse.performance import perf_features
from raceverse.schemas import RaceContext
from raceverse.winning_time_model import FORMATION_COLUMNS, time_features

LOGGER = logging.getLogger(__name__)
MAX_RUNNERS = 18


@dataclass
class Store:
    X: np.ndarray
    y: np.ndarray
    w: np.ndarray
    race_pos: np.ndarray
    date: np.ndarray
    draws: int
    race_table: pd.DataFrame
    ability_ctx: Dict[int, RaceContext]
    outcomes: Dict[int, pd.DataFrame]
    perf_draws: Dict[int, dict]
    oof: Optional[np.ndarray] = None


def build_store(ds: Dataset, cfg: RaceverseConfig, max_races: Optional[int] = None) -> Store:
    races = ds.races
    start = pd.Timestamp(cfg.pace.train_start)
    eligible = races[(~races["is_upcoming"]) & (races["date"] >= start) & races["pace_delta"].notna()
                     & races["early_ref"].notna()]
    ability_start = pd.Timestamp(cfg.winning_time.train_start)
    n_draws = cfg.pace.training_formation_draws
    n_perf = cfg.performance.training_draws
    xs, ys, rp, rd, rows_meta = [], [], [], [], []
    ability_ctx: Dict[int, RaceContext] = {}
    outcomes: Dict[int, pd.DataFrame] = {}
    perf_draws: Dict[int, dict] = {}
    row_cursor = 0
    positions = eligible.index.tolist()
    if max_races:
        positions = positions[-max_races:]
    for count, pos in enumerate(positions):
        race = races.loc[pos]
        ctx = None
        if race["date"] >= ability_start:
            ctx = ds.make_context(pos, with_track_context=True, require_ability=True)
        if ctx is None:
            ctx = ds.make_context(pos, with_track_context=False, require_ability=False)
        if ctx is None:
            continue
        snap = ds.snapshot(ctx.month_idx)
        rng = np.random.default_rng([cfg.random_seed, int(pos)])
        form = sample_formation(ctx, rng, n_draws, cfg.formation, snap["frontness"])
        x = pace_features(ctx, form, snap, ds.first_turn_default)
        xs.append(x.astype(np.float32))
        ys.append(np.full(n_draws, race["pace_delta"]))
        rp.append(np.full(n_draws, pos))
        rd.append(np.full(n_draws, race["date"].to_datetime64()))
        is_ability = ctx.track_context is not None
        rows_meta.append({"race_pos": pos, "race_id": race["race_id"], "row_start": row_cursor, "date": race["date"],
                          "group": group_key(ctx.surface, ctx.distance_m), "y": float(race["pace_delta"]),
                          "has_ability": is_ability})
        if is_ability:
            ability_ctx[pos] = ctx
            outcomes[pos] = ds.outcomes(ctx)
            perf_draws[pos] = {"q_adj": form.q_adj[:n_perf].copy(), "slot": form.lateral_slot[:n_perf].copy()}
        row_cursor += n_draws
        if count and count % 5000 == 0:
            LOGGER.info("store: %d / %d races", count, len(positions))
    return Store(
        X=np.concatenate(xs), y=np.concatenate(ys), w=np.full(row_cursor, 1.0 / n_draws),
        race_pos=np.concatenate(rp), date=np.concatenate(rd), draws=n_draws,
        race_table=pd.DataFrame(rows_meta), ability_ctx=ability_ctx, outcomes=outcomes, perf_draws=perf_draws,
    )


def compute_pace_oof(store: Store, cfg: RaceverseConfig) -> None:
    """月次ローリング・オリジンでOOFペース予測を作り、レース単位の統計を race_table に追加する。"""
    first_month = pd.Timestamp(cfg.pace.train_start) + pd.DateOffset(years=2)
    store.oof = rolling_oof_predictions(
        store.X, store.y, store.w, pd.Series(pd.to_datetime(store.date)), cfg.pace.ridge_alpha,
        first_month, min_rows=cfg.pace.min_train_races * store.draws // 2,
    )
    table = store.race_table
    d = store.draws
    oof = store.oof.reshape(-1, d)
    table["yhat_mean"] = oof.mean(axis=1)
    table["yhat_var"] = oof.var(axis=1)
    table["resid"] = table["y"] - table["yhat_mean"]
    mean_form = store.X.reshape(-1, d, store.X.shape[1]).mean(axis=1)
    for name in FORMATION_COLUMNS:
        table[f"form_{name}"] = mean_form[:, FEATURE_INDEX[name]]


def time_training_table(store: Store, ds: Dataset) -> Optional[Dict[str, np.ndarray]]:
    """決着時計モデルの学習行(レース単位)。ペース・隊列はOOF予測(疑似隊列の平均)。"""
    table = store.race_table
    rows = table[table["has_ability"] & table["yhat_mean"].notna()]
    if rows.empty:
        return None
    feats, ys, dates, groups, positions = [], [], [], [], []
    for _, r in rows.iterrows():
        pos = int(r["race_pos"])
        ctx = store.ability_ctx[pos]
        win_time = ds.races.at[pos, "win_time_sec"]
        if not np.isfinite(ctx.win_time_base) or not np.isfinite(win_time):
            continue
        form = np.array([[r[f"form_{n}"] for n in FORMATION_COLUMNS]])
        f = time_features(ctx, ctx.track_context, np.array([r["yhat_mean"]]), form)[0]
        feats.append(f)
        ys.append(win_time - ctx.win_time_base)
        dates.append(r["date"])
        groups.append(r["group"])
        positions.append(pos)
    return {"X": np.array(feats), "y": np.array(ys), "date": pd.to_datetime(pd.Series(dates)).to_numpy(),
            "group": np.array(groups), "race_pos": np.array(positions)}


def _pad(arr: np.ndarray, fill=0.0) -> np.ndarray:
    n = arr.shape[0]
    if arr.ndim == 1:
        out = np.full(MAX_RUNNERS, fill, dtype=arr.dtype)
        out[:n] = arr
        return out
    out = np.zeros((MAX_RUNNERS,) + arr.shape[1:])
    out[:n] = arr
    return out


def perf_training_table(store: Store, cfg: RaceverseConfig) -> Optional[Dict[str, np.ndarray]]:
    """走破性能モデルの学習行: (レース, 疑似隊列draw, 馬)。目的変数は時計のレース内偏差(秒)。"""
    table = store.race_table
    rows = table[table["has_ability"] & table["yhat_mean"].notna()]
    d = store.draws
    n_perf = cfg.performance.training_draws
    oof = store.oof.reshape(-1, d)
    index_by_pos = {int(p): i for i, p in enumerate(table["race_pos"])}
    feats, targets, oks, race_ids, draw_ids, dates = [], [], [], [], [], []
    for _, r in rows.iterrows():
        pos = int(r["race_pos"])
        ctx = store.ability_ctx[pos]
        outcome = store.outcomes[pos]
        t = outcome["time_sec"].to_numpy(dtype=float)
        ok = np.isfinite(t) & (outcome["finish"].to_numpy() > 0)
        if ok.sum() < 4 or ctx.n > MAX_RUNNERS:
            continue
        z = np.where(ok, t - np.nanmean(np.where(ok, t, np.nan)), 0.0)
        pd_ = store.perf_draws[pos]
        pace = oof[index_by_pos[pos], :n_perf]
        f = perf_features(ctx, pd_["q_adj"], pd_["slot"], pace, cfg.performance)
        for k in range(f.shape[0]):
            feats.append(_pad(f[k]))
            targets.append(_pad(z))
            oks.append(_pad(ok, fill=False))
            race_ids.append(pos)
            draw_ids.append(k)
            dates.append(r["date"])
    if not feats:
        return None
    return {"F": np.stack(feats), "z": np.stack(targets), "ok": np.stack(oks),
            "race_pos": np.array(race_ids), "draw": np.array(draw_ids),
            "date": pd.to_datetime(pd.Series(dates)).to_numpy()}


def save_store(store: Store, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(store, handle, protocol=4)


def load_store(path: Path) -> Store:
    with path.open("rb") as handle:
        return pickle.load(handle)

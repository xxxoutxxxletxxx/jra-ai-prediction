"""月次再学習: ストアの過去行(date < as_of)だけからモデル一式(ModelBundle)を作る。

ペース回帰・時計モデル・走破性能モデルとも、残差分布・共通ショックの強さ・表示閾値は
「as_of より前の時系列OOF予測」からのみ推定する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from raceverse.config import RaceverseConfig
from raceverse.dataset import Dataset
from raceverse.pace_display import fit_display_thresholds
from raceverse.pace_residuals import PaceBounds, PaceResidualSampler
from raceverse.pace_regression import fit_pace_regressor
from raceverse.periods import period_start
from raceverse.performance import PERF_LEVELS, PERF_FEATURES, PerfModel, fit_ridge, level_indices
from raceverse.store import Store
from raceverse.winning_time_model import TIME_LEVELS, TimeModel

LOGGER = logging.getLogger(__name__)


@dataclass
class ModelBundle:
    as_of: pd.Timestamp
    pace_model: object
    pace_bounds: PaceBounds
    display_thresholds: Dict[str, np.ndarray]
    time_models: Dict[str, TimeModel]
    time_sampler: Optional[PaceResidualSampler]
    perf_models: Dict[str, PerfModel]
    train_counts: Dict[str, int]
    warnings: List[str] = field(default_factory=list)


@dataclass
class OOFCache:
    """全期間のローリング・オリジンOOF(各行は自分の月より前のデータだけで学習したモデルの予測)。"""
    time_table: Optional[Dict[str, np.ndarray]]
    perf_table: Optional[Dict[str, np.ndarray]]
    time_oof: Dict[str, np.ndarray]
    perf_mu: Dict[str, np.ndarray]    # level -> [rows, 18]
    perf_z: Optional[np.ndarray] = None  # winsor済み目的変数(OOF時のbounds)


def _months(dates: np.ndarray, unit: str = "month") -> np.ndarray:
    """各行が属する期間(月 / 週)の開始日。名前は月次時代の互換のため _months のまま。"""
    return period_start(pd.to_datetime(pd.Series(dates)), unit).to_numpy()


def _winsor_bounds(z: np.ndarray, q: List[float]) -> np.ndarray:
    return np.quantile(z, q)


def _perf_xy(perf: Dict[str, np.ndarray], mask: np.ndarray, level: str, bounds: Optional[np.ndarray] = None):
    cols = level_indices(level)
    ok = perf["ok"][mask]
    x = perf["F"][mask][:, :, cols][ok]
    z = perf["z"][mask][ok]
    if bounds is not None:
        z = np.clip(z, bounds[0], bounds[1])
    return x, z


def compute_oof_cache(store: Store, ds: Dataset, cfg: RaceverseConfig, time_table, perf_table) -> OOFCache:
    """時計・走破性能モデルのローリング・オリジンOOF。"""
    time_oof = {lv: np.full(len(time_table["y"]), np.nan) for lv in TIME_LEVELS} if time_table else {}
    if time_table:
        months = _months(time_table["date"], cfg.refit_unit)
        first = np.datetime64(pd.Timestamp(cfg.winning_time.train_start) + pd.DateOffset(months=12))
        for month in np.unique(months[months >= first]):
            train = time_table["date"] < month
            if train.sum() < cfg.winning_time.min_train_races:
                continue
            rows = months == month
            for level in TIME_LEVELS:
                model = TimeModel(level, cfg.winning_time.ridge_alpha).fit(time_table["X"][train], time_table["y"][train])
                time_oof[level][rows] = model.predict(time_table["X"][rows])
    perf_mu: Dict[str, np.ndarray] = {}
    if perf_table:
        n_rows = len(perf_table["race_pos"])
        months = _months(perf_table["date"], cfg.refit_unit)
        first = np.datetime64(pd.Timestamp(cfg.winning_time.train_start) + pd.DateOffset(months=12))
        perf_mu = {lv: np.full((n_rows, perf_table["F"].shape[1]), np.nan) for lv in PERF_LEVELS}
        for month in np.unique(months[months >= first]):
            train = perf_table["date"] < month
            if train.sum() < cfg.performance.min_train_races * cfg.performance.training_draws:
                continue
            rows = months == month
            ok_train = perf_table["ok"][train]
            bounds = _winsor_bounds(perf_table["z"][train][ok_train], cfg.performance.margin_winsor)
            for level in PERF_LEVELS:
                x, z = _perf_xy(perf_table, train, level, bounds)
                coef, b = fit_ridge(x, z, cfg.performance.ridge_alpha)
                cols = level_indices(level)
                perf_mu[level][rows] = perf_table["F"][rows][:, :, cols] @ coef + b
    return OOFCache(time_table, perf_table, time_oof, perf_mu)


def _fit_perf_model(level: str, perf: Dict[str, np.ndarray], oof: OOFCache, as_of: np.datetime64,
                    cfg: RaceverseConfig, warnings: List[str]) -> Optional[PerfModel]:
    train = perf["date"] < as_of
    if train.sum() < cfg.performance.min_train_races * cfg.performance.training_draws:
        warnings.append(f"perf[{level}]: insufficient training rows")
        return None
    ok_train = perf["ok"][train]
    bounds = _winsor_bounds(perf["z"][train][ok_train], cfg.performance.margin_winsor)
    x, z = _perf_xy(perf, train, level, bounds)
    coef, b = fit_ridge(x, z, cfg.performance.ridge_alpha)

    mu_all = oof.perf_mu[level]
    use = train & np.isfinite(mu_all[:, 0])
    if use.sum() < cfg.performance.min_oof_races * cfg.performance.training_draws:
        warnings.append(f"perf[{level}]: OOF rows scarce ({int(use.sum())}); using in-sample residuals")
        cols = level_indices(level)
        mu = perf["F"][train][:, :, cols] @ coef + b
        use_idx = np.flatnonzero(train)
    else:
        mu = mu_all[use]
        use_idx = np.flatnonzero(use)
    ok = perf["ok"][use_idx]
    z_all = np.clip(perf["z"][use_idx], bounds[0], bounds[1])
    resid = np.where(ok, z_all - mu, np.nan)
    masked_mu = np.where(ok, mu, np.inf)
    rel = np.where(ok, mu - masked_mu.min(axis=1, keepdims=True), np.nan)
    a, r = rel[ok], np.abs(resid[ok])
    design = np.stack([np.ones_like(a), a], axis=1)
    s0, s1 = np.linalg.lstsq(design, r * np.sqrt(np.pi / 2.0), rcond=None)[0]
    s0, s1 = max(float(s0), 0.05), max(float(s1), 0.0)
    sigma = np.maximum(s0 + s1 * a, 0.05)
    pool = resid[ok] / sigma
    pool = pool - pool.mean()

    tau_q = tau_slot = 0.0
    if level != "base":
        tau_q, tau_slot = _shared_slope_sd(perf, use_idx, resid, s0, s1, mu)
    return PerfModel(level, coef, b, s0, s1, pool, tau_q, tau_slot, bounds, int(train.sum()))


def _shared_slope_sd(perf, idx, resid, s0, s1, mu) -> tuple:
    """レースごとの残差のq_c・slot_c勾配のばらつき(標本誤差を除く)= 共通ショックの強さ。"""
    first_draw = perf["draw"][idx] == 0
    qi, si = PERF_FEATURES.index("q_c"), PERF_FEATURES.index("slot_c")
    slopes, ses = [], []
    for k in np.flatnonzero(first_draw):
        ok = np.isfinite(resid[k])
        if ok.sum() < 6:
            continue
        x = perf["F"][idx[k]][ok][:, [qi, si]]
        y = resid[k][ok]
        gram = x.T @ x
        if np.linalg.det(gram) < 1e-9:
            continue
        inv = np.linalg.inv(gram)
        beta = inv @ x.T @ y
        sigma2 = float(((y - x @ beta) ** 2).sum() / max(ok.sum() - 2, 1))
        slopes.append(beta)
        ses.append(sigma2 * np.diag(inv))
    if len(slopes) < 100:
        return 0.0, 0.0
    slopes, ses = np.array(slopes), np.array(ses)
    tau2 = np.maximum(slopes.var(axis=0) - ses.mean(axis=0), 0.0)
    return float(np.sqrt(tau2[0])), float(np.sqrt(tau2[1]))


def fit_bundle(store: Store, ds: Dataset, cfg: RaceverseConfig, oof: OOFCache, as_of: pd.Timestamp) -> ModelBundle:
    warnings: List[str] = []
    cutoff = np.datetime64(as_of)
    train = store.date < cutoff
    pace_model = fit_pace_regressor(store.X[train], store.y[train], store.w[train], cfg.pace.ridge_alpha)

    table = store.race_table
    all_before = table[table["date"] < as_of]
    if len(all_before) < cfg.pace.min_residual_pool:
        warnings.append("pace training races are few; display thresholds and bounds fall back to global")
    pace_bounds = PaceBounds.fit(all_before["group"].to_numpy(), all_before["y"].to_numpy(),
                                 cfg.pace.truncation_quantiles, cfg.pace.min_residual_pool)
    thresholds = fit_display_thresholds(all_before["group"].to_numpy(), all_before["y"].to_numpy(),
                                        cfg.pace.display_quantiles)

    time_models: Dict[str, TimeModel] = {}
    time_sampler = None
    counts = {"pace_rows": int(train.sum()), "pace_races": int(len(all_before))}
    tt = oof.time_table
    if tt is not None and cfg.winning_time.enabled:
        tmask = tt["date"] < cutoff
        if tmask.sum() >= cfg.winning_time.min_train_races:
            for level in TIME_LEVELS:
                time_models[level] = TimeModel(level, cfg.winning_time.ridge_alpha).fit(tt["X"][tmask], tt["y"][tmask])
            res_mask = tmask & np.isfinite(oof.time_oof["full"])
            if res_mask.sum() >= 100:
                resid = tt["y"][res_mask] - oof.time_oof["full"][res_mask]
                # ペースは乱択しないので、時計残差からペース誤差の共有分は引かない
                time_sampler = PaceResidualSampler.fit(
                    tt["group"][res_mask], resid, np.zeros(res_mask.sum()), tt["y"][res_mask],
                    [0.002, 0.998], cfg.pace.min_residual_pool,
                )
            else:
                warnings.append("time OOF residuals scarce; winning_time unavailable")
            counts["time_races"] = int(tmask.sum())
        else:
            warnings.append("time model: insufficient training races; winning_time unavailable")

    perf_models: Dict[str, PerfModel] = {}
    if oof.perf_table is not None:
        for level in PERF_LEVELS:
            model = _fit_perf_model(level, oof.perf_table, oof, cutoff, cfg, warnings)
            if model is not None:
                perf_models[level] = model
        counts["perf_rows"] = int((oof.perf_table["date"] < cutoff).sum())
    return ModelBundle(as_of, pace_model, pace_bounds, thresholds, time_models, time_sampler, perf_models, counts, warnings)

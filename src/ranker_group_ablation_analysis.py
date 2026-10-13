#!/usr/bin/env python3
"""Metrics, group-contribution, interaction and over-confidence analysis for the group ablation.

Every metric is stored as additive per-(combination, month) sums so that any subset of months
(selection period, final period, single months) can be re-aggregated without refitting.
Confirmed popularity / odds / payouts are used only for *reporting* (never as model input).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src import ranker_group_ablation as ab
    from src import ranker_walk_forward_backtest as wf
except ModuleNotFoundError:
    import ranker_group_ablation as ab
    import ranker_walk_forward_backtest as wf

EPS = 1e-6
POP_BANDS = ["1位", "2-3位", "4-6位", "7位以下"]
PROB_BINS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0001]
PROB_BIN_LABELS = ["<2%", "2-5%", "5-10%", "10-20%", "20-30%", "30-50%", "50%+"]
CONDITIONS = ["~1400m", "1401-1800m", "1801m~", "~12頭", "13頭~", "1着賞金~1200万", "1200万超~2000万", "2000万超"]
N_COND = len(CONDITIONS)
N_COMBO_SLOTS = ab.N_COMBOS + 1  # index 0 (empty set) is never evaluated


def popularity_band(popularity: np.ndarray) -> np.ndarray:
    return np.select([popularity <= 1, popularity <= 3, popularity <= 6], [0, 1, 2], default=3)


class Context:
    """Per-row constants shared by all combinations of one evaluation period."""

    def __init__(self, frame: pd.DataFrame, months: list[pd.Timestamp]):
        self.frame = frame
        self.months = months
        self.month_labels = [m.strftime("%Y-%m") for m in months]
        month_position = {label: i for i, label in enumerate(self.month_labels)}
        self.row_month = frame["date"].dt.strftime("%Y-%m").map(month_position).to_numpy()
        race_ids = frame["race_id"].to_numpy().astype(str)
        self.starts = ab.segment_starts(race_ids)
        self.lengths = np.diff(np.append(self.starts, len(race_ids)))
        self.n_races = len(self.starts)
        self.race_code = np.repeat(np.arange(self.n_races), self.lengths)
        self.race_month = self.row_month[self.starts]
        self.target = frame["target"].to_numpy(dtype=float)
        self.payout = frame["win_payout"].to_numpy(dtype=float)
        self.pop_band = popularity_band(frame["popularity"].to_numpy(dtype=float))
        rank = frame["actual_rank"].to_numpy(dtype=float)
        field_max = np.repeat(np.maximum.reduceat(rank, self.starts), self.lengths)
        self.relevance = field_max - rank + 1
        order = np.lexsort((-self.relevance, self.race_code))
        position = np.arange(len(frame)) - np.repeat(self.starts, self.lengths)
        sorted_rel = self.relevance[order]
        discount = np.where(position < 3, 1.0 / np.log2(position + 2.0), 0.0)
        self.ideal_dcg = np.bincount(self.race_code, weights=sorted_rel * discount, minlength=self.n_races)
        self.discount = discount
        self.position = position
        distance = frame["current_distance"].to_numpy(dtype=float)
        field = frame["field_size"].to_numpy(dtype=float)
        prize = frame["race_first_prize"].to_numpy(dtype=float)
        # The feature cache is turf-only, so conditions are distance(3) + field size(2) + prize level(3).
        self.condition = np.zeros((len(frame), N_COND), dtype=bool)
        self.condition[:, 0] = distance <= 1400
        self.condition[:, 1] = (distance > 1400) & (distance <= 1800)
        self.condition[:, 2] = distance > 1800
        self.condition[:, 3] = field <= 12
        self.condition[:, 4] = field > 12
        self.condition[:, 5] = prize <= 12_000_000
        self.condition[:, 6] = (prize > 12_000_000) & (prize <= 20_000_000)
        self.condition[:, 7] = prize > 20_000_000
        self.winner = self.target == 1
        self.band_bin = None

    def rank_of(self, probability: np.ndarray) -> np.ndarray:
        """Within-race rank, ties broken by row order (== rank(method='first'))."""
        order = np.lexsort((-probability, self.race_code))
        ranks = np.empty(len(probability), dtype=np.int64)
        ranks[order] = self.position + 1
        return ranks


def combo_metric_arrays(ctx: Context, probability: np.ndarray) -> dict[str, np.ndarray]:
    """Additive per-month sums for one combination."""
    n_months = len(ctx.months)
    rm = ctx.row_month
    p_clip = np.clip(probability, EPS, 1 - EPS)
    y = ctx.target
    rank = ctx.rank_of(probability)
    top1 = rank == 1
    out: dict[str, np.ndarray] = {}

    def by_month(values: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        if mask is not None:
            return np.bincount(rm[mask], weights=values[mask], minlength=n_months)
        return np.bincount(rm, weights=values, minlength=n_months)

    out["winner_ll"] = by_month(-np.log(p_clip), ctx.winner)
    out["brier"] = by_month((y - probability) ** 2)
    out["binary_ll"] = by_month(-(y * np.log(p_clip) + (1 - y) * np.log(1 - p_clip)))
    out["top1_hit"] = by_month(y, top1)
    out["top1_payout"] = by_month(ctx.payout, top1)
    out["top1_pred"] = by_month(probability, top1)
    top3_hit_race = np.bincount(ctx.race_code[(rank <= 3) & ctx.winner], minlength=ctx.n_races) > 0
    out["top3_hit"] = np.bincount(ctx.race_month[top3_hit_race], minlength=n_months).astype(float)
    top3_pos = np.where(rank <= 3, 1.0 / np.log2(rank + 1.0), 0.0)
    dcg = np.bincount(ctx.race_code, weights=ctx.relevance * top3_pos, minlength=ctx.n_races)
    ndcg = np.divide(dcg, ctx.ideal_dcg, out=np.zeros_like(dcg), where=ctx.ideal_dcg > 0)
    out["ndcg3"] = np.bincount(ctx.race_month, weights=ndcg, minlength=n_months)

    bands = np.zeros((n_months, len(POP_BANDS), 6))
    for band in range(len(POP_BANDS)):
        in_band = ctx.pop_band == band
        sel = in_band & top1
        bands[:, band, 0] = by_month(np.ones(len(y)), sel)
        bands[:, band, 1] = by_month(y, sel)
        bands[:, band, 2] = by_month(probability, sel)
        bands[:, band, 3] = by_month(np.ones(len(y)), in_band)
        bands[:, band, 4] = by_month(probability, in_band)
        bands[:, band, 5] = by_month(y, in_band)
    out["pop_band"] = bands

    cond = np.zeros((n_months, N_COND, 2))
    loss_row = np.where(ctx.winner, -np.log(p_clip), 0.0)
    for index in range(N_COND):
        member = ctx.condition[:, index]
        cond[:, index, 0] = by_month(loss_row, member & ctx.winner)
        cond[:, index, 1] = by_month(np.ones(len(y)), member & ctx.winner)
    out["condition_ll"] = cond

    prob_bin = np.clip(np.digitize(probability, PROB_BINS) - 1, 0, len(PROB_BIN_LABELS) - 1)
    pb = np.zeros((n_months, len(PROB_BIN_LABELS), 3))
    for index in range(len(PROB_BIN_LABELS)):
        member = prob_bin == index
        pb[:, index, 0] = by_month(np.ones(len(y)), member)
        pb[:, index, 1] = by_month(probability, member)
        pb[:, index, 2] = by_month(y, member)
    out["prob_bin"] = pb
    return out


def compute_all_metrics(ctx: Context, assembled: dict) -> dict[str, np.ndarray]:
    """Return arrays shaped (4096, months, ...) with NaN for combinations that were not run."""
    store: dict[str, np.ndarray] = {}
    n_months = len(ctx.months)
    complete = assembled["complete"]
    for combo in np.flatnonzero(complete):
        probability = ab.combo_probabilities(ctx.frame, assembled["scores"][combo], assembled["temperature"][combo], ctx.months)
        arrays = combo_metric_arrays(ctx, probability)
        for name, values in arrays.items():
            if name not in store:
                store[name] = np.full((N_COMBO_SLOTS,) + values.shape, np.nan)
            store[name][combo + 1] = values
    store["temperature"] = np.full((N_COMBO_SLOTS, n_months), np.nan)
    store["temperature"][1:] = assembled["temperature"]
    store["month_races"] = np.bincount(ctx.race_month, minlength=n_months).astype(float)
    store["month_rows"] = np.bincount(ctx.row_month, minlength=n_months).astype(float)
    store["month_winners"] = np.bincount(ctx.row_month[ctx.winner], minlength=n_months).astype(float)
    return store


def save_metrics(path: Path, store: dict[str, np.ndarray], labels: list[str]) -> None:
    np.savez_compressed(path, month_labels=np.array(labels), **store)


def load_metrics(path: Path) -> dict[str, np.ndarray]:
    data = np.load(path, allow_pickle=False)
    return {key: data[key] for key in data.files}


# ------------------------------------------------------------------ derived tables

def month_mask(store: dict, labels: list[str] | None) -> np.ndarray:
    all_labels = [str(x) for x in store["month_labels"]]
    if labels is None:
        return np.ones(len(all_labels), dtype=bool)
    return np.array([label in labels for label in all_labels])


def scalar_metrics(store: dict, months: np.ndarray) -> pd.DataFrame:
    """Period-aggregated headline metrics per evaluated combination (index = combination id)."""
    races = store["month_races"][months].sum()
    winners = store["month_winners"][months].sum()
    rows = store["month_rows"][months].sum()

    def total(name: str) -> np.ndarray:
        return store[name][:, months].sum(axis=1)

    frame = pd.DataFrame({
        "winner_logloss": total("winner_ll") / winners,
        "brier": total("brier") / rows,
        "binary_logloss": total("binary_ll") / rows,
        "top1_hit_rate": total("top1_hit") / races,
        "top3_recall": total("top3_hit") / races,
        "ndcg3": total("ndcg3") / races,
        "top1_roi_pct": total("top1_payout") / (races * 100) * 100,
    })
    frame.index.name = "combo"
    return frame[~frame["winner_logloss"].isna()]


def monthly_metric(store: dict, name: str) -> np.ndarray:
    """(4096, months) per-month metric value."""
    if name == "winner_logloss":
        return store["winner_ll"] / store["month_winners"]
    if name == "brier":
        return store["brier"] / store["month_rows"]
    if name == "top1_hit_rate":
        return store["top1_hit"] / store["month_races"]
    if name == "top3_recall":
        return store["top3_hit"] / store["month_races"]
    raise KeyError(name)


def band_table(store: dict, months: np.ndarray) -> np.ndarray:
    """(4096, bands, 6) aggregated: top1 n/wins/pred, all n/pred/wins."""
    return store["pop_band"][:, months].sum(axis=1)


def overconfidence_metrics(store: dict, months: np.ndarray) -> pd.DataFrame:
    bands = band_table(store, months)
    races = store["month_races"][months].sum()
    result = {}
    for index, label in enumerate(POP_BANDS):
        n, hit, pred = bands[:, index, 0], bands[:, index, 1], bands[:, index, 2]
        all_n, all_pred, all_win = bands[:, index, 3], bands[:, index, 4], bands[:, index, 5]
        with np.errstate(invalid="ignore", divide="ignore"):
            result[f"top1_share_{label}"] = n / races
            result[f"top1_n_{label}"] = n
            result[f"top1_actual_{label}"] = hit / n
            result[f"top1_pred_{label}"] = pred / n
            result[f"top1_gap_{label}"] = pred / n - hit / n
            result[f"all_pred_{label}"] = all_pred / all_n
            result[f"all_actual_{label}"] = all_win / all_n
            result[f"all_gap_{label}"] = all_pred / all_n - all_win / all_n
    long_n = bands[:, 2:, 0].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        result["top1_longshot_n"] = long_n
        result["top1_longshot_share"] = long_n / races
        result["top1_longshot_actual"] = bands[:, 2:, 1].sum(axis=1) / long_n
        result["top1_longshot_pred"] = bands[:, 2:, 2].sum(axis=1) / long_n
        result["top1_longshot_gap"] = result["top1_longshot_pred"] - result["top1_longshot_actual"]
        all_long_n = bands[:, 2:, 3].sum(axis=1)
        result["all_longshot_gap"] = bands[:, 2:, 4].sum(axis=1) / all_long_n - bands[:, 2:, 5].sum(axis=1) / all_long_n
    frame = pd.DataFrame(result)
    frame.index.name = "combo"
    return frame.iloc[1:]


# ------------------------------------------------------------------ marginal / interaction analysis

def _values_with_pad(series: pd.Series | np.ndarray) -> np.ndarray:
    array = np.full(N_COMBO_SLOTS, np.nan)
    if isinstance(series, pd.Series):
        array[series.index.to_numpy()] = series.to_numpy()
    else:
        array[:] = series
    return array


def background_sets(bit_mask: int) -> np.ndarray:
    """Non-empty combinations that contain none of the bits in ``bit_mask``."""
    candidates = np.arange(1, N_COMBO_SLOTS)
    return candidates[(candidates & bit_mask) == 0]


def marginal_effects(values: np.ndarray, group_bit: int) -> pd.DataFrame:
    """Paired effect of adding a group: value(S + g) - value(S) over all non-empty backgrounds S."""
    bit = 1 << group_bit
    base = background_sets(bit)
    delta = values[base | bit] - values[base]
    size = np.array([bin(x).count("1") for x in base])
    return pd.DataFrame({"background": base, "background_size": size, "delta": delta}).dropna()


def group_contribution_table(values: np.ndarray, lower_is_better: bool = True, labels=None) -> pd.DataFrame:
    rows = []
    for position, key in enumerate(ab.GROUP_KEYS):
        effects = marginal_effects(values, position)
        delta = effects["delta"].to_numpy()
        improved = (delta < 0) if lower_is_better else (delta > 0)
        by_size = effects.groupby("background_size")["delta"].mean()
        rows.append({
            "group": key, "group_name": ab.GROUP_NAMES[key], "n_features": len(ab.GROUPS[key]),
            "n_pairs": len(delta), "mean_delta": delta.mean(), "median_delta": float(np.median(delta)),
            "share_improved": improved.mean(),
            "size_stratified_mean_delta": by_size.mean(),
            "mean_delta_small_backgrounds_1to3": by_size.loc[by_size.index <= 3].mean(),
            "mean_delta_large_backgrounds_8to11": by_size.loc[by_size.index >= 8].mean(),
            "delta_when_all_others_on": values[ab.N_COMBOS] - values[ab.N_COMBOS & ~(1 << position)],
        })
    table = pd.DataFrame(rows)
    return table.sort_values("mean_delta", ascending=lower_is_better).reset_index(drop=True)


def monthly_contribution(values_by_month: np.ndarray, month_labels: list[str]) -> pd.DataFrame:
    """Mean paired delta per group and month (rows: group, columns: month)."""
    result = {}
    for position, key in enumerate(ab.GROUP_KEYS):
        bit = 1 << position
        base = background_sets(bit)
        delta = values_by_month[base | bit] - values_by_month[base]
        result[key] = np.nanmean(delta, axis=0)
    return pd.DataFrame(result, index=month_labels).T


def interaction_effects(values: np.ndarray, bit_a: int, bit_b: int) -> pd.DataFrame:
    """I = [v(S+A+B) - v(S+B)] - [v(S+A) - v(S)] over non-empty backgrounds S without A and B."""
    a, b = 1 << bit_a, 1 << bit_b
    base = background_sets(a | b)
    value = (values[base | a | b] - values[base | b]) - (values[base | a] - values[base])
    return pd.DataFrame({"background": base, "interaction": value}).dropna()


FOCAL_PAIRS = [("G3", "G4"), ("G3", "G5"), ("G7", "G8"), ("G7", "G11"), ("G6", "G8"), ("G9", "G5")]


def interaction_table(values: np.ndarray, values_by_month: np.ndarray | None, month_labels: list[str]) -> pd.DataFrame:
    rows = []
    keys = ab.GROUP_KEYS
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            effect = interaction_effects(values, i, j)
            row = {"group_a": keys[i], "group_b": keys[j],
                   "focal": (keys[i], keys[j]) in FOCAL_PAIRS or (keys[j], keys[i]) in FOCAL_PAIRS,
                   "n_backgrounds": len(effect), "mean_interaction": effect["interaction"].mean(),
                   "share_synergy(<0)": (effect["interaction"] < 0).mean()}
            if values_by_month is not None:
                a, b = 1 << i, 1 << j
                base = background_sets(a | b)
                monthly = (values_by_month[base | a | b] - values_by_month[base | b]) - (values_by_month[base | a] - values_by_month[base])
                monthly_mean = np.nanmean(monthly, axis=0)
                row["months_synergy"] = int((monthly_mean < 0).sum())
                row["months_antagonism"] = int((monthly_mean > 0).sum())
                row["months_total"] = len(monthly_mean)
                row["monthly_mean_interaction"] = ";".join(f"{label}:{value:+.4f}" for label, value in zip(month_labels, monthly_mean))
            rows.append(row)
    table = pd.DataFrame(rows)
    table["abs_mean_interaction"] = table["mean_interaction"].abs()
    return table.sort_values("abs_mean_interaction", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------ bootstrap

def race_loss_vectors(ctx: Context, probability: np.ndarray) -> dict[str, np.ndarray]:
    p_clip = np.clip(probability, EPS, 1 - EPS)
    rank = ctx.rank_of(probability)
    return {
        "loss": np.bincount(ctx.race_code[ctx.winner], weights=-np.log(p_clip[ctx.winner]), minlength=ctx.n_races),
        "winners": np.bincount(ctx.race_code[ctx.winner], minlength=ctx.n_races).astype(float),
        "top1": np.bincount(ctx.race_code[rank == 1], weights=ctx.target[rank == 1], minlength=ctx.n_races),
    }


def paired_bootstrap(a: dict, b: dict, n_boot: int = 2000, seed: int = 20260101) -> dict:
    """Race-level bootstrap of (candidate - reference) winner logloss and Top1 hit rate."""
    rng = np.random.default_rng(seed)
    n = len(a["loss"])
    d_loss = a["loss"] - b["loss"]
    d_top1 = a["top1"] - b["top1"]
    winners = a["winners"]
    ll_samples, hit_samples = np.empty(n_boot), np.empty(n_boot)
    for start in range(0, n_boot, 250):
        stop = min(n_boot, start + 250)
        idx = rng.integers(0, n, size=(stop - start, n))
        ll_samples[start:stop] = d_loss[idx].sum(axis=1) / winners[idx].sum(axis=1)
        hit_samples[start:stop] = d_top1[idx].mean(axis=1)
    return {
        "delta_logloss": d_loss.sum() / winners.sum(), "ci_low": np.percentile(ll_samples, 2.5), "ci_high": np.percentile(ll_samples, 97.5),
        "p_improve": float((ll_samples < 0).mean()),
        "delta_top1": d_top1.mean(), "top1_ci_low": np.percentile(hit_samples, 2.5), "top1_ci_high": np.percentile(hit_samples, 97.5),
    }


def metric_table_with_labels(scalar: pd.DataFrame) -> pd.DataFrame:
    frame = scalar.copy()
    frame.insert(0, "mask", [ab.combo_index_to_mask(int(i)) for i in frame.index])
    frame.insert(1, "n_groups", [ab.combo_index_to_mask(int(i)).count("1") for i in frame.index])
    frame.insert(2, "groups", ["+".join(ab.mask_to_groups(ab.combo_index_to_mask(int(i)))) for i in frame.index])
    frame.insert(3, "n_features", [len(ab.mask_to_features(ab.combo_index_to_mask(int(i)))) for i in frame.index])
    return frame

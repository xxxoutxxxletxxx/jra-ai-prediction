"""学習準備パイプライン: データセット → 学習ストア → OOF → 月次モデル束。結果はキャッシュして再利用する。"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Dict, Optional

import pandas as pd

from raceverse.config import CACHE_DIR, RaceverseConfig
from raceverse.dataset import Dataset, build_dataset
from raceverse.store import (Store, build_store, compute_pace_oof, load_store, perf_training_table, save_store,
                             time_training_table)
from raceverse.training import ModelBundle, OOFCache, compute_oof_cache, fit_bundle

LOGGER = logging.getLogger(__name__)


@dataclass
class Prepared:
    cfg: RaceverseConfig
    ds: Dataset
    store: Store
    oof: OOFCache

    def bundle(self, as_of: pd.Timestamp) -> ModelBundle:
        return fit_bundle(self.store, self.ds, self.cfg, self.oof, as_of)


STORE_VERSION = 4  # ストア生成ロジックを変えたら上げる


def _store_path(cfg: RaceverseConfig, ds: Dataset):
    confirmed = ds.races[~ds.races["is_upcoming"]]
    impact_hash = hashlib.md5(json.dumps(asdict(cfg.pace_impact), sort_keys=True).encode()).hexdigest()[:8]
    tag = (f"v{STORE_VERSION}_{len(confirmed)}_{confirmed['date'].max():%Y%m%d}_{cfg.pace.train_start}_"
           f"{cfg.pace.training_formation_draws}_{cfg.performance.training_draws}_{cfg.winning_time.train_start}_"
           f"{cfg.random_seed}_{impact_hash}")
    return CACHE_DIR / f"store_{tag}.pkl"


def _store_matches(store: Store, ds: Dataset) -> bool:
    table = store.race_table
    if "race_id" not in table or table["race_pos"].max() >= len(ds.races):
        return False
    return bool((ds.races.loc[table["race_pos"].to_numpy(), "race_id"].to_numpy() == table["race_id"].to_numpy()).all())


def prepare(cfg: RaceverseConfig, upcoming_from: Optional[pd.Timestamp] = None, use_cache: bool = True,
            max_store_races: Optional[int] = None) -> Prepared:
    t0 = time.time()
    ds = build_dataset(cfg, upcoming_from=upcoming_from, use_cache=use_cache)
    LOGGER.info("dataset ready (%.0fs)", time.time() - t0)
    path = _store_path(cfg, ds)
    store = None
    if use_cache and max_store_races is None and path.exists():
        store = load_store(path)
        if _store_matches(store, ds):
            LOGGER.info("store loaded from cache: %s", path)
        else:
            LOGGER.info("store cache does not match dataset; rebuilding")
            store = None
    if store is None:
        store = build_store(ds, cfg, max_races=max_store_races)
        compute_pace_oof(store, cfg)
        if max_store_races is None:
            save_store(store, path)
        LOGGER.info("store built (%.0fs): rows=%d races=%d ability_races=%d", time.time() - t0, len(store.y),
                    len(store.race_table), len(store.ability_ctx))
    ds.prepare_course_bias(store.ability_ctx.keys())
    for pos, ctx in store.ability_ctx.items():
        ds.attach_course_bias(ctx, pos)
    LOGGER.info("course bias attached to %d races (%.0fs)", len(store.ability_ctx), time.time() - t0)
    time_table = time_training_table(store, ds)
    perf_table = perf_training_table(store, cfg)
    oof = compute_oof_cache(store, ds, cfg, time_table, perf_table)
    LOGGER.info("OOF cache ready (%.0fs)", time.time() - t0)
    return Prepared(cfg, ds, store, oof)

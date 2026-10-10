"""データセット統合: 実データ + as-of基準 + 履歴 + 騎手プロフィール + 既存能力指標 -> RaceContext。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from raceverse.adapters import existing_ability
from raceverse.adapters.race_data import RaceData, load_race_data
from raceverse.baselines import walk_forward_baseline
from raceverse.config import CACHE_DIR, RaceverseConfig
from raceverse.course_bias import CourseBiasEngine
from raceverse.history_features import RunHistory, build_run_history
from raceverse.jockey_profiles import JockeyProfiles, month_index
from raceverse.pace_impact import PaceImpactProfiles, build_pace_impacts
from raceverse.schemas import RaceContext
from raceverse.track_speed import TrackSpeedBuilder

LOGGER = logging.getLogger(__name__)


@dataclass
class Dataset:
    cfg: RaceverseConfig
    races: pd.DataFrame
    runs: pd.DataFrame
    laps: np.ndarray
    history: RunHistory
    profiles: JockeyProfiles
    jockey_codes: Dict[str, int]
    run_slices: Dict[str, slice]
    base_month: pd.Timestamp
    track_builder: TrackSpeedBuilder
    warnings: List[str]
    _snapshots: Dict[int, Dict[str, np.ndarray]]
    first_turn_default: float
    impacts: Optional[PaceImpactProfiles] = None
    course_bias: Optional[CourseBiasEngine] = None

    def snapshot(self, month: int) -> Dict[str, np.ndarray]:
        """月次スナップショット(騎手プロフィール + Pace Impact)。月は昇順に処理されるので直近数か月だけ保持する。"""
        if month not in self._snapshots:
            snap = self.profiles.snapshot(month)
            if self.impacts is not None:
                snap.update(self.impacts.snapshot(month))
            self._snapshots[month] = snap
            while len(self._snapshots) > 4:
                self._snapshots.pop(next(iter(self._snapshots)))
        return self._snapshots[month]

    def race_pos(self, race_id: str) -> int:
        return int(self.races.index[self.races["race_id"] == race_id][0])

    def make_context(self, pos: int, with_track_context: bool = True, require_ability: bool = True) -> Optional[RaceContext]:
        race = self.races.iloc[pos]
        sl = self.run_slices[race["race_id"]]
        runs = self.runs.iloc[sl]
        if require_ability:
            has = runs["ability"].notna().to_numpy()
        else:
            has = np.ones(len(runs), dtype=bool)
        idx = np.arange(sl.start, sl.stop)[has]
        if len(idx) < 4:
            return None
        sub = self.runs.iloc[idx]
        order = np.argsort(sub["umaban"].to_numpy(), kind="stable")
        idx = idx[order]
        sub = self.runs.iloc[idx]
        notes: List[str] = []
        if has.sum() < len(runs):
            notes.append(f"{int((~has).sum())} runners without ability score were dropped")
        k = self.cfg.formation.max_history_runs
        ctx = RaceContext(
            race_id=race["race_id"], date=race["date"], track=race["track"], surface=race["surface"],
            distance_m=int(race["distance_m"]), layout=race["layout"], going=int(race["going"]),
            class_group=race["class_group"], age_class=race["age_class"], meet_id=race["meet_id"],
            meet_day=int(race["meet_day"]), course_week=int(race["course_week"]), month=int(race["month"]),
            first_turn_distance_m=float(race["first_turn_distance_m"]) if pd.notna(race["first_turn_distance_m"]) else np.nan,
            first_turn_missing=bool(pd.isna(race["first_turn_distance_m"])),
            early_ref=float(race["early_ref"]) if pd.notna(race["early_ref"]) else np.nan,
            early_section_m=float(race["early_section_m"]) if pd.notna(race["early_section_m"]) else np.nan,
            win_time_base=float(race["win_time_base"]) if pd.notna(race["win_time_base"]) else np.nan,
            month_idx=int(race["month_idx"]),
            horse_ids=sub["horse_id"].tolist(), umaban=sub["umaban"].to_numpy(),
            jockey_idx=sub["jockey_idx"].to_numpy(),
            hist_q=self.history.q[idx][:, :k], hist_j=self.history.jockey[idx][:, :k],
            closing_skill=self.history.closing_skill[idx], rest_days=self.history.rest_days[idx],
            age=sub["age"].to_numpy(dtype=float), weight_carried=sub["weight_carried"].to_numpy(dtype=float),
            ability=sub["ability"].to_numpy(dtype=float), odds=sub["odds"].to_numpy(dtype=float),
            warnings=notes, horse_idx=sub["horse_idx"].to_numpy(), wakuban=sub["wakuban"].to_numpy(),
        )
        if with_track_context:
            ctx.track_context = self.track_builder.build_as_of(pos)
        return ctx

    def prepare_course_bias(self, positions) -> None:
        """コースバイアス統計を一括計算する(予測対象より前の確定結果だけ)。"""
        if self.course_bias is not None and self.cfg.course_bias.enabled:
            self.course_bias.compute(list(positions))

    def attach_course_bias(self, ctx: RaceContext, pos: int) -> RaceContext:
        if self.course_bias is None or not self.cfg.course_bias.enabled:
            return ctx
        if ctx.wakuban is None:
            runs = self.runs.iloc[self.run_slices[ctx.race_id]].set_index("horse_id")
            ctx.wakuban = runs.loc[ctx.horse_ids, "wakuban"].to_numpy()
        ctx.bias = self.course_bias.get(pos)
        return ctx

    def outcomes(self, ctx: RaceContext) -> pd.DataFrame:
        """評価専用。予測入力には使わない。"""
        sl = self.run_slices[ctx.race_id]
        runs = self.runs.iloc[sl].set_index("horse_id")
        return runs.loc[ctx.horse_ids, ["finish", "time_sec", "odds", "popularity", "q_early", "early_rank"]].reset_index()


def _baseline_cache_path(cfg: RaceverseConfig, races: pd.DataFrame):
    tag = f"{len(races)}_{races['date'].max():%Y%m%d}_{cfg.baseline_alpha}_{cfg.baseline_first_month}"
    return CACHE_DIR / f"baselines_{tag}.parquet"


def build_dataset(cfg: RaceverseConfig, upcoming_from: Optional[pd.Timestamp] = None,
                  use_cache: bool = True) -> Dataset:
    data: RaceData = load_race_data(min_year=cfg.data_min_year, upcoming_from=upcoming_from)
    races, runs = data.races, data.runs

    cache_path = _baseline_cache_path(cfg, races)
    first_month = pd.Timestamp(cfg.baseline_first_month)
    if use_cache and cache_path.exists():
        cols = pd.read_parquet(cache_path)
        races["win_time_base"] = cols["win_time_base"].to_numpy()
        races["early_ref"] = cols["early_ref"].to_numpy()
        LOGGER.info("baseline cache loaded: %s", cache_path)
    else:
        LOGGER.info("fitting monthly walk-forward baselines ...")
        races["win_time_base"] = walk_forward_baseline(races, "win_time_sec", first_month, cfg.baseline_alpha)
        races["early_ref"] = walk_forward_baseline(races, "early_split_sec", first_month, cfg.baseline_alpha)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        races[["win_time_base", "early_ref"]].to_parquet(cache_path)
    races["track_resid"] = races["win_time_sec"] - races["win_time_base"]
    races["pace_delta"] = races["early_split_sec"] - races["early_ref"]

    base_month = races["date"].min().to_period("M").to_timestamp()
    races["month_idx"] = month_index(races["date"], base_month)
    n_months = int(races["month_idx"].max()) + 1

    history = build_run_history(runs, cfg.formation.max_history_runs)
    profiles = JockeyProfiles.build(
        runs, races, n_jockeys=len(data.jockey_codes), base_month=base_month, n_months=n_months,
        frontness_k=cfg.formation.jockey_frontness_shrinkage_k, tempo_k=cfg.pace.lead_tempo_shrinkage_k,
        lead_rank_cut=cfg.formation.lead_rank_cut,
    )
    runs = _attach_ability(runs, races)
    runs["horse_idx"] = pd.factorize(runs["horse_id"])[0].astype(np.int64)
    slices = _run_slices(runs)
    track_builder = TrackSpeedBuilder(races, cfg.track_speed)
    first_turn_default = float(races["first_turn_distance_m"].median())
    ds = Dataset(cfg, races, runs, data.laps, history, profiles, data.jockey_codes, slices, base_month,
                 track_builder, data.warnings, {}, first_turn_default)
    ds.impacts = build_pace_impacts(ds, cfg, use_cache)
    ds.course_bias = CourseBiasEngine(races, runs, cfg.course_bias)
    return ds


def _run_slices(runs: pd.DataFrame) -> Dict[str, slice]:
    ids = runs["race_id"].to_numpy()
    change = np.flatnonzero(np.r_[True, ids[1:] != ids[:-1], True])
    return {ids[a]: slice(int(a), int(b)) for a, b in zip(change[:-1], change[1:])}


def _attach_ability(runs: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """既存Rankerの能力指標(OOF)を結合。未開催レースは本番Ranker出力(output/predictions.csv)から。"""
    table = existing_ability.load_ability_table()
    merged = runs.merge(table[["race_id", "horse_id", "ability_score"]], on=["race_id", "horse_id"], how="left")
    merged = merged.rename(columns={"ability_score": "ability"})
    merged.index = runs.index
    upcoming_ids = set(races.loc[races["is_upcoming"], "race_id"])
    if upcoming_ids:
        prod = existing_ability.load_production_ability()
        race_keys = races.loc[races["is_upcoming"], ["race_id", "date", "track", "race_num"]]
        race_keys = race_keys.assign(race_date=race_keys["date"].dt.strftime("%Y-%m-%d"),
                                     idRaceNum=race_keys["race_num"].astype(int))
        prod = prod.assign(track=prod["idJyoCD"], idRaceNum=prod["idRaceNum"].astype(int), umaban=prod["Umaban"].astype(int))
        key = race_keys.merge(prod, left_on=["race_date", "track", "idRaceNum"],
                              right_on=["race_date", "track", "idRaceNum"], how="inner")
        lookup = {(r, u): a for r, u, a in zip(key["race_id"], key["umaban"], key["ability_score"])}
        mask = merged["race_id"].isin(upcoming_ids)
        merged.loc[mask, "ability"] = [lookup.get((r, u), np.nan) for r, u in zip(merged.loc[mask, "race_id"], merged.loc[mask, "umaban"])]
    return merged

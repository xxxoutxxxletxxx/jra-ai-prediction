"""JRA-VAN(race.db)から RACEVERSE 用のレース表・出走表を作る実データアダプタ。

使用する実カラム(src/backtest.py と tools の調査結果に対応):
  NL_RA_RACE : idYear/idMonthDay/idJyoCD/idKaiji/idNichiji/idRaceNum, Kyori, TrackCD, CourseKubunCD,
               GradeCD, JyokenInfoSyubetuCD, Honsyokin0(100円単位), SyussoTosu,
               TenkoBabaSibaBabaCD/TenkoBabaDirtBabaCD, LapTime0..24(0.1秒), HaronTimeS3(前3ラップ合計, 0.1秒)
  NL_SE_RACE_UMA: 同キー, Wakuban, Umaban, KettoNum, KisyuCode, Barei, SexCD, Futan, KakuteiJyuni,
               Time(MSST), Jyuni1c..4c, HaronTimeL3, Odds, Ninki, BaTaijyu, IJyoCD
race_id は src.backtest.race_id と同じ "年-月日-場-回-日-R" 形式。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from raceverse.config import DEFAULT_DB, ROOT

LOGGER = logging.getLogger(__name__)

RACE_KEY = ["idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum"]
COURSE_FEATURES_CSV = ROOT / "data" / "output" / "course_features_ver6.csv"
TRACK_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
RA_COLUMNS = RACE_KEY + [
    "headDataKubun", "headMakeDate", "Kyori", "TrackCD", "CourseKubunCD", "GradeCD", "JyokenInfoSyubetuCD",
    "Honsyokin0", "SyussoTosu", "TenkoBabaSibaBabaCD", "TenkoBabaDirtBabaCD", "HaronTimeS3", "HaronTimeL3",
] + [f"LapTime{i}" for i in range(25)]
SE_COLUMNS = RACE_KEY + [
    "headDataKubun", "headMakeDate", "Wakuban", "Umaban", "KettoNum", "KisyuCode", "Barei", "SexCD", "Futan",
    "KakuteiJyuni", "Time", "Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c", "HaronTimeL3", "Odds", "Ninki", "Bamei",
    "BaTaijyu", "IJyoCD",
]


@dataclass
class RaceData:
    races: pd.DataFrame
    runs: pd.DataFrame
    laps: np.ndarray  # [n_races, 25] 秒。races と同順
    jockey_codes: dict = field(default_factory=dict)  # KisyuCode -> jockey_idx
    warnings: List[str] = field(default_factory=list)


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def parse_msst(values: pd.Series) -> pd.Series:
    """JRA-VANのTime(MSST: 分1桁+秒2桁+0.1秒)を秒へ。0/欠損はNaN。"""
    raw = _num(values).astype(int)
    seconds = (raw // 1000) * 60 + (raw % 1000) / 10.0
    return seconds.where(raw > 0)


def surface_from_track_code(track_cd: pd.Series) -> pd.Series:
    """TrackCD 10-22=芝, 23-29=ダート, 51-59=障害。(src.backtest.surface は '2x' を芝と扱うため使わない)"""
    code = _num(track_cd).astype(int)
    result = pd.Series("other", index=track_cd.index)
    result[(code >= 10) & (code <= 22)] = "turf"
    result[(code >= 23) & (code <= 29)] = "dirt"
    return result


def class_group_from_prize(prize_yen: pd.Series, grade: pd.Series) -> pd.Series:
    bins = [-1, 6_500_000, 9_000_000, 13_000_000, 25_000_000, 1e12]
    labels = ["C0", "C1", "C2", "C3", "C4"]
    group = pd.cut(prize_yen, bins=bins, labels=labels).astype(str)
    grade = grade.fillna("").astype(str).str.upper()
    group = group.where(~grade.isin(["A", "B", "C"]), "G" + grade.map({"A": "1", "B": "2", "C": "3"}))
    return group


def age_class_from_code(code: pd.Series) -> pd.Series:
    mapping = {"11": "2yo", "12": "3yo", "13": "3up", "14": "3up"}
    return code.astype(str).map(mapping).fillna("other")


def first_lap_meters(distance: pd.Series) -> pd.Series:
    """LapTime0 が表す区間長(m)。200mの倍数でない距離では端数(100m等)が先頭ラップ。"""
    remainder = distance % 200
    return remainder.where(remainder > 0, 200)


def _load_course_first_turn() -> pd.DataFrame:
    if not COURSE_FEATURES_CSV.exists():
        return pd.DataFrame(columns=["track", "distance_m", "track_cd", "first_turn_distance_m"])
    frame = pd.read_csv(COURSE_FEATURES_CSV, encoding="utf-8-sig", dtype={"TrackCD": str})
    return pd.DataFrame({
        "track": frame["JyoCD"].astype(int).astype(str).str.zfill(2),
        "distance_m": frame["Kyori_m"].astype(int),
        "track_cd": frame["TrackCD"].astype(str),
        "first_turn_distance_m": pd.to_numeric(frame["first_corner_distance_m"], errors="coerce"),
    }).drop_duplicates(["track", "distance_m", "track_cd"])


def _read(connection: sqlite3.Connection, table: str, columns: List[str], where: str) -> pd.DataFrame:
    query = f"SELECT {', '.join(columns)} FROM {table} WHERE {where}"
    return pd.read_sql_query(query, connection)


def make_race_id(frame: pd.DataFrame) -> pd.Series:
    return frame[RACE_KEY[0]].astype(str).str.strip().str.cat(
        [frame[column].astype(str).str.strip() for column in RACE_KEY[1:]], sep="-"
    )


def load_race_data(
    db_path: Path = DEFAULT_DB,
    min_year: int = 2015,
    upcoming_from: Optional[pd.Timestamp] = None,
) -> RaceData:
    """確定済みレース(headDataKubun=7)を読み込む。upcoming_from を渡すとその日以降の未確定出走表も読む。"""
    connection = sqlite3.connect(str(db_path))
    warnings: List[str] = []
    try:
        year_where = f"idYear >= '{int(min_year)}'"
        ra_all = _read(connection, "NL_RA_RACE", RA_COLUMNS, year_where)
        se_all = _read(connection, "NL_SE_RACE_UMA", SE_COLUMNS, year_where)
    finally:
        connection.close()

    for frame in (ra_all, se_all):
        frame["race_id"] = make_race_id(frame)
        frame["date"] = pd.to_datetime(frame["idYear"] + frame["idMonthDay"], format="%Y%m%d", errors="coerce")
    ra_all = ra_all[ra_all["date"].notna() & ra_all["idJyoCD"].isin(TRACK_NAMES)]
    se_all = se_all[se_all["date"].notna() & se_all["idJyoCD"].isin(TRACK_NAMES)]

    confirmed_races = ra_all[ra_all["headDataKubun"] == "7"].drop_duplicates("race_id", keep="last")
    confirmed_runs = se_all[(se_all["headDataKubun"] == "7") & (_num(se_all["KakuteiJyuni"]) > 0)]
    confirmed_runs = confirmed_runs.drop_duplicates(["race_id", "KettoNum"], keep="last")

    upcoming_races = upcoming_runs = None
    if upcoming_from is not None:
        known = set(confirmed_races["race_id"])
        upcoming_races = ra_all[(ra_all["date"] >= upcoming_from) & ~ra_all["race_id"].isin(known)]
        upcoming_races = upcoming_races.sort_values("headMakeDate").drop_duplicates("race_id", keep="last")
        upcoming_runs = se_all[
            (se_all["date"] >= upcoming_from) & ~se_all["race_id"].isin(known)
            & (_num(se_all["KakuteiJyuni"]) == 0) & (_num(se_all["Umaban"]) > 0)
        ].sort_values("headMakeDate").drop_duplicates(["race_id", "KettoNum"], keep="last")

    races = pd.concat([confirmed_races] + ([upcoming_races] if upcoming_races is not None else []), ignore_index=True)
    runs = pd.concat([confirmed_runs] + ([upcoming_runs] if upcoming_runs is not None else []), ignore_index=True)
    races["is_upcoming"] = ~races["race_id"].isin(set(confirmed_races["race_id"]))

    races = _build_races(races, runs, warnings)
    runs = _build_runs(runs, races, warnings)
    # 出走表の無いレースは捨てる
    races = races[races["race_id"].isin(set(runs["race_id"]))].copy()
    runs = runs[runs["race_id"].isin(set(races["race_id"]))].copy()
    races = races.sort_values(["date", "race_id"]).reset_index(drop=True)
    laps = _lap_matrix(races)
    races = races.drop(columns=[f"LapTime{i}" for i in range(25)])
    runs = runs.sort_values(["date", "race_id", "umaban"]).reset_index(drop=True)
    codes = {code: i for i, code in enumerate(sorted(c for c in runs["jockey_code"].unique() if c))}
    runs["jockey_idx"] = runs["jockey_code"].map(codes).fillna(-1).astype(int)
    LOGGER.info("loaded races=%d runs=%d (upcoming races=%d)", len(races), len(runs), int(races["is_upcoming"].sum()))
    return RaceData(races=races, runs=runs, laps=laps, jockey_codes=codes, warnings=warnings)


def _lap_matrix(races: pd.DataFrame) -> np.ndarray:
    laps = np.stack([_num(races[f"LapTime{i}"]).to_numpy(dtype=np.float32) for i in range(25)], axis=1) / 10.0
    return laps


def _build_races(ra: pd.DataFrame, runs: pd.DataFrame, warnings: List[str]) -> pd.DataFrame:
    races = ra.copy()
    races["track"] = races["idJyoCD"]
    races["surface"] = surface_from_track_code(races["TrackCD"])
    races["distance_m"] = _num(races["Kyori"]).astype(int)
    races["layout"] = races["TrackCD"].astype(str) + races["CourseKubunCD"].astype(str).str.strip()
    races["track_cd"] = races["TrackCD"].astype(str).str.strip()  # 内回り/外回りを含む
    races["course_kubun"] = races["CourseKubunCD"].astype(str).str.strip()  # 芝の使用コースA-D(ダートは空)
    going = np.where(races["surface"] == "turf", _num(races["TenkoBabaSibaBabaCD"]), _num(races["TenkoBabaDirtBabaCD"]))
    races["going"] = going.astype(int)
    races["prize_yen"] = _num(races["Honsyokin0"]) * 100.0
    races["class_group"] = class_group_from_prize(races["prize_yen"], races["GradeCD"])
    races["age_class"] = age_class_from_code(races["JyokenInfoSyubetuCD"])
    races["is_stakes"] = races["GradeCD"].astype(str).str.upper().isin(["A", "B", "C", "D"])
    run_counts = runs.groupby("race_id").size()
    races["field_size"] = _num(races["SyussoTosu"]).astype(int)
    missing = races["field_size"] <= 0
    races.loc[missing, "field_size"] = races.loc[missing, "race_id"].map(run_counts).fillna(0).astype(int)
    races["meet_id"] = races["idYear"] + "-" + races["idJyoCD"] + "-" + races["idKaiji"]
    races["meet_day"] = _num(races["idNichiji"]).astype(int)
    races["race_num"] = _num(races["idRaceNum"]).astype(int)
    races["month"] = races["date"].dt.month
    races["course_week"] = (races["meet_day"] - 1) // 2 + 1
    races["early_split_sec"] = (_num(races["HaronTimeS3"]) / 10.0).where(_num(races["HaronTimeS3"]) > 0)
    lap_sum3 = sum(_num(races[f"LapTime{i}"]) for i in range(3)) / 10.0
    fallback = lap_sum3.where(sum((_num(races[f"LapTime{i}"]) > 0).astype(int) for i in range(3)) == 3)
    races["early_split_sec"] = races["early_split_sec"].fillna(fallback)
    races["early_section_m"] = first_lap_meters(races["distance_m"]) + 400  # 先頭3ラップの区間長(未開催でも定義できる)
    races["race_last3f_sec"] = (_num(races["HaronTimeL3"]) / 10.0).where(_num(races["HaronTimeL3"]) > 0)

    winners = runs[(_num(runs["KakuteiJyuni"]) == 1)]
    win_time = parse_msst(winners["Time"]).groupby(winners["race_id"]).min()
    races["win_time_sec"] = races["race_id"].map(win_time)

    course = _load_course_first_turn()
    keyed = races[["race_id", "track", "distance_m", "TrackCD"]].rename(columns={"TrackCD": "track_cd"})
    keyed["track_cd"] = keyed["track_cd"].astype(str)
    merged = keyed.merge(course, on=["track", "distance_m", "track_cd"], how="left")
    races["first_turn_distance_m"] = merged["first_turn_distance_m"].to_numpy()
    n_missing = int((races["surface"].isin(["turf", "dirt"]) & races["first_turn_distance_m"].isna()).sum())
    if n_missing:
        warnings.append(f"first_turn_distance_m missing for {n_missing} races (imputed downstream, flagged)")

    races = races[races["surface"].isin(["turf", "dirt"])].copy()  # 障害は対象外
    keep = [
        "race_id", "date", "track", "surface", "distance_m", "layout", "track_cd", "course_kubun", "going",
        "prize_yen", "class_group",
        "age_class", "is_stakes", "field_size", "meet_id", "meet_day", "course_week", "race_num", "month",
        "early_split_sec", "early_section_m", "race_last3f_sec", "win_time_sec", "first_turn_distance_m",
        "is_upcoming", "idYear", "idMonthDay", "idJyoCD", "idKaiji", "idNichiji", "idRaceNum",
    ] + [f"LapTime{i}" for i in range(25)]
    return races[keep].reset_index(drop=True)


def _build_runs(se: pd.DataFrame, races: pd.DataFrame, warnings: List[str]) -> pd.DataFrame:
    runs = se[se["race_id"].isin(set(races["race_id"]))].copy()
    out = pd.DataFrame({
        "race_id": runs["race_id"].to_numpy(),
        "date": runs["date"].to_numpy(),
        "horse_id": runs["KettoNum"].astype(str).to_numpy(),
        "horse_name": runs["Bamei"].fillna("").astype(str).str.strip().to_numpy(),
        "umaban": _num(runs["Umaban"]).astype(int).to_numpy(),
        "wakuban": _num(runs["Wakuban"]).astype(int).to_numpy(),
        "jockey_code": runs["KisyuCode"].astype(str).str.strip().to_numpy(),
        "age": _num(runs["Barei"]).astype(int).to_numpy(),
        "sex": runs["SexCD"].astype(str).to_numpy(),
        "weight_carried": (_num(runs["Futan"]) / 10.0).to_numpy(),
        "finish": _num(runs["KakuteiJyuni"]).astype(int).to_numpy(),
        "time_sec": parse_msst(runs["Time"]).to_numpy(),
        "c1": _num(runs["Jyuni1c"]).astype(int).to_numpy(),
        "c2": _num(runs["Jyuni2c"]).astype(int).to_numpy(),
        "c3": _num(runs["Jyuni3c"]).astype(int).to_numpy(),
        "c4": _num(runs["Jyuni4c"]).astype(int).to_numpy(),
        "last3f_sec": (_num(runs["HaronTimeL3"]) / 10.0).where(_num(runs["HaronTimeL3"]) > 0).to_numpy(),
        "odds": (_num(runs["Odds"]) / 10.0).to_numpy(),
        "popularity": _num(runs["Ninki"]).astype(int).to_numpy(),
    })
    out["jockey_code"] = out["jockey_code"].where(~out["jockey_code"].isin(["", "00000", "nan"]), "")
    field = races.set_index("race_id")["field_size"]
    out["field_size"] = out["race_id"].map(field).to_numpy()

    corners = out[["c1", "c2", "c3", "c4"]].to_numpy()
    valid = (corners >= 1) & (corners <= out["field_size"].to_numpy()[:, None])
    first = np.where(valid.any(axis=1), valid.argmax(axis=1), -1)
    early_rank = np.where(first >= 0, corners[np.arange(len(out)), np.maximum(first, 0)], 0)
    n = out["field_size"].to_numpy()
    q = np.where((first >= 0) & (n > 1), (early_rank - 1) / np.maximum(n - 1, 1), np.nan)
    out["early_corner_idx"] = first + 1  # 1..4, 0=無効
    out["early_rank"] = early_rank
    out["q_early"] = q  # 0=先頭, 1=最後方 (仕様3.2)

    median_l3 = out.groupby("race_id")["last3f_sec"].transform("median")
    out["closing_rel"] = out["last3f_sec"] - median_l3  # 負=速い上がり(過去走の代理指標)
    return out

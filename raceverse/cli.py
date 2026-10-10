"""RACEVERSE CLI。

  python -m raceverse.cli prepare                       # データ読込・基準・学習ストアのキャッシュ作成
  python -m raceverse.cli backtest --sims 10000         # 独立Walk-Forwardバックテスト(既存Rankerと同一期間・同一馬)
  python -m raceverse.cli predict --date 2026-10-10     # 未開催レースの勝率・展開・時計を出力
  python -m raceverse.cli simulate --race-id <id>       # 確定済みレースを当時の情報だけで再現(検証用)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from raceverse.config import REPORT_DIR, load_config
from raceverse.evaluation import power_normalize
from raceverse.pipeline import Prepared, prepare
from raceverse.reports import write_race_outputs
from raceverse.simulator import simulate_race

LOGGER = logging.getLogger("raceverse")
ROOT = Path(__file__).resolve().parents[1]


def latest_gamma(level: str) -> Optional[float]:
    files = sorted(REPORT_DIR.glob("backtest_*/calibration_gammas.csv"))
    if not files:
        return None
    frame = pd.read_csv(files[-1])
    frame = frame[frame["level"] == level]
    return float(frame["gamma"].iloc[-1]) if len(frame) else None


def _calibrate(result, gamma: Optional[float]) -> Optional[pd.Series]:
    if gamma is None:
        return None
    frame = result.horses[["race_id", "win_probability"]]
    return power_normalize(frame, "win_probability", gamma).reset_index(drop=True)


def _production_maps() -> Dict[tuple, dict]:
    path = ROOT / "output" / "predictions.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"idJyoCD": str, "idRaceNum": str})
    out = {}
    for _, r in frame.iterrows():
        out[(r["race_date"], str(r["idJyoCD"]).zfill(2), int(r["idRaceNum"]), int(r["Umaban"]))] = {
            "name": r["Bamei"], "ranker_p": float(r["predicted_win_probability"])}
    return out


def cmd_prepare(args) -> None:
    cfg = load_config(args.config)
    prepare(cfg, use_cache=not args.rebuild)


def cmd_backtest(args) -> None:
    from raceverse.backtest import LEVELS, run_backtest

    cfg = load_config(args.config)
    cfg.random_seed = args.seed if args.seed is not None else cfg.random_seed
    P = prepare(cfg, use_cache=not args.rebuild)
    levels = args.levels.split(",") if args.levels else LEVELS
    summary = run_backtest(P, out_dir=args.out, n_sims=args.sims, levels=levels,
                           max_races_per_month=args.max_races_per_month, test_start=args.start, test_end=args.end)
    print(f"done in {summary['runtime_sec']:.0f}s -> {args.out or REPORT_DIR}")


def _run_races(P: Prepared, positions, as_of: pd.Timestamp, args, out_dir: Path) -> None:
    ds, cfg = P.ds, P.cfg
    bundle = P.bundle(as_of)
    gamma = latest_gamma(args.level)
    prod = _production_maps()
    ds.prepare_course_bias(positions)
    for pos in positions:
        ctx = ds.make_context(int(pos))
        if ctx is None:
            LOGGER.warning("skip %s: fewer than 4 runners with ability scores", ds.races.at[pos, "race_id"])
            continue
        ds.attach_course_bias(ctx, int(pos))
        snap = ds.snapshot(ctx.month_idx)
        result = simulate_race(ctx, bundle, snap, cfg, n_sims=args.sims,
                               perf_level=args.level, seed=args.seed, first_turn_default=ds.first_turn_default)
        date_key = ctx.date.strftime("%Y-%m-%d")
        race_num = int(ds.races.at[pos, "race_num"])
        keys = {h: (date_key, ctx.track, race_num, int(u)) for h, u in zip(ctx.horse_ids, ctx.umaban)}
        names = {h: prod[k]["name"] for h, k in keys.items() if k in prod}
        ranker = {h: prod[k]["ranker_p"] for h, k in keys.items() if k in prod}
        write_race_outputs(result, out_dir, names, ranker, _calibrate(result, gamma))
        top = result.horses.sort_values("win_probability", ascending=False).iloc[0]
        print(f"{ctx.race_id}: n={ctx.n} top umaban={int(top['umaban'])} p={top['win_probability']:.3f} "
              f"win_time={result.race.get('expected_winning_time_sec')} -> {out_dir}")


def cmd_predict(args) -> None:
    cfg = load_config(args.config)
    date = pd.Timestamp(args.date)
    P = prepare(cfg, upcoming_from=date, use_cache=not args.rebuild)
    races = P.ds.races
    window = races[races["is_upcoming"] & (races["date"] >= date) & (races["date"] < date + pd.Timedelta(days=args.days))]
    if args.race_id:
        window = window[window["race_id"] == args.race_id]
    if window.empty:
        print("対象の未開催レースがありません(DBの出馬表更新が必要です)")
        return
    out_dir = Path(args.out or REPORT_DIR / f"predict_{date:%Y%m%d}")
    _run_races(P, window.index, date, args, out_dir)


def cmd_simulate(args) -> None:
    cfg = load_config(args.config)
    P = prepare(cfg, use_cache=not args.rebuild)
    pos = P.ds.race_pos(args.race_id)
    race_date = P.ds.races.at[pos, "date"]
    as_of = race_date.to_period("M").to_timestamp()  # 月初時点の情報だけで学習
    out_dir = Path(args.out or REPORT_DIR / "simulate")
    _run_races(P, [pos], as_of, args, out_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raceverse", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--rebuild", action="store_true", help="キャッシュを使わず再構築")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    b = sub.add_parser("backtest")
    b.add_argument("--sims", type=int, default=None)
    b.add_argument("--start", default=None)
    b.add_argument("--end", default=None)
    b.add_argument("--levels", default=None,
                   help="base,formation,pace,full,formation_bias,pace_bias (既定: base,formation,pace,full)")
    b.add_argument("--max-races-per-month", type=int, default=None)
    b.add_argument("--seed", type=int, default=None)
    b.add_argument("--out", type=Path, default=None)
    for name in ("predict", "simulate"):
        p = sub.add_parser(name)
        p.add_argument("--sims", type=int, default=10_000)
        p.add_argument("--seed", type=int, default=None)
        p.add_argument("--level", default="formation", choices=["formation", "pace", "formation_bias", "pace_bias"])
        p.add_argument("--out", type=Path, default=None)
        if name == "predict":
            p.add_argument("--date", required=True)
            p.add_argument("--days", type=int, default=2)
        p.add_argument("--race-id", default=None, required=(name == "simulate"))
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = build_parser().parse_args()
    {"prepare": cmd_prepare, "backtest": cmd_backtest, "predict": cmd_predict, "simulate": cmd_simulate}[args.command](args)


if __name__ == "__main__":
    main()

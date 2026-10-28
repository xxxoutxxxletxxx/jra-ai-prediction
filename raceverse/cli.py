"""RACEVERSE CLI。

  python -m raceverse.cli prepare                       # データ読込・基準・学習ストアのキャッシュ作成
  python -m raceverse.cli backtest --sims 10000         # 独立Walk-Forwardバックテスト(既存Rankerと同一期間・同一馬)
  python -m raceverse.cli predict --date 2026-10-10     # 未開催レースの勝率・展開・時計を出力
  python -m raceverse.cli simulate --race-id <id>       # 確定済みレースを当時の情報だけで再現(検証用)
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from raceverse.config import REPORT_DIR, load_config
from raceverse.baselines import fit_current_baseline
from raceverse.evaluation import power_normalize
from raceverse.periods import floor_timestamp
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


def _parse_backtest_levels(value: str) -> list[str]:
    from raceverse.backtest import validate_levels

    try:
        return validate_levels([level.strip() for level in value.split(",")])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


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
    levels = args.levels if args.levels is not None else LEVELS
    summary = run_backtest(P, out_dir=args.out, n_sims=args.sims, levels=levels,
                           max_races_per_month=args.max_races_per_month, test_start=args.start, test_end=args.end)
    print(f"done in {summary['runtime_sec']:.0f}s -> {args.out or REPORT_DIR}")


GOING_SCENARIOS = (1, 2, 3, 4)
GOING_LABELS = {1: "good", 2: "yielding", 3: "soft", 4: "heavy"}


def _run_races(P: Prepared, positions, as_of: pd.Timestamp, args, out_dir: Path,
               going_scenarios: bool = False) -> None:
    ds, cfg = P.ds, P.cfg
    bundle = P.bundle(as_of)
    gamma = latest_gamma(args.level)
    prod = _production_maps()
    baseline_models = {}
    ds.prepare_course_bias(positions)
    for pos in positions:
        scenarios = GOING_SCENARIOS if going_scenarios else (None,)
        for going in scenarios:
            ctx = ds.make_context(int(pos), going_override=going, require_ability=not going_scenarios)
            if ctx is None:
                LOGGER.warning("skip %s: fewer than 4 runners with ability scores", ds.races.at[pos, "race_id"])
                break
            file_suffix = ""
            if going is not None:
                race_row = ds.races.iloc[int(pos)].copy()
                race_row["going"] = going
                for target in ("win_time_sec", "early_split_sec"):
                    if target not in baseline_models:
                        baseline_models[target] = fit_current_baseline(ds.races, target, as_of, cfg.baseline_alpha)
                    prediction = baseline_models[target].predict(race_row.to_frame().T)[0]
                    setattr(ctx, "win_time_base" if target == "win_time_sec" else "early_ref", float(prediction))
                file_suffix = f"_going-{going}"
            ds.attach_course_bias(ctx, int(pos), going)
            snap = ds.snapshot(ctx.month_idx)
            result = simulate_race(ctx, bundle, snap, cfg, n_sims=args.sims,
                                   perf_level=args.level, seed=args.seed, first_turn_default=ds.first_turn_default)
            result.race["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            confirmed_dates = ds.races.loc[~ds.races["is_upcoming"], "date"]
            result.race["training_data_through"] = confirmed_dates.max().strftime("%Y-%m-%d")
            if gamma is not None:
                result.race["calibration_gamma"] = gamma
            if going is not None:
                result.race["going_scenario"] = going
                result.race["going_scenario_label"] = GOING_LABELS[going]
            date_key = ctx.date.strftime("%Y-%m-%d")
            race_num = int(ds.races.at[pos, "race_num"])
            keys = {h: (date_key, ctx.track, race_num, int(u)) for h, u in zip(ctx.horse_ids, ctx.umaban)}
            names = {h: prod[k]["name"] for h, k in keys.items() if k in prod}
            runner_rows = ds.runs.iloc[ds.run_slices[ctx.race_id]]
            runner_names = runner_rows.set_index("horse_id")["horse_name"].to_dict()
            names.update({horse_id: runner_names[horse_id] for horse_id in ctx.horse_ids
                          if horse_id not in names and runner_names.get(horse_id)})
            ranker = {h: prod[k]["ranker_p"] for h, k in keys.items() if k in prod}
            calibrated = _calibrate(result, gamma)
            write_race_outputs(result, out_dir, names, ranker, calibrated, file_suffix)
            top = result.horses.sort_values("win_probability", ascending=False).iloc[0]
            print(f"{ctx.race_id} going={ctx.going}: n={ctx.n} top umaban={int(top['umaban'])} "
                  f"p={top['win_probability']:.3f} win_time={result.race.get('expected_winning_time_sec')} -> {out_dir}")


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
    _run_races(P, window.index, date, args, out_dir, args.going_scenarios)


def cmd_simulate(args) -> None:
    cfg = load_config(args.config)
    P = prepare(cfg, use_cache=not args.rebuild)
    pos = P.ds.race_pos(args.race_id)
    race_date = P.ds.races.at[pos, "date"]
    as_of = floor_timestamp(race_date, P.cfg.refit_unit)  # 月初(週次設定なら週の月曜)時点の情報だけで学習
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
    b.add_argument("--levels", type=_parse_backtest_levels, default=None,
                   help="base,formation,pace,formation_bias,pace_bias (既定: base,formation,pace)")
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
            p.add_argument("--going-scenarios", action="store_true",
                           help="未開催レースを良・稍重・重・不良の4条件で独立予測")
        p.add_argument("--race-id", default=None, required=(name == "simulate"))
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = build_parser().parse_args()
    {"prepare": cmd_prepare, "backtest": cmd_backtest, "predict": cmd_predict, "simulate": cmd_simulate}[args.command](args)


if __name__ == "__main__":
    main()

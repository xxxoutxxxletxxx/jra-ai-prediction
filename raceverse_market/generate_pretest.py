"""評価期間より前(2024-09〜2025-08)のWalk-Forward予測を生成する。

M1/M2の補正器は「評価月より前の予測結果」だけで学習するため、評価期間(2025-09〜)より前の
予測が必要になる。既存の raceverse.backtest の関数をそのまま呼び出し、モデル・設定は変更しない。
(既存Rankerとの結合は評価期間外のため行わない。払戻・オッズはDBから別途取得する。)

  PYTHONPATH=. .venv/bin/python -m raceverse_market.generate_pretest
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import pandas as pd

from raceverse.backtest import calibrate_walk_forward, simulate_period
from raceverse.config import load_config
from raceverse.pipeline import prepare
from raceverse_market import PRETEST_DIR

LOGGER = logging.getLogger("raceverse_market.pretest")
LEVELS = ["base", "formation", "pace"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2024-09-01")
    parser.add_argument("--end", default="2025-09-01")
    parser.add_argument("--sims", type=int, default=None)
    parser.add_argument("--out", type=Path, default=PRETEST_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    cfg = load_config(None)
    n_sims = args.sims or cfg.backtest.n_simulations
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    burn_start = start - pd.DateOffset(months=cfg.calibration.burn_in_months)
    P = prepare(cfg, use_cache=True)
    t0 = time.time()
    horses, _ = simulate_period(P, burn_start, end, n_sims, LEVELS)
    horses, gammas = calibrate_walk_forward(horses, cfg.calibration.window_months, cfg.calibration.gamma_grid)
    args.out.mkdir(parents=True, exist_ok=True)
    gammas.to_csv(args.out / "calibration_gammas.csv", index=False)
    horses.to_csv(args.out / "predictions_with_burnin.csv", index=False)
    horses[horses["date"] >= start].to_csv(args.out / "predictions.csv", index=False)
    LOGGER.info("pretest predictions: %d rows (%.0fs) -> %s", len(horses), time.time() - t0, args.out)


if __name__ == "__main__":
    main()

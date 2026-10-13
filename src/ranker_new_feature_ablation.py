"""Run the pre-registered 16-configuration Ranker experiment.

The runner delegates fitting, calibration and monthly walk-forward semantics to
the existing Ranker implementation.  It does not alter the production feature
list or production model files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import ranker_walk_forward_backtest as wf
from .ranker_new_feature_groups import (
    BASELINE_FEATURES,
    configurations,
    feature_quality_summary,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "reports" / "ranker_new_feature_ablation"


def write_catalog(frame: pd.DataFrame, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    catalog = validate_catalog(frame.columns)
    (output / "catalog_validation.json").write_text(
        __import__("json").dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    feature_quality_summary(frame).to_csv(output / "feature_quality.csv", index=False)


def run(start: str, end: str, output: Path, calibration_months: int) -> pd.DataFrame:
    start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
    wf.TEST_END = end_date
    all_features = tuple(
        feature for config in configurations() for feature in config.features
    )
    frame, _ = wf.load_frame(list(dict.fromkeys(all_features)))
    evaluation = frame[(frame["date"] >= start_date) & (frame["date"] < end_date)]
    if evaluation.empty:
        raise RuntimeError("No evaluation rows were loaded for the requested period.")
    write_catalog(frame, output)
    months = wf.month_starts(start_date, end_date)
    rows = []
    for config in configurations():
        predictions, logs = wf.monthly_walk_forward(
            frame,
            list(config.features),
            months,
            calibration_months,
        )
        summary = wf.metrics(predictions)
        winner_rows = predictions[predictions["target"] == 1]
        summary["winner_logloss"] = float(
            (-np.log(np.clip(winner_rows["ranker_win_probability"], 1e-6, 1.0))).mean()
        )
        summary.update({
            "configuration": config.index,
            "mask": config.mask,
            "enabled_groups": "+".join(config.enabled_groups) or "Baseline",
            "features": len(config.features),
            "months": len(logs),
        })
        rows.append(summary)
        predictions.to_csv(output / f"predictions_{config.index:02d}_{config.mask}.csv", index=False)
        pd.DataFrame(logs).to_csv(output / f"monthly_{config.index:02d}_{config.mask}.csv", index=False)
    result = pd.DataFrame(rows).sort_values("configuration")
    result.to_csv(output / "configuration_results.csv", index=False)
    markdown = result.to_markdown(index=False) if _has_tabulate() else pipe_markdown(result)
    (output / "configuration_results.md").write_text(
        markdown + "\n",
        encoding="utf-8",
    )
    return result


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
    except ImportError:
        return False
    return True


def pipe_markdown(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(str(column) for column in frame.columns) + " |"
    separator = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *body])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the four new Ranker feature groups")
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--end", default="2026-10-01")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--calibration-months", type=int, default=wf.CALIBRATION_MONTHS)
    args = parser.parse_args()
    result = run(args.start, args.end, args.out, args.calibration_months)
    print(result[["configuration", "mask", "enabled_groups", "logloss", "brier", "top1_hit_rate"]].to_string(index=False))


if __name__ == "__main__":
    main()

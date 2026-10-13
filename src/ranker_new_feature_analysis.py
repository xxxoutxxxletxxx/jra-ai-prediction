"""Summarise completed four-group Ranker ablation outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .ranker_new_feature_groups import GROUP_KEYS


def markdown(frame: pd.DataFrame) -> str:
    try:
        return frame.to_markdown(index=False)
    except ImportError:
        return frame.to_string(index=False)


def load_results(directory: Path) -> pd.DataFrame:
    return pd.read_csv(
        directory / "configuration_results.csv",
        dtype={"mask": str},
    ).set_index("configuration")


def marginal_effects(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for position, group in enumerate(GROUP_KEYS):
        bit = 1 << position
        pairs = []
        for index, row in results.iterrows():
            if index & bit:
                counterpart = results.loc[index ^ bit]
                pairs.append({
                    "logloss_delta": row["winner_logloss"] - counterpart["winner_logloss"],
                    "brier_delta": row["brier"] - counterpart["brier"],
                    "top1_delta": row["top1_hit_rate"] - counterpart["top1_hit_rate"],
                })
        values = pd.DataFrame(pairs)
        rows.append({
            "group": group,
            "mean_logloss_delta": values["logloss_delta"].mean(),
            "mean_brier_delta": values["brier_delta"].mean(),
            "mean_top1_delta": values["top1_delta"].mean(),
            "pairs_improved_logloss": int((values["logloss_delta"] < 0).sum()),
            "pairs_worsened_logloss": int((values["logloss_delta"] > 0).sum()),
            "pairs_total": len(values),
        })
    return pd.DataFrame(rows)


def pair_interactions(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for left in range(4):
        for right in range(left + 1, 4):
            bit_left, bit_right = 1 << left, 1 << right
            values = []
            for context in range(16):
                if context & (bit_left | bit_right) == 0:
                    continue
                if context & (bit_left | bit_right) != (bit_left | bit_right):
                    continue
                base = context ^ bit_left ^ bit_right
                left_only = context ^ bit_right
                right_only = context ^ bit_left
                values.append(
                    results.loc[context, "winner_logloss"]
                    - results.loc[left_only, "winner_logloss"]
                    - results.loc[right_only, "winner_logloss"]
                    + results.loc[base, "winner_logloss"]
                )
            rows.append({
                "group_pair": f"{GROUP_KEYS[left]} x {GROUP_KEYS[right]}",
                "mean_logloss_interaction": float(np.mean(values)),
            })
    return pd.DataFrame(rows)


def monthly_effects(directory: Path, results: pd.DataFrame) -> pd.DataFrame:
    monthly = {}
    for index in results.index:
        path = directory / f"predictions_{index:02d}_{results.loc[index, 'mask']}.csv"
        frame = pd.read_csv(path)
        frame["month"] = frame["date"].str[:7]
        frame["winner_logloss"] = np.where(
            frame["target"] == 1,
            -np.log(np.clip(frame["ranker_win_probability"], 1e-6, 1)),
            0.0,
        )
        monthly[index] = frame.groupby("month")["winner_logloss"].sum() / frame.groupby("month")["target"].sum()
    baseline = monthly[0]
    rows = []
    for position, group in enumerate(GROUP_KEYS):
        deltas = []
        for index, values in monthly.items():
            if index & (1 << position):
                common = baseline.index.intersection(values.index)
                deltas.extend((values[common] - monthly[index ^ (1 << position)][common]).tolist())
        rows.append({
            "group": group,
            "months_improved": int(sum(value < 0 for value in deltas)),
            "months_worsened": int(sum(value > 0 for value in deltas)),
            "month_comparisons": len(deltas),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse four-group Ranker ablation outputs")
    parser.add_argument("--dir", type=Path, default=Path("reports/ranker_new_feature_ablation"))
    args = parser.parse_args()
    results = load_results(args.dir)
    outputs = {
        "group_marginal_effects": marginal_effects(results),
        "pair_interactions": pair_interactions(results),
        "monthly_effects": monthly_effects(args.dir, results),
    }
    sections = []
    for name, frame in outputs.items():
        frame.to_csv(args.dir / f"{name}.csv", index=False)
        sections.append(f"## {name}\n\n{markdown(frame)}")
    (args.dir / "analysis.md").write_text(
        "# Ranker new feature group analysis\n\n" + "\n\n".join(sections) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

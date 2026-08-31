#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import (  # noqa: E402
    DEFAULT_DB,
    build_v1_features,
    history_class_score,
    history_policy_allows,
    load_data,
    race_id,
)

HORSE_ID = "2019106416"
TARGET_RACE_ID = "2026-0704-02-01-07-09"
POLICIES = ("baseline", "filter-a", "filter-b")


def main() -> None:
    data, _, _ = load_data(DEFAULT_DB)
    horse_rows = [row for row in data if str(row.get("KettoNum")) == HORSE_ID]
    target_rows = [row for row in data if race_id(row) == TARGET_RACE_ID]
    reduced = horse_rows + [row for row in target_rows if str(row.get("KettoNum")) != HORSE_ID]
    source_summary = []
    for row in sorted(horse_rows, key=lambda item: item["date"]):
        score = history_class_score(row)
        allowed = {policy: history_policy_allows(row, policy) for policy in POLICIES}
        if score == 0:
            assert not allowed["filter-a"] and not allowed["filter-b"]
        elif score == 1:
            assert allowed["filter-a"] and not allowed["filter-b"]
        elif score >= 2:
            assert allowed["filter-a"] and allowed["filter-b"]
        source_summary.append({"source_race_id": race_id(row), "source_date": row["date"].isoformat(), "score": score, "history_allowed": allowed})
    traces = {}
    for policy in POLICIES:
        trace = {"horse_id": HORSE_ID, "target_race_id": TARGET_RACE_ID, "source": [], "appended": []}
        features = build_v1_features(reduced, history_policy=policy, feature_target_ids={TARGET_RACE_ID}, history_trace=trace)
        trace["feature_row"] = next(row for row in features if row["horse_id"] == HORSE_ID and row["race_id"] == TARGET_RACE_ID)
        traces[policy] = trace
    output = {"horse_id": HORSE_ID, "target_race_id": TARGET_RACE_ID, "source_summary": source_summary, "traces": traces}
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

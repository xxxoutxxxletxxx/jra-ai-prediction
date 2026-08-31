#!/usr/bin/env python3
"""Build the reusable Phase 5 Parquet feature cache."""
from __future__ import annotations

import argparse
import os
import time

from .backtest import build_v1_features, load_data, phase5_profile, write_feature_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 5 feature cache")
    parser.add_argument("--db", default=None)
    parser.add_argument("--model", default="F")
    args = parser.parse_args()
    started = time.perf_counter()
    os.environ["PHASE5_PROFILE"] = "1"
    db_path = args.db or None
    from pathlib import Path
    data, _, _ = load_data(Path(db_path) if db_path else __import__("src.backtest", fromlist=["DEFAULT_DB"]).DEFAULT_DB)
    data = [row for row in data if str(row.get("idJyoCD", "")).zfill(2) in __import__("src.backtest", fromlist=["JYO_NAMES"]).JYO_NAMES]
    phase5_profile(f"cache build input rows={len(data)}")
    rows = build_v1_features(data)
    write_feature_cache(rows, len(data), args.model)
    phase5_profile(f"cache build complete: {time.perf_counter() - started:.2f}s")


if __name__ == "__main__":
    main()

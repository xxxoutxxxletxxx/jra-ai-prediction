# Phase 5 Runtime Profile

## Before cache
- DB load: about 22 seconds
- Course join: about 13 seconds
- History/feature construction: about 330 seconds
- LightGBM: about 65 seconds
- Peak memory: about 8.4-8.9 GB

## Initial cache build
- DB load: 22.43 seconds
- Course join: 13.21 seconds
- History construction: 346.55 seconds
- Cache write included in total: 423.53 seconds
- Feature rows: 706,014
- Columns: 196
- Parquet size: about 100.3 MB, zstd compression
- Peak memory: about 6.8 GB

## Cached 10-race attempt
- DB load and course join still occurred: about 21.6 seconds
- Parquet load: 25.74 seconds
- Cached feature selection: 4.7 seconds
- History regeneration: skipped
- Feature rows selected: 700,543; target races: 10; prediction rows: 110
- LightGBM training: 203.10 seconds
- Total measured process: about 238 seconds
- Peak memory: about 9.2 GB

## Findings
- No N+1 SQLite query was found.
- Course CSV is loaded once into a dictionary.
- The cache removes the approximately 330-second history reconstruction, but current cached backtest still converts the entire Parquet table to `list[dict]` and trains on about 700k rows. This preserves compatibility but defeats the memory reduction goal.
- 50/432 cached timings were not run because the 10-race run showed the remaining bottleneck is model matrix construction/training, not feature generation. Further work should keep the cache as a pandas/Arrow table and avoid `to_dict('records')`, then separate training-window selection from target-race selection.

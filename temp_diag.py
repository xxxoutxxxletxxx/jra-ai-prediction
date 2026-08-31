import sys
from datetime import date
import pandas as pd
from src.backtest import load_data, limit_evaluation_races, build_v1_features, JYO_NAMES, race_id, DEFAULT_DB

data, pays, source = load_data(DEFAULT_DB)
data = [row for row in data if str(row.get('idJyoCD', '')).zfill(2) in JYO_NAMES]
start = date(2026, 7, 1)
end = date(2026, 9, 1)
limited = limit_evaluation_races(data, start, end, 10)
target_ids = {race_id(row) for row in limited if start <= row['date'] < end}

feat_baseline = pd.DataFrame(build_v1_features(limited, history_policy='baseline', feature_target_ids=target_ids))
feat_filterb = pd.DataFrame(build_v1_features(limited, history_policy='filter-b', feature_target_ids=target_ids))

merged = pd.merge(feat_baseline, feat_filterb, on=['race_id', 'horse_id'], suffixes=('_base', '_filterb'))

diff_usable_mask = merged['usable_history_count_base'].ne(merged['usable_history_count_filterb'])
diff_margin_mask = merged['last1_margin_base'].ne(merged['last1_margin_filterb'])
diff_mask = diff_usable_mask | diff_margin_mask
diff_rows = merged[diff_mask]

print(f'Total merged rows: {len(merged)}')
print(f'Total rows with differences: {len(diff_rows)}')
print(f'Count of differing usable_history_count: {diff_usable_mask.sum()}')
print(f'Count of differing last1_margin: {diff_margin_mask.sum()}')

print('\nFirst 10 rows where they differ:')
cols = ['race_id', 'horse_id', 'usable_history_count_base', 'usable_history_count_filterb', 'last1_margin_base', 'last1_margin_filterb']
print(diff_rows[cols].head(10).to_string(index=False))

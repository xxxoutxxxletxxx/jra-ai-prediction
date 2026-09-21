#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / 'recent_1month_horse_detail_2026-09-21.csv'
FILES = [
    ROOT / 'reports' / 'ranker_walk_forward_86_features' / 'walk_forward_predictions.csv',
    ROOT / 'output' / 'predictions.csv',
]
START = pd.to_datetime('2026-08-22')
END = pd.to_datetime('2026-09-21')

def read_csv_flexible(path):
    if not path.exists():
        return None
    df = pd.read_csv(path)
    # normalize column names
    df.columns = [c.strip() for c in df.columns]
    colmap = {c.lower(): c for c in df.columns}
    def g(col_candidates):
        for c in col_candidates:
            if c in colmap:
                return colmap[c]
        return None
    # possible names
    col_date = g(['date','race_date'])
    if col_date:
        df['date'] = pd.to_datetime(df[col_date])
    else:
        # try to infer from index or other
        pass
    # mapping
    def get(cands):
        key = g(cands)
        if key:
            return df[key]
        # return a Series of NaNs matching df length so callers can call Series methods
        return pd.Series([np.nan] * len(df), index=df.index)
    df2 = pd.DataFrame()
    df2['date'] = pd.to_datetime(df['date'])
    df2['race_id'] = get(['race_id','idRaceNum','id_race','race'])
    df2['horse_id'] = get(['horse_id','horseid','umaban_id','id'])
    df2['horse_name'] = get(['horse_name','bamei','bamei_jp','name'])
    df2['actual_rank'] = pd.to_numeric(get(['actual_rank','target_actual','actual']), errors='coerce')
    df2['target'] = pd.to_numeric(get(['target','is_win']), errors='coerce')
    df2['odds'] = pd.to_numeric(get(['odds','win_odds','odds_win','win_odds_value']), errors='coerce')
    df2['win_odds'] = pd.to_numeric(get(['win_odds','odds']), errors='coerce')
    df2['popularity'] = pd.to_numeric(get(['popularity','pop']), errors='coerce')
    df2['ranker_win_probability'] = pd.to_numeric(get(['ranker_win_probability','ranker_score','probability']), errors='coerce')
    df2['prediction_rank'] = pd.to_numeric(get(['prediction_rank','rank','pred_rank']), errors='coerce')
    df2['win_payout'] = pd.to_numeric(get(['win_payout','payout','win_return']), errors='coerce').fillna(0)
    df2['place_payout'] = pd.to_numeric(get(['place_payout']), errors='coerce').fillna(0)
    # keep original row for reference
    return df2

parts = []
for f in FILES:
    df = read_csv_flexible(f)
    if df is None:
        continue
    # filter by date range inclusive
    df = df[(df['date'] >= START) & (df['date'] <= END)].copy()
    parts.append(df)

if not parts:
    print('No source files found in expected locations. Exiting.')
    raise SystemExit(1)

df = pd.concat(parts, ignore_index=True, sort=False)
# normalize horse id and name
if df['horse_id'].isna().all():
    df['horse_id'] = df['horse_name'].astype(str)
else:
    df['horse_id'] = df['horse_id'].fillna(df['horse_name']).astype(str)

df['horse_name'] = df['horse_name'].fillna('')

# define bet flag: prediction_rank == 1 and odds is finite
df['bet_placed'] = (df['prediction_rank'] == 1) & df['odds'].notna()

# per-row win_return for bets: use win_payout when bet placed, else 0
df['win_return_if_bet'] = np.where(df['bet_placed'], df['win_payout'], 0.0)

# staked per bet: 100 (yen)
STAKE = 100.0

grp = df.groupby(['horse_id','horse_name'], dropna=False)
# compute per-horse summary via apply for flexible fields
summary = df.groupby(['horse_id','horse_name']).apply(
    lambda g: pd.Series({
        'races': len(g),
        'first_date': g['date'].min(),
        'last_date': g['date'].max(),
        'bets': int(g['bet_placed'].sum()),
        'wins_when_bet': int(((g['prediction_rank']==1) & (g['actual_rank']==1)).sum()),
        'total_staked': float(g['bet_placed'].sum()) * STAKE,
        'total_return': float(g['win_return_if_bet'].sum()),
        'avg_pred_prob': float(g['ranker_win_probability'].mean(skipna=True)) if g['ranker_win_probability'].notna().any() else np.nan,
        'avg_odds': float(g['odds'].mean(skipna=True)) if g['odds'].notna().any() else np.nan,
        'avg_popularity': float(g['popularity'].mean(skipna=True)) if g['popularity'].notna().any() else np.nan,
        'mean_prediction_rank': float(g['prediction_rank'].mean(skipna=True)) if g['prediction_rank'].notna().any() else np.nan,
        'last_race_id': g['race_id'].iloc[-1] if 'race_id' in g and len(g)>0 else None,
        'last_actual_rank': int(g['actual_rank'].iloc[-1]) if g['actual_rank'].notna().any() else np.nan,
    })
)
summary = summary.reset_index()
summary['roi'] = np.where(summary['total_staked']>0, summary['total_return']/summary['total_staked'] - 1.0, np.nan)

OUT.parent.mkdir(parents=True, exist_ok=True)
summary = summary.sort_values(by='total_return', ascending=False)
summary.to_csv(OUT, index=False)
print(f'Wrote {OUT} ({len(summary)} rows)')

#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / 'reports' / 'recent_1month_horse_detail_2026-09-21.csv'
if not IN.exists():
    raise SystemExit(f'missing {IN}')
df = pd.read_csv(IN)
# totals
total_horses = len(df)
total_races = df['races'].sum()
total_bets = df['bets'].sum()
total_staked = df['total_staked'].sum()
total_return = df['total_return'].sum()
overall_roi = (total_return / total_staked - 1.0) if total_staked>0 else float('nan')
# top by total_return
top_return = df.sort_values('total_return', ascending=False).head(10)[['horse_name','races','bets','wins_when_bet','total_staked','total_return','roi']]
# top by roi (require at least 1 bet)
top_roi = df[df['bets']>0].sort_values('roi', ascending=False).head(10)[['horse_name','races','bets','wins_when_bet','total_staked','total_return','roi']]
print('TOTAL_HORSES,', total_horses)
print('TOTAL_RACES,', int(total_races))
print('TOTAL_BETS,', int(total_bets))
print('TOTAL_STAKED,', float(total_staked))
print('TOTAL_RETURN,', float(total_return))
print('OVERALL_ROI,', float(overall_roi))
print('\nTOP_BY_TOTAL_RETURN')
print(top_return.to_csv(index=False))
print('\nTOP_BY_ROI')
print(top_roi.to_csv(index=False))

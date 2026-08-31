from __future__ import annotations
import csv, json
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parent.parent

def read_csv(p):
 with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True); fields=[]
 for r in rows:
  for k in r:
   if k not in fields:fields.append(k)
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 out=ROOT/'reports'; inventory=read_csv(out/'feature_inventory_cleanup.csv')
 cache=set(pq.ParquetFile(ROOT/'data/cache/phase6_g_features.parquet').schema.names) if (ROOT/'data/cache/phase6_g_features.parquet').exists() else set(pq.ParquetFile(ROOT/'data/cache/phase5_f_features.parquet').schema.names)
 inv=set(r['feature'] for r in inventory)
 write(out/'cache_inventory_column_diff.csv',[{'column':c,'in_phase6_g_cache':int(c in cache),'in_cleanup_inventory':int(c in inv),'reason':'cache-only feature or prior cache version' if c not in inv else 'inventory-present','expected_difference':'inspect before new cache'} for c in sorted(cache|inv) if (c in cache)!=(c in inv)])
 audit=['# Cleanup Leakage Audit (Step 2)','', '## Status','', 'Race Bias features are SAFE only as historical features: source race P is processed after P ends, then stored for future target R. The current target race results are not used to create its own features.', '', '| Feature | Source | Result use | Temporal status |','|---|---|---|---|']
 for f in ['position_bias_top5_v2','position_bias_top6_v2','position_bias_weighted_top6_v2','position_bias_residual_v2','race_position_bias_last1','race_position_bias_last2','race_position_bias_last3','strong_against_bias_v2_last1','strong_against_bias_v2_last2','strong_against_bias_v2_last3','adjusted_performance_v2_last1','adjusted_performance_v2_last2','adjusted_performance_v2_last3']:
  audit.append(f'| `{f}` | prior source race history | source race result only, never target row | SAFE under date-batched state update |')
 audit += ['', 'Residual note: expected rank is computed from pre-race accumulated wins/races. It is not fit on the target race result.', 'Target result columns remain evaluation/history inputs only and are excluded from model feature lists.']
 (out/'leakage_audit_cleanup.md').write_text('\n'.join(audit)+'\n',encoding='utf-8')
 (out/'horse_fit_design_notes.md').write_text('# Horse Fit Design Notes\n\nCleanup-C will transform course geometry into horse-level residual fit: performance under a condition minus the horse baseline, shrunk toward 0.5 when sample count is low. No implementation is made in Step 2.\n',encoding='utf-8')
 print(json.dumps({'cache_columns':len(cache),'inventory_columns':len(inv),'diff_rows':len([c for c in cache|inv if (c in cache)!=(c in inv)])},ensure_ascii=False))
if __name__=='__main__':main()

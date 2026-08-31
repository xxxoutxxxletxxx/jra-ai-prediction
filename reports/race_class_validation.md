# Race Class Filter Validation

Prediction source: `reports/backtest_phase5_F_cached_df_432/predictions.csv`
Prediction rows: 5581, races: 432
UNKNOWN: 418 races (96.76%)

## Crosswalk

```csv
normalized_race_class,races,median_first_prize,min_first_prize,max_first_prize,ratio
新馬,,,,,
未勝利,,,,,
1勝,,,,,
2勝,,,,,
3勝,,,,,
OP,,,,,
L,3.0,24000000.0,24000000.0,28000000.0,0.006944444444444444
G3,11.0,41000000.0,34000000.0,43000000.0,0.02546296296296296
G2,,,,,
G1,,,,,
UNKNOWN,418.0,7800000.0,5800000.0,24000000.0,0.9675925925925926
```

Class labels are reconstructed from NL_RA_RACE JyokenName/RaceInfo and GradeCD. UNKNOWN is excluded from A/B and cumulative filters; no class is inferred from prize alone.

## Anomaly review

The prize crosswalk above is the audit surface. Large ranges reflect race-level prize variation and should be reviewed before operationalizing a prize threshold; no automatic relabeling was performed.

# Phase 3 Anchor and Major Gap

- Races: 432
- Anchor strength is an equal mean of percentile(gap_1_2), percentile(top1_share), inverse percentile(entropy), and percentile(p1-minus-field-median).
- Major gap: exploratory top 10 percentile of all adjacent gaps; no production threshold is claimed.
- Anchor rates and ROI are separated: see anchor_percentile_analysis.csv.
- Cluster and multi-gap structure: see race_clusters.csv and major_gaps.csv.
- Anchor to opponent-cluster quinella/exacta flow uses one 100-yen ticket per opponent; stake equals ticket count.
- Wide flow uses NL_HR_PAY PayWide0..6 and accounts for one ticket per opponent.
- No odds are used in Model D or Anchor/Gap features; odds and payouts are research-only.
- All source rows are out-of-sample Model D predictions; no target/result columns are used to form features.

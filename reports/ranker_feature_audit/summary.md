# Ranker Feature Audit

## Scope
- Baseline: monthly Walk-Forward, 2025-09 through 2026-08, first prize above 8,000,000 yen.
- TreeSHAP source: LightGBM `pred_contrib=True`; no production model, feature definition, or purchase rule was changed for this audit.

## Core Finding
- Market-disagreeing Top1 selections are materially overestimated: market-popularity 4-6 Top1 has predicted win probability 20.03% versus actual 8.33%; popularity 7+ has predicted 15.44% versus actual 4.44%.
- EV>=1 losing Top1 cases (418) are most commonly raised by the near-run performance and career groups, especially `weighted_adjusted_performance_last3`, `last1_raw_performance`, `career_win_rate`, `career_races`, and `recent3_place_rate`.
- The same near-run features also lower market favorites when Ranker places them second or lower. This is a miscalibration/relative-weight problem rather than evidence of a result-column leak.

## Top Features
1. `weighted_adjusted_performance_last3`
2. `career_win_rate`
3. `last1_raw_performance`
4. `career_races`
5. `prize_ratio_vs_last3_mean`
6. `weighted_margin_last3`
7. `recent3_place_rate`
8. `last1_adjusted_performance`
9. `mean_adjusted_performance_last3`
10. `prize_change_from_last3_mean`

See `feature_importance_comparison.csv` for the complete top 50 across gain, split, permutation, and TreeSHAP.

## Duplication And Data Quality
- The performance family is strongly redundant: raw versus adjusted recent performance correlations are about 0.999; weighted versus mean margins is 0.963; several margin interactions exceed 0.94.
- Race-prize fields are also nearly duplicate: first, second, and total top-five prize correlations exceed 0.999.
- `prize_change_from_last3_mean` has very large tails (about -366M to +493M yen). It is not missing, but requires scale/semantic review before further use.
- No direct evidence was found that top importance features contain target-race finish, payout, or other post-race columns. Their cached definitions should still be preserved in the leakage review.

## Focused Ablation
- Short August screen selected `prize_ratio_vs_last3_mean` for confirmation: it improved August ROI from 71.73% to 78.67% with Brier 0.06813 to 0.06788.
- Full-year monthly retraining confirmation did not reproduce this gain: baseline ROI 69.73%, removal ROI 69.18%; Brier worsened from 0.064461 to 0.064490; AUC fell from 0.761456 to 0.761172.
- Therefore, no feature is a confirmed deletion candidate from this experiment.

## Audit Classification
- **Strong suspicion / redesign:** the overlapping recent-performance family, especially `weighted_adjusted_performance_last3`, `last1_raw_performance`, `last1_adjusted_performance`, `mean_adjusted_performance_last3`, raw/adjusted prior-race values, weighted/mean margins, and margin interactions. These consistently dominate SHAP and incorrect market disagreement while heavily duplicating one another.
- **Moderate suspicion / verify:** `prize_ratio_vs_last3_mean`, `prize_change_from_last3_mean`, and the highly correlated current prize fields. The isolated prize ratio ablation was not confirmed, so these should be rescaled/consolidated rather than removed blindly.
- **Healthy for now:** `career_win_rate` and `career_races` have high permutation importance and a broadly monotonic calibration relationship. They should not be removed without a separate full-year test.

## Next Step
- Do not optimize purchase filters yet. First create a compact, non-redundant near-run performance representation and retest it against the same 12-month monthly Walk-Forward baseline.
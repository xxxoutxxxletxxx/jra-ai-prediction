# Ranker Dedup Redesign (Raw Margin Removed)

## Change
- Removed 17 features that duplicate `last1-3_adjusted_performance`: raw margin values, `last1-3_raw_performance`, and every `margin_x_*` interaction.
- Everything else (feature set, monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged from `reports/ranker_walk_forward_12m`.

## Full-Year Comparison (2025-09 to 2026-08)
- Baseline (CLEANUP_B, 104 features): Brier 0.064461, LogLoss 0.235329, AUC 0.761456, Top1 24.89%, Top3 55.62%, Top1 Win ROI 69.73%, Top1 profit -49250 yen.
- Dedup (raw margin removed, 87 features): Brier 0.064490, LogLoss 0.235422, AUC 0.761240, Top1 24.65%, Top3 55.19%, Top1 Win ROI 68.25%, Top1 profit -51660 yen.

## Removed Features
- best_margin_last3
- last1_margin
- last1_margin_x_prize_strength
- last1_margin_x_winner_strength_v2
- last1_raw_performance
- last2_margin
- last2_margin_x_prize_strength
- last2_margin_x_winner_strength_v2
- last2_raw_performance
- last3_margin
- last3_margin_x_prize_strength
- last3_margin_x_winner_strength_v2
- last3_raw_performance
- margin_x_field_strength
- margin_x_winner_strength
- mean_margin_last3
- weighted_margin_last3

## Market-Popularity Calibration (Top1 selections only)
| Market group | Variant | Races | Predicted win prob | Actual win rate | Win ROI |
|---|---|---:|---:|---:|---:|
| A_favorite (1st) | baseline | 912 | 27.91% | 34.65% | 77.61% |
| A_favorite (1st) | dedup | 919 | 27.73% | 34.93% | 78.52% |
| B_2_3 | baseline | 514 | 23.21% | 14.40% | 58.11% |
| B_2_3 | dedup | 493 | 23.17% | 13.39% | 53.73% |
| C_4_6 | baseline | 156 | 20.03% | 8.33% | 60.13% |
| C_4_6 | dedup | 169 | 19.75% | 7.10% | 53.08% |
| D_7_plus | baseline | 45 | 15.44% | 4.44% | 76.00% |
| D_7_plus | dedup | 46 | 15.10% | 4.35% | 74.35% |

Removing raw margin did not close the overrating gap for C_4_6/D_7_plus; the predicted-vs-actual gap and ROI for those groups are flat to slightly worse. Only the market favorite group improved marginally.

## Conclusion
- Deduplicating the exact/near-duplicate raw margin signal is a valid design cleanup, but it is not a fix for the longshot overrating problem on its own: full-year Brier, AUC, Top1/Top3, and Top1 win ROI are all flat to slightly worse than the 104-feature baseline, and the C_4_6/D_7_plus miscalibration gap did not shrink.
- This is consistent with the earlier `prize_ratio_vs_last3_mean` ablation: isolated feature removals from this family do not reproduce as full-year improvements. The redundancy itself was not the source of the miscalibration; the remaining `adjusted_performance` family still carries the same information.
- Next step should target the calibration/weighting of `adjusted_performance` and `career_*` for low-popularity horses directly (e.g., isotonic/Platt recalibration conditioned on popularity band, or a monotonic constraint against market odds), rather than further feature removal.

## Outputs
- `dedup_predictions.csv`: per-horse predictions from the dedup variant, same schema as `walk_forward_predictions.csv`.
- `monthly_results.csv`: month-by-month metrics for both variants.
- `comparison.csv`: full-year metrics for both variants.
- `market_disagreement_comparison.csv`: popularity-band predicted-vs-actual comparison for both variants.

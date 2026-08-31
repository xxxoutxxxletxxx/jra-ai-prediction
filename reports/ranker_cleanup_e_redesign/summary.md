# Ranker CLEANUP_E Redesign (Winning Margin + Class-Matched Form)

## Change
- Added 8 feature(s) on top of the career-count-reduced set: winner-vs-runner-up winning margin for last1-3, and last1-3 adjusted_performance restricted to prior races within +/-1 legacy class tier (with sample count).
- Everything else (monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged.

## Full-Year Comparison (2025-09 to 2026-08)
- Baseline (CLEANUP_B, 104 features): Brier 0.064461, AUC 0.761456, Top1 24.89%, Top3 55.62%, Top1 Win ROI 69.73%, profit -49250 yen.
- Dedup (raw margin removed, 87 features): Brier 0.064490, AUC 0.761240, Top1 24.65%, Top3 55.19%, Top1 Win ROI 68.25%, profit -51660 yen.
- No career_win_rate/career_races (85 features): Brier 0.064640, AUC 0.756059, Top1 24.77%, Top3 53.84%, Top1 Win ROI 69.62%, profit -49430 yen.
- CLEANUP_E (winning margin + class-matched form, 93 features): Brier 0.064573, AUC 0.758286, Top1 24.77%, Top3 54.70%, Top1 Win ROI 69.07%, profit -50330 yen.

## Added In This Step
- class_matched_sample_count
- last1_class_matched_adjusted_performance
- last1_winning_margin
- last2_class_matched_adjusted_performance
- last2_winning_margin
- last3_class_matched_adjusted_performance
- last3_winning_margin
- mean_class_matched_adjusted_performance_last3

## Outputs
- `cleanup_e_predictions.csv`: per-horse predictions for the new variant.
- `monthly_results.csv` / `comparison.csv`: month-by-month and full-year metrics for all four variants.
- `market_disagreement_comparison.csv`: popularity-band predicted-vs-actual for all four variants.

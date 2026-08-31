# Ranker Career Win-Rate / Race-Count Redesign

## Change
- Dropped `career_win_rate` and `career_races` on top of the raw-margin dedup (2 feature(s) removed here).
- The categorical class_label (`race_class_label`, `last1-3_race_class`) is now removed from feature generation entirely in `src/backtest.py`; it was already absent from this Ranker feature set, so this run confirms no regression from that removal, not a new ablation.
- Everything else (monthly expanding-window retraining, 3-month prior-only calibration, 8,000,000 yen prize filter, seed) is unchanged.

## Full-Year Comparison (2025-09 to 2026-08)
- Baseline (CLEANUP_B, 104 features): Brier 0.064461, AUC 0.761456, Top1 24.89%, Top3 55.62%, Top1 Win ROI 69.73%, profit -49250 yen.
- Dedup (raw margin removed, 87 features): Brier 0.064490, AUC 0.761240, Top1 24.65%, Top3 55.19%, Top1 Win ROI 68.25%, profit -51660 yen.
- No career_win_rate/career_races (85 features): Brier 0.064640, AUC 0.756059, Top1 24.77%, Top3 53.84%, Top1 Win ROI 69.62%, profit -49430 yen.

## Removed In This Step
- career_races
- career_win_rate

## Outputs
- `reduced_predictions.csv`: per-horse predictions for the new variant.
- `monthly_results.csv` / `comparison.csv`: month-by-month and full-year metrics for all three variants.
- `market_disagreement_comparison.csv`: popularity-band predicted-vs-actual for all three variants.

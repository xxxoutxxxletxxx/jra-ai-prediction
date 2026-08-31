# Monthly Ranker Walk-Forward Backtest

## Design
- Final out-of-sample period: 2025-09-01 to 2026-08-31.
- Monthly expanding-window retraining. Each forecast month uses only target races dated before that month.
- Temperature: a preliminary Ranker trains before the preceding three calibration months; its out-of-time calibration scores select T. The final Ranker then retrains through the month immediately before prediction.
- Low-prize races remain in precomputed historical features but are excluded from Ranker train/evaluation targets.

## Annual Comparison
- Monthly Walk-Forward: Brier 0.064461, LogLoss 0.235329, AUC 0.761456, Top1 24.89%, Top3 55.62%, Top1 ROI 69.73%.
- Fixed: Brier 0.064534, LogLoss 0.235645, AUC 0.761367, Top1 24.77%, Top3 55.07%, Top1 ROI 69.79%.
- Result: monthly retraining gives a small probability/ranking improvement, but does not improve Top1 win ROI in this final year. It is retained as the leakage-safe operational baseline, not as evidence of a profitable purchase rule.

## Outputs
- `walk_forward_predictions.csv` is the standard input for the later purchase-condition search.
- `monthly_training_log.csv` records each month’s train end, sample sizes, calibration window, and fixed temperature.
- `monthly_results.csv` reports fixed and walk-forward metrics by month.

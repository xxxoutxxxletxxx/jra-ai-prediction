# Monthly Ranker Walk-Forward Backtest

## Design
- Final out-of-sample period: 2025-09-01 to 2026-08-31.
- Monthly expanding-window retraining. Each forecast month uses only target races dated before that month.
- Temperature: a preliminary Ranker trains before the preceding three calibration months; its out-of-time calibration scores select T. The final Ranker then retrains through the month immediately before prediction.
- Low-prize races remain in precomputed historical features but are excluded from Ranker train/evaluation targets.

## Annual Comparison
- Monthly Walk-Forward: Brier 0.064431, LogLoss 0.235949, AUC 0.757947, Top1 26.43%, Top3 54.82%, Top1 ROI 80.50%.
- Fixed: Brier 0.064421, LogLoss 0.235776, AUC 0.758629, Top1 26.43%, Top3 55.13%, Top1 ROI 80.21%.
- Result: monthly retraining gives a small probability/ranking improvement, but does not improve Top1 win ROI in this final year. It is retained as the leakage-safe operational baseline, not as evidence of a profitable purchase rule.

## Rule-Based Betting (src/betting_rules.py)
- Rule: odds < 3.0 requires predicted probability >= 0.40; 5.0 <= odds < 20.0 is always bought; everything else is skipped.
- Monthly Walk-Forward: 494 bets, ROI 91.88%, profit -4010 yen (all Top1: ROI 80.50%).
- Fixed: 452 bets, ROI 92.77%, profit -3270 yen (all Top1: ROI 80.21%).

## Outputs
- `walk_forward_predictions.csv` is the standard input for the later purchase-condition search.
- `monthly_training_log.csv` records each month’s train end, sample sizes, calibration window, and fixed temperature.
- `monthly_results.csv` reports fixed and walk-forward metrics by month.

# Monthly Ranker Walk-Forward Backtest

## Design
- Final out-of-sample period: 2025-09-01 to 2026-08-31.
- Monthly expanding-window retraining. Each forecast month uses only target races dated before that month.
- Temperature: a preliminary Ranker trains before the preceding three calibration months; its out-of-time calibration scores select T. The final Ranker then retrains through the month immediately before prediction.
- Low-prize races remain in precomputed historical features but are excluded from Ranker train/evaluation targets.

## Annual Comparison
- Monthly Walk-Forward: Brier 0.064517, LogLoss 0.236261, AUC 0.757262, Top1 25.88%, Top3 54.76%, Top1 ROI 77.08%.
- Fixed: Brier 0.064479, LogLoss 0.236137, AUC 0.757948, Top1 26.22%, Top3 54.81%, Top1 ROI 77.73%.
- Result: monthly retraining gives a small probability/ranking improvement, but does not improve Top1 win ROI in this final year. It is retained as the leakage-safe operational baseline, not as evidence of a profitable purchase rule.

## Rule-Based Betting (src/betting_rules.py)
- Rule: odds < 3.0 requires predicted probability >= 0.40; 5.0 <= odds < 20.0 is always bought; everything else is skipped.
- Monthly Walk-Forward: 549 bets, ROI 86.07%, profit -7650 yen (all Top1: ROI 77.08%).
- Fixed: 562 bets, ROI 85.93%, profit -7910 yen (all Top1: ROI 77.73%).

## Outputs
- `walk_forward_predictions.csv` is the standard input for the later purchase-condition search.
- `monthly_training_log.csv` records each month’s train end, sample sizes, calibration window, and fixed temperature.
- `monthly_results.csv` reports fixed and walk-forward metrics by month.

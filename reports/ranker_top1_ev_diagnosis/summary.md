# Ranker Top1 EV Diagnosis

## Scope
- Fixed input: `reports/ranker_walk_forward_12m/walk_forward_predictions.csv`.
- Exactly one Ranker Top1 horse per race. No model, feature, probability, or purchase logic was changed.
- EV uses `ranker_win_probability * (odds / 10)` and 100-yen win bets only for realized ROI.

## EV Distribution
- minimum: 0.224726
- p10: 0.461356
- p25: 0.592952
- median: 0.776392
- p75: 1.066541
- p90: 1.503967
- maximum: 22.114310
- mean: 0.955526

## Key Results
- Top1 baseline: 1627 bets, hit 24.89%, ROI 69.73%, profit -49250 yen.
- EV >= 1.0: 469 bets (28.83%), hit 10.87%, predicted 24.97%, ROI 58.68%, profit -19380 yen.
- EV >= 1.1: 372 bets, ROI 53.17%, profit -17420 yen.
- EV >= 1.2: 290 bets, ROI 52.97%, profit -13640 yen.
- EV >= 1.3: 234 bets, ROI 48.97%, profit -11940 yen.
- EV >= 1.5: 165 bets, ROI 51.09%, profit -8070 yen.

## Robustness
- EV >= 1.0 had ROI >=100% in only 1/12 months.
- EV >= 1.0 payout sensitivity: all 58.68%, excluding largest one 54.79%, excluding largest three 49.18%.
- Higher EV bands have lower realized win rates despite broadly similar or higher predicted probabilities, indicating overestimated model probability relative to the market-price relationship.

## Conclusion
- Case A applies only when ROI generally rises with EV thresholds, remains supported by sufficient samples, and survives payout sensitivity.
- Observed pattern is not sufficiently monotonic and robust to establish EV as a reliable market-value signal. Return to feature/model evaluation before optimizing purchase thresholds.
- See the monthly and payout-sensitivity files before interpreting any high-ROI tail as a usable condition.

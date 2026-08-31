# Prize Filter A/B Experiment

## Objective
- Compare the effect of excluding target races by first-prize thresholds only.
- Only the first-prize target-race threshold differs between A and B; the model, features, months, and walk-forward procedure are identical.
- Feature history retains all source races. The threshold filters only the fitting and evaluation target races.

## A
- target races: 219
- AUC: 0.7410004879363207
- LogLoss: 0.2507847816701153
- Top1: 0.2694063926940639
- Top3: 0.5981735159817352
- Win ROI: 80.0
- Place ROI: 76.21004566210046
- Profit: -4380.0 / -5210.0

## B
- target races: 99
- AUC: 0.741894224114519
- LogLoss: 0.2493774335049299
- Top1: 0.26262626262626265
- Top3: 0.5656565656565656
- Win ROI: 69.0909090909091
- Place ROI: 76.56565656565657
- Profit: -3060.0 / -2320.0

## A→B additional exclusion (800万円超〜1,140万円以下)
- race_count: 120
- top1_hit_rate: 0.2833333333333333
- top3_hit_rate: 0.575
- win_roi: 86.58333333333333
- place_roi: 75.5
- win_profit: -1610.0
- place_profit: -2940.0

## Recommendation
- Adopt A (exclude races with first prize of 800万円 or less) as the current standard.
- B removed 120 additional races but changed win ROI by -10.91 points and Top3 hit rate by -3.25%.
- The additionally excluded band returned a win ROI of 86.58333333333333, so it is not the principal source of the weaker ROI.
- Both variants remain below 100% ROI. Keep this race filter as A and next test a betting-condition filter using the existing probability, odds, and popularity fields.

## Monthly comparison
| label | month | races | top1_hit_rate | win_roi | place_roi | profit |
|---|---|---:|---:|---:|---:|---:|
| A | 2026-07 | 144 | 0.2569444444444444 | 77.56944444444444 | 76.80555555555556 | -3230.0 |
| A | 2026-08 | 75 | 0.29333333333333333 | 84.66666666666667 | 75.06666666666668 | -1150.0 |
| B | 2026-07 | 64 | 0.25 | 72.1875 | 81.25 | -1780.0 |
| B | 2026-08 | 35 | 0.2857142857142857 | 63.42857142857142 | 68.0 | -1280.0 |

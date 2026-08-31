# Model Rebuild AB Test

評価期間: 2026-08-01 <= date < 2026-09-01

同一の 144 races / 1,860 horses を使用。各モデルは月初以前の履歴だけで学習し、1レース1頭を単勝・複勝100円で評価した。

| Policy | Top1 | Top3 | Win ROI | Place ROI | Win profit | Place profit |
|---|---:|---:|---:|---:|---:|---:|
| A legacy | 23.61% | 55.56% | 67.01% | 83.19% | -4,750 | -2,420 |
| B performance | 18.06% | 54.86% | 54.10% | 74.24% | -6,610 | -3,710 |
| C + prize class | 20.14% | 55.56% | 57.29% | 77.43% | -6,150 | -3,250 |
| D + distance/course fit | 20.14% | 56.25% | 57.57% | 73.89% | -6,110 | -3,760 |
| E + pace fit | 20.83% | 58.33% | 60.21% | 79.58% | -5,730 | -2,940 |
| F + interval/course/track/season fit | 22.22% | 55.56% | 61.18% | 77.43% | -5,590 | -3,250 |
| G + draw/rail fit | 21.53% | 52.78% | 58.40% | 79.86% | -5,990 | -2,900 |
| H + carried-weight fit | 20.14% | 54.17% | 54.03% | 74.31% | -6,620 | -3,700 |
| I full fit set | 20.14% | 54.17% | 54.03% | 74.31% | -6,620 | -3,700 |

## Interpretation

- This is one month and is not sufficient for automatic adoption.
- A remains the strongest reference on this period.
- E has the best Top3 and F has the best win ROI among rebuild policies, but neither beats A.
- H and I are identical in this sample; carried-weight and sample-count additions did not change the ranking.
- The next candidate validation set is E/F over multiple months. I should remain REVIEW rather than replace A.

## Leakage checks

- Target-race finish, margin, and first-corner position are not used to construct target fit values.
- Historical performance is appended only after the race date boundary is crossed.
- `raw_performance` is derived only from non-negative `TimeDiff` margin and has no class, pace, position, jockey, or opponent term.
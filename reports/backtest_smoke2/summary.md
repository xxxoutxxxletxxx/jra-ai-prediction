# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.3967241923172468
- Brier Score: 0.08004127356961369
- ROC-AUC: 0.5637574358199723
- Top1 hit rate: 11.11%
- Top3 hit rate: 33.56%

## Betting Performance
- Win: 432 races, hit 11.11%, ROI 47.0%, profit -22890 yen
- Place: 432 races, hit 28.24%, ROI 69.7%, profit -13110 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|
| 2026-07 | 288 | 12.85% | 48.8% | 75.2% |
| 2026-08 | 144 | 7.64% | 43.5% | 58.6% |
| TOTAL | 432 | 11.11% | 47.0% | 69.7% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / ～1200m: 30 races, win rate 16.67%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 15.38%, win ROI 66.4%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 11.11%, win ROI 23.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 10.00%, win ROI 23.7%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 9.76%, win ROI 37.6%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 9.76%, win ROI 71.5%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 9.76%, win ROI 37.6%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 9.76%, win ROI 71.5%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 10.00%, win ROI 23.7%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 11.11%, win ROI 23.3%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 15.38%, win ROI 66.4%
- 函館 / 芝 / ～1200m: 30 races, win rate 16.67%, win ROI 71.0%

## AI vs Favorite
- Spearman correlation: 0.319565992647285
- AI rank 1, not favorite: 362 bets, win ROI 38.0%, place ROI 65.3%

## Risk
- Win: final profit -22890 yen, max drawdown 27350 yen, max losing streak 38
- Place: final profit -13110 yen, max drawdown 14150 yen, max losing streak 15

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2724 | 0.002811600789901653 | 0.06607929515418502 |
| 5～10% | 970 | 0.0742199344399848 | 0.05567010309278351 |
| 10～20% | 1116 | 0.13509434379782864 | 0.0967741935483871 |
| 20～30% | 480 | 0.23175134975104122 | 0.10416666666666667 |
| 30～40% | 158 | 0.333078582189714 | 0.0949367088607595 |
| 40%以上 | 133 | 0.5619349238898111 | 0.18796992481203006 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

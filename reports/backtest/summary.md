# Backtest Report

## Overall Performance
- Races: 3234
- LogLoss: 0.3920658569388026
- Brier Score: 0.0831814685767507
- ROC-AUC: 0.5637100054079858
- Top1 hit rate: 12.43%
- Top3 hit rate: 32.34%

## Betting Performance
- Win: 3234 races, hit 12.43%, ROI 71.8%, profit -91170 yen
- Place: 3234 races, hit 30.36%, ROI 76.8%, profit -75010 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|
| 2025-09 | 240 | 15.00% | 68.8% | 82.4% |
| 2025-10 | 264 | 15.91% | 72.4% | 89.9% |
| 2025-11 | 312 | 11.22% | 77.7% | 66.9% |
| 2025-12 | 264 | 16.67% | 98.6% | 105.6% |
| 2026-01 | 276 | 9.06% | 47.6% | 101.3% |
| 2026-02 | 282 | 13.48% | 72.0% | 64.8% |
| 2026-03 | 300 | 11.33% | 81.9% | 61.2% |
| 2026-04 | 264 | 10.23% | 74.4% | 51.6% |
| 2026-05 | 336 | 9.23% | 58.4% | 74.0% |
| 2026-06 | 264 | 15.91% | 109.0% | 87.0% |
| 2026-07 | 288 | 12.85% | 48.8% | 75.2% |
| 2026-08 | 144 | 7.64% | 43.5% | 58.6% |
| TOTAL | 3234 | 12.43% | 71.8% | 76.8% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 京都 / 芝 / 2100～2400m: 31 races, win rate 22.58%, win ROI 163.2%
- 阪神 / 芝 / 1700～2000m: 211 races, win rate 21.33%, win ROI 123.9%
- 東京 / 芝 / 2100～2400m: 65 races, win rate 20.00%, win ROI 44.6%
- 中京 / 芝 / ～1200m: 31 races, win rate 19.35%, win ROI 89.0%
- 中京 / 芝 / 1700～2000m: 86 races, win rate 17.44%, win ROI 139.8%
- 函館 / 芝 / ～1200m: 64 races, win rate 17.19%, win ROI 69.4%
- 阪神 / 芝 / 2100～2400m: 30 races, win rate 16.67%, win ROI 57.7%
- 中山 / 芝 / 1300～1600m: 64 races, win rate 15.62%, win ROI 53.6%
- 東京 / 芝 / 1300～1600m: 352 races, win rate 14.49%, win ROI 97.1%
- 東京 / 芝 / 1700～2000m: 105 races, win rate 14.29%, win ROI 134.7%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 阪神 / 芝 / ～1200m: 74 races, win rate 4.05%, win ROI 24.9%
- 福島 / 芝 / ～1200m: 91 races, win rate 5.49%, win ROI 21.2%
- 中山 / 芝 / ～1200m: 155 races, win rate 6.45%, win ROI 23.6%
- 京都 / 芝 / 1300～1600m: 180 races, win rate 6.67%, win ROI 49.4%
- 新潟 / 芝 / 1700～2000m: 92 races, win rate 7.61%, win ROI 30.5%
- 京都 / 芝 / ～1200m: 77 races, win rate 7.79%, win ROI 157.4%
- 札幌 / 芝 / 1700～2000m: 55 races, win rate 9.09%, win ROI 45.6%
- 小倉 / 芝 / 2500m～: 31 races, win rate 9.68%, win ROI 61.3%
- 福島 / 芝 / 1700～2000m: 123 races, win rate 9.76%, win ROI 95.0%
- 函館 / 芝 / 1700～2000m: 70 races, win rate 10.00%, win ROI 18.7%

## AI vs Favorite
- Spearman correlation: 0.3090017475667397
- AI rank 1, not favorite: 2650 bets, win ROI 70.7%, place ROI 75.2%

## Risk
- Win: final profit -91170 yen, max drawdown 94590 yen, max losing streak 41
- Place: final profit -75010 yen, max drawdown 75760 yen, max losing streak 18

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 18737 | 0.003307758619611103 | 0.06265677536425254 |
| 5～10% | 9133 | 0.0710133995154244 | 0.056279426256432716 |
| 10～20% | 8825 | 0.13599104811832585 | 0.07626062322946175 |
| 20～30% | 4319 | 0.23316445108447625 | 0.09701319749942117 |
| 30～40% | 1642 | 0.33419979580100506 | 0.10657734470158343 |
| 40%以上 | 1896 | 0.5887855660358918 | 0.14820675105485231 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

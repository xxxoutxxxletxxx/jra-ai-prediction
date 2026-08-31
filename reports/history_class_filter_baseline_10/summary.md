# Backtest Report

## Overall Performance
- Races: 10
- LogLoss: 0.26655887490999436
- Brier Score: 0.07658455386306923
- ROC-AUC: 0.772
- Top1 hit rate: 20.00%
- Top3 hit rate: 70.00%

## Betting Performance
- Win: 10 races, hit 20.00%, ROI 36.0%, profit -640 yen
- Place: 10 races, hit 60.00%, ROI 69.0%, profit -310 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|
| 2026-07 | 10 | 20.00% | 36.0% | 69.0% |
| TOTAL | 10 | 20.00% | 36.0% | 69.0% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。

## AI vs Favorite
- Spearman correlation: 0.8693956675608052
- AI rank 1, not favorite: 4 bets, win ROI 0.0%, place ROI 0.0%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - F_CACHED: 4件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -640 yen, max drawdown 640 yen, max losing streak 4
- Place: final profit -310 yen, max drawdown 330 yen, max losing streak 2

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 42 | 0.02716034979658048 | 0.023809523809523808 |
| 5～10% | 27 | 0.07455359016985318 | 0.037037037037037035 |
| 10～20% | 26 | 0.1281902636005927 | 0.15384615384615385 |
| 20～30% | 11 | 0.26002204573865423 | 0.2727272727272727 |
| 30～40% | 3 | 0.32837575445504613 | 0.3333333333333333 |
| 40%以上 | 1 | 0.4179584608710803 | 0 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

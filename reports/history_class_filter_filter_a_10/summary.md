# Backtest Report

## Overall Performance
- Races: 10
- LogLoss: 0.293367023210142
- Brier Score: 0.08146512917685284
- ROC-AUC: 0.648
- Top1 hit rate: 10.00%
- Top3 hit rate: 50.00%

## Betting Performance
- Win: 10 races, hit 10.00%, ROI 21.0%, profit -790 yen
- Place: 10 races, hit 60.00%, ROI 106.0%, profit 60 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|
| 2026-07 | 10 | 10.00% | 21.0% | 106.0% |
| TOTAL | 10 | 10.00% | 21.0% | 106.0% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。

## AI vs Favorite
- Spearman correlation: 0.43925343191398236
- AI rank 1, not favorite: 6 bets, win ROI 0.0%, place ROI 98.3%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 6件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -790 yen, max drawdown 790 yen, max losing streak 5
- Place: final profit 60 yen, max drawdown 340 yen, max losing streak 1

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 23 | 0.035282192002990403 | 0.08695652173913043 |
| 5～10% | 50 | 0.07051150559251751 | 0.06 |
| 10～20% | 29 | 0.1312652515125698 | 0.10344827586206896 |
| 20～30% | 7 | 0.24896667509148077 | 0.2857142857142857 |
| 30～40% | 1 | 0.37298304631630674 | 0 |
| 40%以上 | 0 | None | None |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

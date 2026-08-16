# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.24006444672535865
- Brier Score: 0.06606151123956573
- ROC-AUC: 0.7588528516864116
- Top1 hit rate: 27.55%
- Top3 hit rate: 58.80%

## Betting Performance
- Win: 432 races, hit 27.55%, ROI 79.9%, profit -8670 yen
- Place: 432 races, hit 56.02%, ROI 76.7%, profit -10050 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 28.47% | 84.1% | 76.1% |
| 2026-08 | 144 | 25.69% | 71.6% | 78.0% |
| TOTAL | 432 | 27.55% | 79.9% | 76.7% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 36.11%, win ROI 102.2%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 119.2%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 24.39%, win ROI 77.1%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 24.39%, win ROI 77.1%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 119.2%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 36.11%, win ROI 102.2%

## AI vs Favorite
- Spearman correlation: 0.7818097708949363
- AI rank 1, not favorite: 193 bets, win ROI 74.5%, place ROI 65.7%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 193件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -8670 yen, max drawdown 9090 yen, max losing streak 18
- Place: final profit -10050 yen, max drawdown 10280 yen, max losing streak 9

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2365 | 0.025827912437867157 | 0.024101479915433405 |
| 5～10% | 1726 | 0.07276654896208505 | 0.0660486674391657 |
| 10～20% | 1120 | 0.1396341314312588 | 0.14017857142857143 |
| 20～30% | 320 | 0.24038344369164738 | 0.2625 |
| 30～40% | 47 | 0.32756780141978503 | 0.3829787234042553 |
| 40%以上 | 3 | 0.4232657212773242 | 0.6666666666666666 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

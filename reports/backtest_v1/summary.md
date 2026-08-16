# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.24011083545871448
- Brier Score: 0.06607070434418724
- ROC-AUC: 0.7586334635276177
- Top1 hit rate: 28.24%
- Top3 hit rate: 59.03%

## Betting Performance
- Win: 432 races, hit 28.24%, ROI 81.9%, profit -7840 yen
- Place: 432 races, hit 56.02%, ROI 76.5%, profit -10150 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_class, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, last1_class, last2_class, last3_class, current_distance, field_size, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained; internal LightGBM names sanitized
- GradeCD and JyokenInfoSyubetuCD raw codes; official mapping unavailable
| 2026-07 | 288 | 29.17% | 85.9% | 75.2% |
| 2026-08 | 144 | 26.39% | 73.8% | 79.0% |
| TOTAL | 432 | 28.24% | 81.9% | 76.5% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 36.11%, win ROI 102.2%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 30.77%, win ROI 123.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 30.77%, win ROI 123.3%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 36.11%, win ROI 102.2%

## AI vs Favorite
- Spearman correlation: 0.7814862733295416
- AI rank 1, not favorite: 193 bets, win ROI 76.4%, place ROI 64.4%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 193件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -7840 yen, max drawdown 8260 yen, max losing streak 18
- Place: final profit -10150 yen, max drawdown 10380 yen, max losing streak 9

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2366 | 0.02577101206423964 | 0.02324598478444632 |
| 5～10% | 1726 | 0.07273672765929844 | 0.06720741599073002 |
| 10～20% | 1117 | 0.13938756078699088 | 0.1396598030438675 |
| 20～30% | 324 | 0.24034129082715522 | 0.2623456790123457 |
| 30～40% | 45 | 0.32872003171337844 | 0.4 |
| 40%以上 | 3 | 0.42180902155962086 | 0.6666666666666666 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

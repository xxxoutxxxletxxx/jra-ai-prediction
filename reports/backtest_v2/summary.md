# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.2404268600184191
- Brier Score: 0.06614418809009143
- ROC-AUC: 0.757945627701891
- Top1 hit rate: 27.31%
- Top3 hit rate: 57.87%

## Betting Performance
- Win: 432 races, hit 27.31%, ROI 82.4%, profit -7620 yen
- Place: 432 races, hit 55.56%, ROI 77.2%, profit -9850 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, last1_winner_strength_v2, last2_winner_strength_v2, last3_winner_strength_v2, last1_field_strength_v2, last2_field_strength_v2, last3_field_strength_v2, last1_margin_x_winner_strength_v2, last2_margin_x_winner_strength_v2, last3_margin_x_winner_strength_v2, max_winner_strength_last3, mean_winner_strength_last3, weighted_winner_strength_last3, best_strong_opponent_performance_last3, last1_field_max_strength_v2, last2_field_max_strength_v2, last3_field_max_strength_v2, last1_field_top3_mean_strength_v2, last2_field_top3_mean_strength_v2, last3_field_top3_mean_strength_v2, opponent_history_missing_last3, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained; internal LightGBM names sanitized
- GradeCD/JyokenInfoSyubetuCD are retained as raw categories; official mapping unavailable
| 2026-07 | 288 | 27.78% | 86.3% | 76.9% |
| 2026-08 | 144 | 26.39% | 74.5% | 77.8% |
| TOTAL | 432 | 27.31% | 82.4% | 77.2% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 38.89%, win ROI 107.2%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 124.6%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 77.6%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 25.64%, win ROI 100.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 16.67%, win ROI 34.0%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 函館 / 芝 / ～1200m: 30 races, win rate 16.67%, win ROI 34.0%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 54.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 25.64%, win ROI 100.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 77.6%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 124.6%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 38.89%, win ROI 107.2%

## AI vs Favorite
- Spearman correlation: 0.7819305106795755
- AI rank 1, not favorite: 196 bets, win ROI 79.4%, place ROI 65.9%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 196件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -7620 yen, max drawdown 7770 yen, max losing streak 20
- Place: final profit -9850 yen, max drawdown 10080 yen, max losing streak 8

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2363 | 0.02606836311348552 | 0.02496826068556919 |
| 5～10% | 1689 | 0.0719874383995244 | 0.06275902901124926 |
| 10～20% | 1159 | 0.1377204409852485 | 0.14236410698878343 |
| 20～30% | 318 | 0.2404227186591588 | 0.25471698113207547 |
| 30～40% | 47 | 0.32135459060987553 | 0.40425531914893614 |
| 40%以上 | 5 | 0.4336750598262747 | 0.4 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

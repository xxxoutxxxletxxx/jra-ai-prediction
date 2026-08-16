# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.24000424715147728
- Brier Score: 0.06610685681172591
- ROC-AUC: 0.7590623493954238
- Top1 hit rate: 26.39%
- Top3 hit rate: 59.26%

## Betting Performance
- Win: 432 races, hit 26.39%, ROI 74.4%, profit -11040 yen
- Place: 432 races, hit 55.09%, ROI 75.2%, profit -10730 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, last1_winner_strength_v2, last2_winner_strength_v2, last3_winner_strength_v2, last1_field_strength_v2, last2_field_strength_v2, last3_field_strength_v2, last1_margin_x_winner_strength_v2, last2_margin_x_winner_strength_v2, last3_margin_x_winner_strength_v2, max_winner_strength_last3, mean_winner_strength_last3, weighted_winner_strength_last3, best_strong_opponent_performance_last3, last1_field_max_strength_v2, last2_field_max_strength_v2, last3_field_max_strength_v2, last1_field_top3_mean_strength_v2, last2_field_top3_mean_strength_v2, last3_field_top3_mean_strength_v2, opponent_history_missing_last3, last1_winner_max_race_class_before_target, last2_winner_max_race_class_before_target, last3_winner_max_race_class_before_target, last1_winner_best_win_class_before_target, last2_winner_best_win_class_before_target, last3_winner_best_win_class_before_target, last1_winner_max_prize_before_target, last2_winner_max_prize_before_target, last3_winner_max_prize_before_target, last1_winner_mean_prize_before_target, last2_winner_mean_prize_before_target, last3_winner_mean_prize_before_target, race_class_label, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class, race_sex_condition, race_age_condition, is_filly_mare_only, is_2yo_only, is_3yo_only, last1_sex_condition, last2_sex_condition, last3_sex_condition, last1_is_filly_mare_only, last2_is_filly_mare_only, last3_is_filly_mare_only, last1_age_condition, last2_age_condition, last3_age_condition, race_class_change, female_only_to_open, open_to_female_only, age_condition_change, race_first_prize, race_second_prize, race_third_prize, race_total_top5_prize, race_first_prize_log, race_total_top5_prize_log, last1_race_first_prize, last2_race_first_prize, last3_race_first_prize, last1_race_first_prize_log, last2_race_first_prize_log, last3_race_first_prize_log, max_race_prize_last3, mean_race_prize_last3, weighted_race_prize_last3, prize_change_from_last1, prize_change_from_last3_mean, prize_ratio_vs_last1, prize_ratio_vs_last3_mean, last1_margin_x_prize_strength, last2_margin_x_prize_strength, last3_margin_x_prize_strength, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 25.69% | 72.5% | 73.7% |
| 2026-08 | 144 | 27.78% | 78.4% | 78.1% |
| TOTAL | 432 | 26.39% | 74.4% | 75.2% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 38.89%, win ROI 112.2%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 25.64%, win ROI 100.3%
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 44.7%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 56.7%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 44.7%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 20.00%, win ROI 56.7%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 25.64%, win ROI 100.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 38.89%, win ROI 112.2%

## AI vs Favorite
- Spearman correlation: 0.7873564281149368
- AI rank 1, not favorite: 197 bets, win ROI 62.5%, place ROI 60.2%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 197件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -11040 yen, max drawdown 11040 yen, max losing streak 20
- Place: final profit -10730 yen, max drawdown 10960 yen, max losing streak 8

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2446 | 0.02611221472300617 | 0.02330335241210139 |
| 5～10% | 1691 | 0.07243730227047032 | 0.06918982850384388 |
| 10～20% | 1045 | 0.1404688922122098 | 0.1444976076555024 |
| 20～30% | 336 | 0.241965052103929 | 0.23809523809523808 |
| 30～40% | 59 | 0.33246036192228656 | 0.4406779661016949 |
| 40%以上 | 4 | 0.4232212652034347 | 0.25 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

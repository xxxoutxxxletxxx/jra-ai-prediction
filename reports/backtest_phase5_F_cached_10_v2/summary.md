# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.2391761258219967
- Brier Score: 0.06598216521355046
- ROC-AUC: 0.7626206634873366
- Top1 hit rate: 24.54%
- Top3 hit rate: 58.56%

## Betting Performance
- Win: 432 races, hit 24.54%, ROI 68.8%, profit -13470 yen
- Place: 432 races, hit 55.56%, ROI 80.6%, profit -8370 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, last1_winner_strength_v2, last2_winner_strength_v2, last3_winner_strength_v2, last1_field_strength_v2, last2_field_strength_v2, last3_field_strength_v2, last1_margin_x_winner_strength_v2, last2_margin_x_winner_strength_v2, last3_margin_x_winner_strength_v2, max_winner_strength_last3, mean_winner_strength_last3, weighted_winner_strength_last3, best_strong_opponent_performance_last3, last1_field_max_strength_v2, last2_field_max_strength_v2, last3_field_max_strength_v2, last1_field_top3_mean_strength_v2, last2_field_top3_mean_strength_v2, last3_field_top3_mean_strength_v2, opponent_history_missing_last3, last1_winner_max_race_class_before_target, last2_winner_max_race_class_before_target, last3_winner_max_race_class_before_target, last1_winner_best_win_class_before_target, last2_winner_best_win_class_before_target, last3_winner_best_win_class_before_target, last1_winner_max_prize_before_target, last2_winner_max_prize_before_target, last3_winner_max_prize_before_target, last1_winner_mean_prize_before_target, last2_winner_mean_prize_before_target, last3_winner_mean_prize_before_target, last1_raw_performance, last2_raw_performance, last3_raw_performance, last1_position_advantage, last2_position_advantage, last3_position_advantage, last1_adjusted_performance, last2_adjusted_performance, last3_adjusted_performance, best_adjusted_performance_last3, mean_adjusted_performance_last3, weighted_adjusted_performance_last3, hidden_strength_last1, hidden_strength_last2, hidden_strength_last3, max_hidden_strength_last3, max_strong_against_bias_last3, strong_against_bias_last1, strong_against_bias_last2, strong_against_bias_last3, race_position_bias_last1, race_position_bias_last2, race_position_bias_last3, setup_improvement, hidden_strength_x_race_strength, course_first_corner_distance_m, course_elevation_difference_m, course_final_straight_m, course_start_uphill, course_start_downhill, course_final_uphill, course_final_downhill, course_final_steep_hill, course_rolling_terrain, course_mostly_flat, course_gentle_corners, course_tight_corners, course_up_down_transition_sentence_count, course_geometry_fit, horse_expected_position, position_stability, frontness_mean, frontness_std, front_density, forward_density, mid_density, rear_density, expected_front_count, expected_position_mean, expected_position_std, gate_position_pct, gate_x_expected_position, race_class_label, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class, race_sex_condition, race_age_condition, is_filly_mare_only, is_2yo_only, is_3yo_only, last1_sex_condition, last2_sex_condition, last3_sex_condition, last1_is_filly_mare_only, last2_is_filly_mare_only, last3_is_filly_mare_only, last1_age_condition, last2_age_condition, last3_age_condition, race_class_change, female_only_to_open, open_to_female_only, age_condition_change, race_first_prize, race_second_prize, race_third_prize, race_total_top5_prize, race_first_prize_log, race_total_top5_prize_log, last1_race_first_prize, last2_race_first_prize, last3_race_first_prize, last1_race_first_prize_log, last2_race_first_prize_log, last3_race_first_prize_log, max_race_prize_last3, mean_race_prize_last3, weighted_race_prize_last3, prize_change_from_last1, prize_change_from_last3_mean, prize_ratio_vs_last1, prize_ratio_vs_last3_mean, last1_margin_x_prize_strength, last2_margin_x_prize_strength, last3_margin_x_prize_strength, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 22.57% | 66.1% | 78.7% |
| 2026-08 | 144 | 28.47% | 74.2% | 84.5% |
| TOTAL | 432 | 24.54% | 68.8% | 80.6% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 27.78%, win ROI 88.6%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 72.4%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 73.4%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 53.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 23.33%, win ROI 73.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 20.51%, win ROI 68.7%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 20.51%, win ROI 68.7%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 53.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 23.33%, win ROI 73.0%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 72.4%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 73.4%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 27.78%, win ROI 88.6%

## AI vs Favorite
- Spearman correlation: 0.7924958743680541
- AI rank 1, not favorite: 198 bets, win ROI 55.8%, place ROI 74.5%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 198件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -13470 yen, max drawdown 13480 yen, max losing streak 17
- Place: final profit -8370 yen, max drawdown 8600 yen, max losing streak 6

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2412 | 0.025623440184476046 | 0.02155887230514096 |
| 5～10% | 1634 | 0.07190594293632044 | 0.06487148102815178 |
| 10～20% | 1123 | 0.13761103466353905 | 0.15048975957257346 |
| 20～30% | 336 | 0.24076366348142397 | 0.23511904761904762 |
| 30～40% | 69 | 0.3293996245972761 | 0.34782608695652173 |
| 40%以上 | 7 | 0.42644866271727866 | 0.2857142857142857 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

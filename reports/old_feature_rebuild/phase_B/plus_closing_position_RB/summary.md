# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.23968461235176408
- Brier Score: 0.06594931525005612
- ROC-AUC: 0.7599021384950692
- Top1 hit rate: 25.69%
- Top3 hit rate: 57.18%

## Betting Performance
- Win: 432 races, hit 25.69%, ROI 69.3%, profit -13250 yen
- Place: 432 races, hit 54.63%, ROI 80.2%, profit -8540 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, last1_winner_strength_v2, last2_winner_strength_v2, last3_winner_strength_v2, last1_field_strength_v2, last2_field_strength_v2, last3_field_strength_v2, last1_margin_x_winner_strength_v2, last2_margin_x_winner_strength_v2, last3_margin_x_winner_strength_v2, max_winner_strength_last3, mean_winner_strength_last3, weighted_winner_strength_last3, best_strong_opponent_performance_last3, last1_field_max_strength_v2, last2_field_max_strength_v2, last3_field_max_strength_v2, last1_field_top3_mean_strength_v2, last2_field_top3_mean_strength_v2, last3_field_top3_mean_strength_v2, opponent_history_missing_last3, last1_winner_max_race_class_before_target, last2_winner_max_race_class_before_target, last3_winner_max_race_class_before_target, last1_winner_best_win_class_before_target, last2_winner_best_win_class_before_target, last3_winner_best_win_class_before_target, last1_winner_max_prize_before_target, last2_winner_max_prize_before_target, last3_winner_max_prize_before_target, last1_winner_mean_prize_before_target, last2_winner_mean_prize_before_target, last3_winner_mean_prize_before_target, last1_raw_performance, last2_raw_performance, last3_raw_performance, last1_position_advantage, last2_position_advantage, last3_position_advantage, last1_adjusted_performance, last2_adjusted_performance, last3_adjusted_performance, best_adjusted_performance_last3, mean_adjusted_performance_last3, weighted_adjusted_performance_last3, hidden_strength_last1, hidden_strength_last2, hidden_strength_last3, max_hidden_strength_last3, max_strong_against_bias_last3, strong_against_bias_last1, strong_against_bias_last2, strong_against_bias_last3, race_position_bias_last1, race_position_bias_last2, race_position_bias_last3, setup_improvement, hidden_strength_x_race_strength, course_first_corner_distance_m, course_elevation_difference_m, course_final_straight_m, course_start_uphill, course_start_downhill, course_final_uphill, course_final_downhill, course_final_steep_hill, course_rolling_terrain, course_mostly_flat, course_gentle_corners, course_tight_corners, course_up_down_transition_sentence_count, course_geometry_fit, horse_expected_position, position_stability, frontness_mean, frontness_std, front_density, forward_density, mid_density, rear_density, expected_front_count, expected_position_mean, expected_position_std, gate_position_pct, gate_x_expected_position, strong_against_bias_v2_last1, strong_against_bias_v2_last2, strong_against_bias_v2_last3, setup_benefit_last1, setup_benefit_last2, setup_benefit_last3, adjusted_performance_v2_last1, adjusted_performance_v2_last2, adjusted_performance_v2_last3, mean_adjusted_performance_v2_last3, best_adjusted_performance_v2_last3, weighted_adjusted_performance_v2_last3, max_strong_against_bias_v2_last3, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, class_change_last1, class_change_last3_mean, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, race_sex_condition, race_age_condition, is_filly_mare_only, is_2yo_only, is_3yo_only, last1_sex_condition, last2_sex_condition, last3_sex_condition, last1_is_filly_mare_only, last2_is_filly_mare_only, last3_is_filly_mare_only, last1_age_condition, last2_age_condition, last3_age_condition, race_class_change, female_only_to_open, open_to_female_only, age_condition_change, race_first_prize, race_second_prize, race_third_prize, race_total_top5_prize, race_first_prize_log, race_total_top5_prize_log, last1_race_first_prize, last2_race_first_prize, last3_race_first_prize, last1_race_first_prize_log, last2_race_first_prize_log, last3_race_first_prize_log, max_race_prize_last3, mean_race_prize_last3, weighted_race_prize_last3, prize_change_from_last1, prize_change_from_last3_mean, prize_ratio_vs_last1, prize_ratio_vs_last3_mean, last1_margin_x_prize_strength, last2_margin_x_prize_strength, last3_margin_x_prize_strength, last1_closing_speed, last2_closing_speed, last3_closing_speed, mean_closing_speed_last3, best_closing_speed_last3, last1_late_frontness, last2_late_frontness, last3_late_frontness, mean_late_frontness_last3, position_closing_power_last1, position_closing_power_last2_mean, position_closing_power_last3_mean, best_position_closing_power_last3
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 25.00% | 71.4% | 79.2% |
| 2026-08 | 144 | 27.08% | 65.2% | 82.4% |
| TOTAL | 432 | 25.69% | 69.3% | 80.2% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 44.44%, win ROI 149.7%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 67.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 24.39%, win ROI 62.7%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 53.3%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 20.51%, win ROI 55.9%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 37.7%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 37.7%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 20.51%, win ROI 55.9%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 53.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 24.39%, win ROI 62.7%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 67.3%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 44.44%, win ROI 149.7%

## AI vs Favorite
- Spearman correlation: 0.7910830242475074
- AI rank 1, not favorite: 196 bets, win ROI 50.6%, place ROI 72.7%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 196件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -13250 yen, max drawdown 13300 yen, max losing streak 16
- Place: final profit -8540 yen, max drawdown 10070 yen, max losing streak 9

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2469 | 0.02587765729376152 | 0.024706358849736737 |
| 5～10% | 1604 | 0.07270536570706443 | 0.06608478802992519 |
| 10～20% | 1090 | 0.13649410607481294 | 0.14311926605504588 |
| 20～30% | 348 | 0.24172991506744138 | 0.22701149425287356 |
| 30～40% | 67 | 0.3366622785012018 | 0.417910447761194 |
| 40%以上 | 3 | 0.41686928050913413 | 0.6666666666666666 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

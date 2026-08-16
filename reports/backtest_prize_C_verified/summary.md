# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.2403773093645921
- Brier Score: 0.06618478734357297
- ROC-AUC: 0.7574196355998648
- Top1 hit rate: 26.62%
- Top3 hit rate: 59.49%

## Betting Performance
- Win: 432 races, hit 26.62%, ROI 75.6%, profit -10530 yen
- Place: 432 races, hit 55.56%, ROI 76.4%, profit -10210 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, race_class_label, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class, race_sex_condition, race_age_condition, is_filly_mare_only, is_2yo_only, is_3yo_only, last1_sex_condition, last2_sex_condition, last3_sex_condition, last1_is_filly_mare_only, last2_is_filly_mare_only, last3_is_filly_mare_only, last1_age_condition, last2_age_condition, last3_age_condition, race_class_change, female_only_to_open, open_to_female_only, age_condition_change, race_first_prize, race_second_prize, race_third_prize, race_total_top5_prize, race_first_prize_log, race_total_top5_prize_log, last1_race_first_prize, last2_race_first_prize, last3_race_first_prize, last1_race_first_prize_log, last2_race_first_prize_log, last3_race_first_prize_log, max_race_prize_last3, mean_race_prize_last3, weighted_race_prize_last3, prize_change_from_last1, prize_change_from_last3_mean, prize_ratio_vs_last1, prize_ratio_vs_last3_mean, last1_margin_x_prize_strength, last2_margin_x_prize_strength, last3_margin_x_prize_strength, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 25.69% | 75.4% | 74.1% |
| 2026-08 | 144 | 28.47% | 76.1% | 81.0% |
| TOTAL | 432 | 26.62% | 75.6% | 76.4% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 30.56%, win ROI 83.6%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 81.5%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 116.4%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 48.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 13.33%, win ROI 22.7%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 13.33%, win ROI 22.7%
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 48.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 85.9%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 116.4%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 81.5%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 30.56%, win ROI 83.6%

## AI vs Favorite
- Spearman correlation: 0.7845914636313289
- AI rank 1, not favorite: 195 bets, win ROI 67.6%, place ROI 64.2%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 195件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -10530 yen, max drawdown 10570 yen, max losing streak 20
- Place: final profit -10210 yen, max drawdown 10440 yen, max losing streak 6

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2460 | 0.025850404891523494 | 0.022764227642276424 |
| 5～10% | 1684 | 0.07300996643738472 | 0.07185273159144893 |
| 10～20% | 1042 | 0.1404498365447538 | 0.14395393474088292 |
| 20～30% | 335 | 0.24008767021438499 | 0.2417910447761194 |
| 30～40% | 57 | 0.3292387913273192 | 0.40350877192982454 |
| 40%以上 | 3 | 0.4242822484527504 | 0.3333333333333333 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

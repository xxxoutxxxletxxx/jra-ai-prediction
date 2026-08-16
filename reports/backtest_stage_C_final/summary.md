# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.23991185256435862
- Brier Score: 0.065995179934954
- ROC-AUC: 0.7589944649446494
- Top1 hit rate: 28.01%
- Top3 hit rate: 59.03%

## Betting Performance
- Win: 432 races, hit 28.01%, ROI 78.3%, profit -9380 yen
- Place: 432 races, hit 56.71%, ROI 77.6%, profit -9670 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, race_class_label, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class, race_sex_condition, race_age_condition, is_filly_mare_only, is_2yo_only, is_3yo_only, last1_sex_condition, last2_sex_condition, last3_sex_condition, last1_is_filly_mare_only, last2_is_filly_mare_only, last3_is_filly_mare_only, last1_age_condition, last2_age_condition, last3_age_condition, race_class_change, female_only_to_open, open_to_female_only, age_condition_change
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 27.78% | 78.4% | 76.2% |
| 2026-08 | 144 | 28.47% | 78.1% | 80.5% |
| TOTAL | 432 | 28.01% | 78.3% | 77.6% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 33.33%, win ROI 83.3%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 92.9%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 107.2%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 39.3%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 39.3%
- 函館 / 芝 / ～1200m: 30 races, win rate 23.33%, win ROI 59.0%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 107.2%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 29.27%, win ROI 92.9%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 33.33%, win ROI 83.3%

## AI vs Favorite
- Spearman correlation: 0.7844743072543794
- AI rank 1, not favorite: 191 bets, win ROI 67.7%, place ROI 64.2%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 191件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -9380 yen, max drawdown 9960 yen, max losing streak 20
- Place: final profit -9670 yen, max drawdown 9900 yen, max losing streak 7

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2377 | 0.025762895832479506 | 0.023559108119478336 |
| 5～10% | 1698 | 0.07237928097142801 | 0.06419316843345112 |
| 10～20% | 1113 | 0.13813075715256 | 0.14375561545372867 |
| 20～30% | 339 | 0.2388339955421262 | 0.24188790560471976 |
| 30～40% | 52 | 0.3292105112269246 | 0.4807692307692308 |
| 40%以上 | 2 | 0.43279047221704914 | 0 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

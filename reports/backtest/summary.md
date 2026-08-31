# Backtest Report

## Overall Performance
- Races: 10
- LogLoss: 0.23566215572534988
- Brier Score: 0.06436243871087946
- ROC-AUC: 0.7386363636363636
- Top1 hit rate: 0.00%
- Top3 hit rate: 20.00%

## Betting Performance
- Win: 10 races, hit 0.00%, ROI 0.0%, profit -1000 yen
- Place: 10 races, hit 30.00%, ROI 39.0%, profit -610 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, racecourse, surface, grade_code, condition_code, last1_class, last2_class, last3_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2024-01 | 10 | 0.00% | 0.0% | 39.0% |
| TOTAL | 10 | 0.00% | 0.0% | 39.0% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。

## AI vs Favorite
- Spearman correlation: 0.6252695461565705
- AI rank 1, not favorite: 6 bets, win ROI 0.0%, place ROI 23.3%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 6件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -1000 yen, max drawdown 1000 yen, max losing streak 10
- Place: final profit -610 yen, max drawdown 640 yen, max losing streak 4

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 50 | 0.02255773702193743 | 0 |
| 5～10% | 56 | 0.0622842277302794 | 0.10714285714285714 |
| 10～20% | 25 | 0.14226085187502382 | 0.12 |
| 20～30% | 10 | 0.2217703618010178 | 0.1 |
| 30～40% | 1 | 0.30304305412149246 | 0 |
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

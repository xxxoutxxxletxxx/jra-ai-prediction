# Backtest Report

## Overall Performance
- Races: 432
- LogLoss: 0.24017865933840948
- Brier Score: 0.06605739553436155
- ROC-AUC: 0.7580323939204304
- Top1 hit rate: 26.62%
- Top3 hit rate: 58.10%

## Betting Performance
- Win: 432 races, hit 26.62%, ROI 74.6%, profit -10980 yen
- Place: 432 races, hit 56.02%, ROI 76.8%, profit -10010 yen

## Monthly Performance
| Month | Races | Top1 Win Rate | Win ROI | Place ROI |
|---|---:|---:|---:|---:|

## v1 Features
- career_races, career_wins, career_win_rate, career_places, career_place_rate, recent3_win_rate, recent3_place_rate, recent5_win_rate, recent5_place_rate, races_last_180d, races_last_365d, last1_finish, last2_finish, last3_finish, last1_margin, last2_margin, last3_margin, best_margin_last3, mean_margin_last3, weighted_margin_last3, last1_winner_strength, last2_winner_strength, last3_winner_strength, last1_field_strength, last2_field_strength, last3_field_strength, margin_x_winner_strength, margin_x_field_strength, last1_distance, last2_distance, last3_distance, current_distance, field_size, race_class_label, race_class_score, current_race_class_score, last1_race_class_score, last2_race_class_score, last3_race_class_score, max_race_class_last3, mean_race_class_last3, weighted_race_class_last3, last1_margin_x_race_class, last2_margin_x_race_class, last3_margin_x_race_class, last1_race_class, last2_race_class, last3_race_class
- pandas get_dummies; unknown category retained
- JyokenName only; raw unknown codes retained
| 2026-07 | 288 | 26.39% | 74.9% | 75.6% |
| 2026-08 | 144 | 27.08% | 74.0% | 79.2% |
| TOTAL | 432 | 26.62% | 74.6% | 76.8% |

## Strong Conditions
- 30レース以上の条件から、予測1位の勝率上位（因果・統計的有意性は未検定）。
- 函館 / 芝 / 1700～2000m: 36 races, win rate 33.33%, win ROI 87.8%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 31.71%, win ROI 103.7%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 107.2%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 48.3%
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 39.3%

## Weak Conditions
- 30レース以上の条件から、予測1位の勝率下位。
- 新潟 / 芝 / 1700～2000m: 30 races, win rate 16.67%, win ROI 39.3%
- 函館 / 芝 / ～1200m: 30 races, win rate 20.00%, win ROI 48.3%
- 福島 / 芝 / 1700～2000m: 41 races, win rate 26.83%, win ROI 71.0%
- 小倉 / 芝 / 1700～2000m: 39 races, win rate 28.21%, win ROI 107.2%
- 札幌 / 芝 / 1700～2000m: 41 races, win rate 31.71%, win ROI 103.7%
- 函館 / 芝 / 1700～2000m: 36 races, win rate 33.33%, win ROI 87.8%

## AI vs Favorite
- Spearman correlation: 0.7838931699933961
- AI rank 1, not favorite: 194 bets, win ROI 61.2%, place ROI 64.4%
- 理由分類（AI rank 1 かつ popularity >= 2）:
  - V1_LIGHTGBM: 194件
- 判定ルール: 過去勝率（過去勝数 / 過去出走数）が主スコア。履歴なしは 1 / 出走頭数、同率は馬番の小さい順。
- 詳細な根拠は predictions.csv の historical_*、favorite_*、probability_margin_vs_favorite、reason_code、prediction_reason 列を参照。

## Risk
- Win: final profit -10980 yen, max drawdown 10980 yen, max losing streak 20
- Place: final profit -10010 yen, max drawdown 10240 yen, max losing streak 6

## Calibration
| Bin | Predictions | Mean Probability | Actual Win Rate |
|---|---:|---:|---:|
| 0～5% | 2365 | 0.025762205771753706 | 0.022832980972515855 |
| 5～10% | 1679 | 0.07191226282679256 | 0.06730196545562835 |
| 10～20% | 1160 | 0.13777793894069706 | 0.1413793103448276 |
| 20～30% | 331 | 0.24039101291394888 | 0.24169184290030213 |
| 30～40% | 43 | 0.33171121277414445 | 0.46511627906976744 |
| 40%以上 | 3 | 0.43415692994872807 | 0.3333333333333333 |

## Leakage Review
- 過去の確定結果から作った馬別勝率のみ。評価月当日以降の行、同一レース結果、払戻は学習に使用しない。
- DBに保存された値の取得時点は不明。最終オッズ/最終人気の可能性があるため、予測時点の厳密な再現とはみなさない。
- GradeCD/JyokenInfoSyubetuCDの公式対応表がリポジトリ内にないため、v1は生コードをカテゴリ入力し、1勝/2勝/3勝/OP/重賞への断定分類はしていない。
- TimeDiffを着差として使用。ChakusaCDはコードの意味が未確認のため数値化していない。
- 除外した結果・レース後確定列: KakuteiJyuni, NyusenJyuni, Time, TimeDiff, HaronTimeL3, HaronTimeL4, Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c, Honsyokin, Fukasyokin, IJyoCD, ChakusaCD, headDataKubun
- ROIは統計的有意性を示さず、LOW SAMPLE 条件はサンプル不足として解釈すること。

## Output Notes
- Calibration/cumulative profit PNG: not generated (matplotlib unavailable)

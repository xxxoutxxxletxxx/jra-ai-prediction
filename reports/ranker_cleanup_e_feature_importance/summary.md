# CLEANUP_E Feature Importance (model trained on data before 2026-08)

- 学習データ: 226994件（2026-08-01より前の全レース）
- 特徴量数: 93

## Gain上位20特徴量
| 順位 | 特徴量 | Gain比率 | 分岐回数 |
|---:|---|---:|---:|
| 1 | recent3_place_rate | 18.95% | 118 |
| 2 | weighted_adjusted_performance_last3 | 12.79% | 108 |
| 3 | mean_class_matched_adjusted_performance_last3 | 12.20% | 51 |
| 4 | last1_class_matched_adjusted_performance | 8.07% | 30 |
| 5 | prize_ratio_vs_last3_mean | 5.93% | 159 |
| 6 | best_strong_opponent_performance_last3 | 3.99% | 63 |
| 7 | hidden_strength_x_race_strength | 2.93% | 88 |
| 8 | prize_change_from_last3_mean | 2.63% | 104 |
| 9 | last1_adjusted_performance | 2.55% | 80 |
| 10 | last3_field_strength | 2.43% | 59 |
| 11 | last1_winning_margin | 2.06% | 104 |
| 12 | races_last_180d | 2.06% | 94 |
| 13 | last3_field_top3_mean_strength_v2 | 1.57% | 52 |
| 14 | races_last_365d | 1.34% | 67 |
| 15 | prize_ratio_vs_last1 | 1.23% | 63 |
| 16 | hidden_strength_last1 | 1.21% | 57 |
| 17 | last1_winner_strength | 1.17% | 40 |
| 18 | last2_winning_margin | 1.06% | 74 |
| 19 | last2_winner_strength | 0.98% | 31 |
| 20 | last1_distance | 0.91% | 73 |

## 直近30日間の全馬予測
- 期間: 2026-07-10 〜 2026-08-09
- 件数: 2305（184レース）
- 全馬（1位評価だけでなく出走馬すべて）の予測勝率を `last_30_days_all_horses.csv` に出力。

# CLEANUP_E without `recent3_place_rate`

- 除外特徴量: `recent3_place_rate`（CLEANUP_EでGain比率トップ 18.95%）
- 特徴量数: 92（CLEANUP_Eの93から1本減）
- 全体成績: Brier 0.064632, AUC 0.756154, Top1 25.75%, Top3 53.41%, Top1 Win ROI 75.02%

## Gain上位20特徴量（除外後）
| 順位 | 特徴量 | Gain比率 | 分岐回数 |
|---:|---|---:|---:|
| 1 | mean_class_matched_adjusted_performance_last3 | 18.35% | 56 |
| 2 | weighted_adjusted_performance_last3 | 15.57% | 124 |
| 3 | best_strong_opponent_performance_last3 | 11.85% | 96 |
| 4 | last1_class_matched_adjusted_performance | 6.31% | 34 |
| 5 | prize_ratio_vs_last3_mean | 4.64% | 140 |
| 6 | hidden_strength_x_race_strength | 3.90% | 103 |
| 7 | last1_adjusted_performance | 3.00% | 93 |
| 8 | races_last_180d | 2.41% | 119 |
| 9 | prize_change_from_last3_mean | 2.32% | 100 |
| 10 | last1_winning_margin | 2.28% | 108 |
| 11 | last3_field_strength | 1.85% | 41 |
| 12 | prize_ratio_vs_last1 | 1.70% | 80 |
| 13 | races_last_365d | 1.42% | 62 |
| 14 | hidden_strength_last1 | 1.38% | 55 |
| 15 | mean_adjusted_performance_last3 | 1.24% | 43 |
| 16 | last1_distance | 1.17% | 77 |
| 17 | career_places | 1.05% | 71 |
| 18 | last2_winning_margin | 1.02% | 64 |
| 19 | last2_winner_strength | 0.96% | 32 |
| 20 | mean_winner_strength_last3 | 0.96% | 26 |

## 直近30日間の全馬予測（除外後モデル）
- 期間: 2026-07-10 〜 2026-08-09
- 件数: 2305（184レース）
- `last_30_days_all_horses.csv` に全出走馬の予測勝率を出力。

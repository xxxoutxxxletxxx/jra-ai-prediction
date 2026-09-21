# 過去5年Ranker 95特徴量の影響分析

## 結論

- **予想を最も動かす特徴量**は、クラス適合済み近走パフォーマンス、調整済み近走パフォーマンス、対戦相手・レース強度に集中している。
- **的中率への寄与**は、各特徴量を月内でシャッフルしたときのAI本命的中率低下幅で評価した。正値はその特徴量が的中率を押し上げ、負値は当該期間では押し下げた可能性を示す。
- **回収率への影響**は因果推論ではなく、AI本命におけるSHAP寄与上位25%と下位25%の単勝ROI差である。高配当1件に左右されるため、12か月中7か月以上同方向かつROI差10pt以上のみ「傾向あり」とした。
- 対象は2025-09〜2026-08の月次walk-forward、各予測月より前の**直近5年間だけ**で学習、1着賞金800万円超、全95特徴量。評価は1,627レース。
- AI本命の基準成績は的中率 **26.31%**、単勝ROI **80.96%**。したがって、特徴量の改善だけで現状の期待収益がプラスになるとは言えない。

## 予想への影響が大きい特徴量

平均絶対SHAPが大きいほど、その特徴量がRankerスコアを大きく動かしている。

| 予想順位 | 特徴量 | 分類 | 平均絶対SHAP | 本命的中率寄与(pt) |
|---|---|---|---|---|
| 1 | `mean_class_matched_adjusted_performance_last3` | class_matched_performance | 0.1955 | +1.615 |
| 2 | `weighted_adjusted_performance_last3` | performance_aggregate | 0.1428 | +0.667 |
| 3 | `last1_adjusted_performance` | performance | 0.1194 | +1.839 |
| 4 | `last1_class_matched_adjusted_performance` | class_matched_performance | 0.1005 | +1.264 |
| 5 | `best_strong_opponent_performance_last3` | opponent_strength_aggregate | 0.0976 | +0.233 |
| 6 | `hidden_strength_x_race_strength` | interaction | 0.0792 | +0.661 |
| 7 | `last1_field_strength` | field_strength | 0.0748 | +1.016 |
| 8 | `last3_field_strength` | field_strength | 0.0626 | +0.652 |
| 9 | `hidden_strength_last2` | hidden_strength | 0.0404 | +0.710 |
| 10 | `races_last_180d` | activity | 0.0401 | +0.584 |
| 11 | `mean_adjusted_performance_last3` | performance_aggregate | 0.0391 | +0.179 |
| 12 | `max_winning_margin_last5` | winning_margin_aggregate | 0.0368 | -0.253 |
| 13 | `last3_field_strength_v2` | field_strength_v2 | 0.0348 | +0.321 |
| 14 | `last3_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0348 | +1.540 |
| 15 | `mean_winning_margin_last5` | winning_margin_aggregate | 0.0321 | +0.692 |

## 的中精度への影響

### プラス寄与上位

| 予想順位 | 特徴量 | 分類 | 平均絶対SHAP | 本命的中率寄与(pt) |
|---|---|---|---|---|
| 3 | `last1_adjusted_performance` | performance | 0.1194 | +1.839 |
| 1 | `mean_class_matched_adjusted_performance_last3` | class_matched_performance | 0.1955 | +1.615 |
| 14 | `last3_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0348 | +1.540 |
| 4 | `last1_class_matched_adjusted_performance` | class_matched_performance | 0.1005 | +1.264 |
| 7 | `last1_field_strength` | field_strength | 0.0748 | +1.016 |
| 24 | `last1_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0212 | +0.958 |
| 31 | `last2_winner_strength` | opponent_strength | 0.0146 | +0.888 |
| 27 | `last1_winner_strength` | opponent_strength | 0.0180 | +0.719 |
| 9 | `hidden_strength_last2` | hidden_strength | 0.0404 | +0.710 |
| 15 | `mean_winning_margin_last5` | winning_margin_aggregate | 0.0321 | +0.692 |
| 23 | `races_last_365d` | activity | 0.0214 | +0.672 |
| 2 | `weighted_adjusted_performance_last3` | performance_aggregate | 0.1428 | +0.667 |
| 6 | `hidden_strength_x_race_strength` | interaction | 0.0792 | +0.661 |
| 8 | `last3_field_strength` | field_strength | 0.0626 | +0.652 |
| 48 | `race_total_top5_prize` | race_prize | 0.0061 | +0.623 |

### マイナスまたは寄与が確認できない特徴量

負値は、その列を崩した方がAI本命的中率が高かったことを意味する。ただし相関特徴量間で重要度が分散し、月ごとのレース数にも差があるため、単独削除の根拠にはしない。

| 予想順位 | 特徴量 | 分類 | 平均絶対SHAP | 本命的中率寄与(pt) |
|---|---|---|---|---|
| 34 | `prize_change_from_last1` | prize_change | 0.0119 | -0.314 |
| 69 | `last1_winner_mean_prize_before_target` | prize_history | 0.0027 | -0.292 |
| 50 | `race_second_prize` | race_prize | 0.0056 | -0.278 |
| 26 | `last2_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0202 | -0.270 |
| 12 | `max_winning_margin_last5` | winning_margin_aggregate | 0.0368 | -0.253 |
| 75 | `last1_winner_best_win_class_before_target` | class_history | 0.0017 | -0.204 |
| 38 | `max_hidden_strength_last3` | hidden_strength_aggregate | 0.0088 | -0.168 |
| 22 | `prize_ratio_vs_last1` | prize_change | 0.0221 | -0.162 |
| 76 | `max_winner_strength_last3` | opponent_strength_aggregate | 0.0015 | -0.133 |
| 70 | `last2_winner_strength_v2` | opponent_strength_v2 | 0.0027 | -0.133 |

## 回収率への影響

### プラス傾向

| 特徴量 | 高寄与ROI | 低寄与ROI | 差(pt) | プラス月 |
|---|---|---|---|---|
| `last4_winning_margin` | 92.71 | 63.27 | +29.44 | 9/12 |
| `last2_winner_strength` | 96.07 | 71.18 | +24.89 | 7/12 |
| `last2_winner_best_win_class_before_target` | 92.52 | 70.57 | +21.96 | 7/12 |
| `mean_winning_margin_last5` | 85.01 | 65.48 | +19.53 | 9/12 |
| `max_winning_margin_last5` | 83.64 | 65.97 | +17.67 | 8/12 |
| `last2_field_strength` | 90.34 | 74.45 | +15.90 | 8/12 |
| `best_strong_opponent_performance_last3` | 78.57 | 63.86 | +14.72 | 8/12 |
| `last2_field_max_strength_v2` | 86.76 | 74.10 | +12.65 | 8/12 |
| `weighted_winner_strength_last3` | 87.67 | 76.49 | +11.18 | 7/12 |

### マイナス傾向

| 特徴量 | 高寄与ROI | 低寄与ROI | 差(pt) | プラス月 |
|---|---|---|---|---|
| `last3_distance` | 59.21 | 93.73 | -34.52 | 3/12 |
| `race_total_top5_prize` | 69.34 | 103.32 | -33.98 | 5/12 |
| `race_second_prize` | 64.64 | 96.44 | -31.79 | 5/12 |
| `mean_race_prize_last3` | 74.79 | 102.95 | -28.16 | 2/12 |
| `race_third_prize` | 74.82 | 102.68 | -27.86 | 5/12 |
| `last1_race_first_prize` | 77.96 | 103.19 | -25.23 | 2/12 |
| `weighted_race_prize_last3` | 67.74 | 91.11 | -23.37 | 3/12 |
| `hidden_strength_last2` | 69.02 | 92.04 | -23.02 | 4/12 |
| `last2_distance` | 70.20 | 93.05 | -22.85 | 4/12 |
| `last3_winner_strength_v2` | 73.24 | 91.87 | -18.62 | 3/12 |
| `career_wins` | 74.47 | 91.53 | -17.06 | 5/12 |
| `prize_ratio_vs_last3_mean` | 72.75 | 87.79 | -15.04 | 5/12 |
| `last3_class_matched_adjusted_performance` | 77.47 | 91.77 | -14.30 | 4/12 |
| `last2_position_advantage` | 66.95 | 81.18 | -14.23 | 5/12 |
| `mean_winner_strength_last3` | 74.30 | 88.23 | -13.93 | 4/12 |

## 見解

1. 予想影響と収益影響は別物である。SHAP上位でも市場が同じ情報をオッズへ織り込んでいればROIは上がらない。
2. 的中面では本命的中率寄与上位を維持候補とし、負値の特徴量は相関群単位の除去テスト候補とするのが妥当である。Brier差も内部計算し、確率精度との方向が大きく矛盾しないか確認している。
3. ROI差が大きくても月次再現性が弱い特徴量は購入条件に使わない。プラス月数が7/12以上でも、次の12か月で再検証する必要がある。
4. 本分析は同一モデル内の関連性分析であり、特徴量の追加・削除による因果効果は個別ablationのwalk-forward比較でのみ確定できる。

## 95特徴量一覧

| 予想順位 | 特徴量 | 分類 | 平均絶対SHAP | 的中寄与順位 | 本命的中率差(pt) | 的中判定 | ROI差 | プラス月 | ROI判定 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `mean_class_matched_adjusted_performance_last3` | class_matched_performance | 0.1955 | 2 | +1.615 | 改善 | -2.2 | 6 | 混在・不明確 |
| 2 | `weighted_adjusted_performance_last3` | performance_aggregate | 0.1428 | 12 | +0.667 | 改善 | +7.5 | 6 | 混在・不明確 |
| 3 | `last1_adjusted_performance` | performance | 0.1194 | 1 | +1.839 | 改善 | -0.6 | 6 | 混在・不明確 |
| 4 | `last1_class_matched_adjusted_performance` | class_matched_performance | 0.1005 | 4 | +1.264 | 改善 | +4.5 | 10 | 混在・不明確 |
| 5 | `best_strong_opponent_performance_last3` | opponent_strength_aggregate | 0.0976 | 28 | +0.233 | 改善 | +14.7 | 8 | プラス傾向 |
| 6 | `hidden_strength_x_race_strength` | interaction | 0.0792 | 13 | +0.661 | 改善 | -10.9 | 6 | 混在・不明確 |
| 7 | `last1_field_strength` | field_strength | 0.0748 | 5 | +1.016 | 改善 | -5.8 | 8 | 混在・不明確 |
| 8 | `last3_field_strength` | field_strength | 0.0626 | 14 | +0.652 | 改善 | +5.4 | 5 | 混在・不明確 |
| 9 | `hidden_strength_last2` | hidden_strength | 0.0404 | 9 | +0.710 | 改善 | -23.0 | 4 | マイナス傾向 |
| 10 | `races_last_180d` | activity | 0.0401 | 16 | +0.584 | 改善 | -0.4 | 5 | 混在・不明確 |
| 11 | `mean_adjusted_performance_last3` | performance_aggregate | 0.0391 | 35 | +0.179 | 改善 | +3.2 | 7 | 混在・不明確 |
| 12 | `max_winning_margin_last5` | winning_margin_aggregate | 0.0368 | 91 | -0.253 | 悪化/寄与なし | +17.7 | 8 | プラス傾向 |
| 13 | `last3_field_strength_v2` | field_strength_v2 | 0.0348 | 22 | +0.321 | 改善 | +3.6 | 6 | 混在・不明確 |
| 14 | `last3_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0348 | 3 | +1.540 | 改善 | -9.6 | 4 | 混在・不明確 |
| 15 | `mean_winning_margin_last5` | winning_margin_aggregate | 0.0321 | 10 | +0.692 | 改善 | +19.5 | 9 | プラス傾向 |
| 16 | `last2_field_strength_v2` | field_strength_v2 | 0.0303 | 72 | -0.048 | 悪化/寄与なし | -7.8 | 5 | 混在・不明確 |
| 17 | `hidden_strength_last1` | hidden_strength | 0.0299 | 84 | -0.109 | 悪化/寄与なし | -9.7 | 5 | 混在・不明確 |
| 18 | `last2_class_matched_adjusted_performance` | class_matched_performance | 0.0289 | 19 | +0.381 | 改善 | +0.9 | 9 | 混在・不明確 |
| 19 | `last2_adjusted_performance` | performance | 0.0274 | 20 | +0.351 | 改善 | +4.8 | 7 | 混在・不明確 |
| 20 | `prize_ratio_vs_last3_mean` | prize_change | 0.0254 | 18 | +0.417 | 改善 | -15.0 | 5 | マイナス傾向 |
| 21 | `career_places` | career | 0.0224 | 27 | +0.233 | 改善 | +4.2 | 8 | 混在・不明確 |
| 22 | `prize_ratio_vs_last1` | prize_change | 0.0221 | 88 | -0.162 | 悪化/寄与なし | +2.7 | 8 | 混在・不明確 |
| 23 | `races_last_365d` | activity | 0.0214 | 11 | +0.672 | 改善 | -4.0 | 4 | 混在・不明確 |
| 24 | `last1_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0212 | 6 | +0.958 | 改善 | -7.7 | 5 | 混在・不明確 |
| 25 | `last2_field_strength` | field_strength | 0.0204 | 32 | +0.211 | 改善 | +15.9 | 8 | プラス傾向 |
| 26 | `last2_field_top3_mean_strength_v2` | field_strength_aggregate | 0.0202 | 92 | -0.270 | 悪化/寄与なし | -3.3 | 6 | 混在・不明確 |
| 27 | `last1_winner_strength` | opponent_strength | 0.0180 | 8 | +0.719 | 改善 | -3.5 | 5 | 混在・不明確 |
| 28 | `recent5_win_rate` | recent_form | 0.0174 | 62 | -0.003 | 悪化/寄与なし | -3.1 | 5 | 混在・不明確 |
| 29 | `prize_change_from_last3_mean` | prize_change | 0.0166 | 41 | +0.060 | 改善 | -9.2 | 5 | 混在・不明確 |
| 30 | `last1_field_strength_v2` | field_strength_v2 | 0.0162 | 31 | +0.220 | 改善 | -4.7 | 5 | 混在・不明確 |
| 31 | `last2_winner_strength` | opponent_strength | 0.0146 | 7 | +0.888 | 改善 | +24.9 | 7 | プラス傾向 |
| 32 | `last1_distance` | distance | 0.0124 | 17 | +0.522 | 改善 | -21.1 | 6 | 混在・不明確 |
| 33 | `best_adjusted_performance_last3` | performance_aggregate | 0.0121 | 82 | -0.096 | 悪化/寄与なし | -0.0 | 7 | 混在・不明確 |
| 34 | `prize_change_from_last1` | prize_change | 0.0119 | 95 | -0.314 | 悪化/寄与なし | -1.2 | 8 | 混在・不明確 |
| 35 | `last2_distance` | distance | 0.0118 | 37 | +0.144 | 改善 | -22.9 | 4 | マイナス傾向 |
| 36 | `last2_position_advantage` | running_style | 0.0106 | 23 | +0.315 | 改善 | -14.2 | 5 | マイナス傾向 |
| 37 | `last2_field_max_strength_v2` | field_strength_aggregate | 0.0092 | 71 | -0.041 | 悪化/寄与なし | +12.7 | 8 | プラス傾向 |
| 38 | `max_hidden_strength_last3` | hidden_strength_aggregate | 0.0088 | 89 | -0.168 | 悪化/寄与なし | -9.4 | 7 | 混在・不明確 |
| 39 | `setup_improvement` | form_change | 0.0085 | 61 | -0.001 | 悪化/寄与なし | +1.7 | 8 | 混在・不明確 |
| 40 | `hidden_strength_last3` | hidden_strength | 0.0082 | 26 | +0.279 | 改善 | +9.2 | 7 | 混在・不明確 |
| 41 | `mean_winner_strength_last3` | opponent_strength_aggregate | 0.0082 | 43 | +0.041 | 改善 | -13.9 | 4 | マイナス傾向 |
| 42 | `last3_winner_strength` | opponent_strength | 0.0075 | 24 | +0.302 | 改善 | -6.6 | 5 | 混在・不明確 |
| 43 | `last3_race_first_prize` | previous_race_prize | 0.0074 | 38 | +0.127 | 改善 | -13.2 | 5 | マイナス傾向 |
| 44 | `last1_field_max_strength_v2` | field_strength_aggregate | 0.0066 | 63 | -0.005 | 悪化/寄与なし | +1.3 | 7 | 混在・不明確 |
| 45 | `last1_winner_strength_v2` | opponent_strength_v2 | 0.0065 | 30 | +0.229 | 改善 | +8.0 | 6 | 混在・不明確 |
| 46 | `last1_position_advantage` | running_style | 0.0063 | 21 | +0.322 | 改善 | -7.2 | 7 | 混在・不明確 |
| 47 | `last3_distance` | distance | 0.0061 | 44 | +0.025 | 改善 | -34.5 | 3 | マイナス傾向 |
| 48 | `race_total_top5_prize` | race_prize | 0.0061 | 15 | +0.623 | 改善 | -34.0 | 5 | マイナス傾向 |
| 49 | `last2_winner_mean_prize_before_target` | prize_history | 0.0059 | 79 | -0.061 | 悪化/寄与なし | +4.6 | 4 | 混在・不明確 |
| 50 | `race_second_prize` | race_prize | 0.0056 | 93 | -0.278 | 悪化/寄与なし | -31.8 | 5 | マイナス傾向 |
| 51 | `last3_winner_strength_v2` | opponent_strength_v2 | 0.0051 | 34 | +0.196 | 改善 | -18.6 | 3 | マイナス傾向 |
| 52 | `last3_position_advantage` | running_style | 0.0050 | 45 | +0.006 | 改善 | -6.6 | 6 | 混在・不明確 |
| 53 | `last1_winning_margin` | winning_margin | 0.0047 | 40 | +0.076 | 改善 | -6.8 | 5 | 混在・不明確 |
| 54 | `last3_class_matched_adjusted_performance` | class_matched_performance | 0.0047 | 78 | -0.053 | 悪化/寄与なし | -14.3 | 4 | マイナス傾向 |
| 55 | `last3_adjusted_performance` | performance | 0.0046 | 77 | -0.052 | 悪化/寄与なし | -12.6 | 4 | マイナス傾向 |
| 56 | `race_third_prize` | race_prize | 0.0043 | 83 | -0.107 | 悪化/寄与なし | -27.9 | 5 | マイナス傾向 |
| 57 | `weighted_race_prize_last3` | previous_race_prize_aggregate | 0.0042 | 42 | +0.046 | 改善 | -23.4 | 3 | マイナス傾向 |
| 58 | `last3_winner_max_race_class_before_target` | class_history | 0.0042 | 68 | -0.025 | 悪化/寄与なし | -21.0 | 6 | 混在・不明確 |
| 59 | `last3_winner_mean_prize_before_target` | prize_history | 0.0038 | 36 | +0.171 | 改善 | +5.7 | 8 | 混在・不明確 |
| 60 | `current_distance` | distance | 0.0034 | 69 | -0.037 | 悪化/寄与なし | +20.8 | 5 | 混在・不明確 |
| 61 | `last3_field_max_strength_v2` | field_strength_aggregate | 0.0033 | 73 | -0.048 | 悪化/寄与なし | +7.2 | 6 | 混在・不明確 |
| 62 | `last1_winner_max_race_class_before_target` | class_history | 0.0033 | 39 | +0.120 | 改善 | -8.1 | 6 | 混在・不明確 |
| 63 | `mean_race_prize_last3` | previous_race_prize_aggregate | 0.0033 | 29 | +0.230 | 改善 | -28.2 | 2 | マイナス傾向 |
| 64 | `race_first_prize` | race_prize | 0.0032 | 25 | +0.282 | 改善 | +1.6 | 6 | 混在・不明確 |
| 65 | `max_race_prize_last3` | previous_race_prize_aggregate | 0.0031 | 81 | -0.091 | 悪化/寄与なし | -4.0 | 9 | 混在・不明確 |
| 66 | `last5_winning_margin` | winning_margin | 0.0031 | 64 | -0.005 | 悪化/寄与なし | -2.3 | 7 | 混在・不明確 |
| 67 | `career_wins` | career | 0.0031 | 75 | -0.051 | 悪化/寄与なし | -17.1 | 5 | マイナス傾向 |
| 68 | `weighted_winner_strength_last3` | opponent_strength_aggregate | 0.0029 | 33 | +0.197 | 改善 | +11.2 | 7 | プラス傾向 |
| 69 | `last1_winner_mean_prize_before_target` | prize_history | 0.0027 | 94 | -0.292 | 悪化/寄与なし | -8.1 | 6 | 混在・不明確 |
| 70 | `last2_winner_strength_v2` | opponent_strength_v2 | 0.0027 | 86 | -0.133 | 悪化/寄与なし | -13.6 | 5 | マイナス傾向 |
| 71 | `last2_winner_max_race_class_before_target` | class_history | 0.0025 | 67 | -0.020 | 悪化/寄与なし | -7.1 | 7 | 混在・不明確 |
| 72 | `last1_race_first_prize` | previous_race_prize | 0.0023 | 65 | -0.016 | 悪化/寄与なし | -25.2 | 2 | マイナス傾向 |
| 73 | `last2_winner_best_win_class_before_target` | class_history | 0.0018 | 85 | -0.120 | 悪化/寄与なし | +22.0 | 7 | プラス傾向 |
| 74 | `last2_race_first_prize` | previous_race_prize | 0.0018 | 70 | -0.038 | 悪化/寄与なし | -2.1 | 7 | 混在・不明確 |
| 75 | `last1_winner_best_win_class_before_target` | class_history | 0.0017 | 90 | -0.204 | 悪化/寄与なし | -3.1 | 6 | 混在・不明確 |
| 76 | `max_winner_strength_last3` | opponent_strength_aggregate | 0.0015 | 87 | -0.133 | 悪化/寄与なし | -0.4 | 7 | 混在・不明確 |
| 77 | `last2_winning_margin` | winning_margin | 0.0012 | 66 | -0.018 | 悪化/寄与なし | -0.5 | 6 | 混在・不明確 |
| 78 | `last3_winner_best_win_class_before_target` | class_history | 0.0011 | 80 | -0.076 | 悪化/寄与なし | +1.8 | 6 | 混在・不明確 |
| 79 | `field_size` | race_structure | 0.0007 | 76 | -0.052 | 悪化/寄与なし | +7.1 | 7 | 混在・不明確 |
| 80 | `last4_winning_margin` | winning_margin | 0.0006 | 74 | -0.049 | 悪化/寄与なし | +29.4 | 9 | プラス傾向 |
| 81 | `last3_winning_margin` | winning_margin | 0.0004 | 46 | +0.000 | 悪化/寄与なし | +8.3 | 7 | 混在・不明確 |
| 82 | `class_matched_sample_count` | class_matched_performance | 0.0001 | 46 | +0.000 | 悪化/寄与なし | -10.4 | 6 | 混在・不明確 |
| 83 | `max_strong_against_bias_last3` | opponent_bias | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `race_first_prize_log` | race_prize_transform | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last3_winner_max_prize_before_target` | prize_history | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last2_winner_max_prize_before_target` | prize_history | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `race_total_top5_prize_log` | race_prize_transform | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `strong_against_bias_last3` | opponent_bias | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last1_winner_max_prize_before_target` | prize_history | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last2_race_first_prize_log` | previous_race_prize_transform | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last3_race_first_prize_log` | previous_race_prize_transform | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `strong_against_bias_last2` | opponent_bias | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `opponent_history_missing_last3` | data_quality | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `strong_against_bias_last1` | opponent_bias | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |
| 83 | `last1_race_first_prize_log` | previous_race_prize_transform | 0.0000 | 46 | +0.000 | 悪化/寄与なし | +0.0 | 0 | 混在・不明確 |

## 指標の定義と注意

- TreeSHAPは各馬のRankerスコアへの寄与。平均絶対値なので方向ではなく影響量を示す。
- 本命的中率差は、元モデルの的中率から当該特徴量を月内でシャッフルしたモデルの的中率を引き、12か月を単純平均した値。大きい正値ほどAI本命の選択に寄与する。
- ROI差はSHAP上位四分位ROIから下位四分位ROIを引いた値。オッズ・人気・他特徴量の交絡を含む。
- 95特徴量には強い相関があるため、個別順位は「独立した因果的重要度」ではない。
- 単勝払戻は100円購入基準。ROI 100%が損益分岐点。

# Race Class Filter AB Test

## 結論

新馬・未勝利は購入対象外とし、同一モデルFの既存予測に対してA/Bフィルタだけを適用した。

| 条件 | レース | 勝率 | 複勝率 | 単勝ROI | 複勝ROI |
|---|---:|---:|---:|---:|---:|
| A: 1勝クラス以上 | 14 | 0.21 | 0.43 | 74.29% | 67.86% |
| B: 2勝クラス以上 | 14 | 0.21 | 0.43 | 74.29% | 67.86% |
| 1勝クラス単独 | 0 | N/A | N/A | N/A% | N/A% |

## Detailed metrics

```csv
filter,races,horses,top1_wins,top1_places,win_rate,place_rate,logloss,brier,auc,top1_accuracy,top3_accuracy,win_investment,win_payout,win_profit,win_roi,place_investment,place_payout,place_profit,place_roi,top1_mean_odds,top1_median_odds,hit_mean_odds,hit_median_odds,top1_mean_popularity,top1_median_popularity,win_roi_exclude_top_0,win_roi_exclude_top_1,win_roi_exclude_top_3,win_roi_exclude_top_5,place_roi_exclude_top_0,place_roi_exclude_top_1,place_roi_exclude_top_3,place_roi_exclude_top_5
ALL,432,5581,108,241,0.25,0.5578703703703703,0.2392257292706298,0.0660202945664975,0.7624592693295354,0.25,0.5833333333333334,43200,30670.0,-12530.0,70.99537037037037,43200,34860.0,-8340.0,80.69444444444444,69.70370370370371,33.0,28.39814814814815,24.0,2.189814814814815,1.0,70.99537037037037,69.16666666666667,65.94907407407408,63.35648148148149,80.69444444444444,77.96296296296296,75.41666666666667,73.75
A_1plus,14,191,3,6,0.21428571428571427,0.42857142857142855,0.25620279329133616,0.06775135611064853,0.6501210653753027,0.21428571428571427,0.35714285714285715,1400,1040.0,-360.0,74.28571428571429,1400,950.0,-450.0,67.85714285714286,50.07142857142857,40.5,34.666666666666664,29.0,2.0,1.0,74.28571428571429,40.0,0.0,0.0,67.85714285714286,52.85714285714286,29.28571428571429,9.285714285714286
B_2plus,14,191,3,6,0.21428571428571427,0.42857142857142855,0.25620279329133616,0.06775135611064853,0.6501210653753027,0.21428571428571427,0.35714285714285715,1400,1040.0,-360.0,74.28571428571429,1400,950.0,-450.0,67.85714285714286,50.07142857142857,40.5,34.666666666666664,29.0,2.0,1.0,74.28571428571429,40.0,0.0,0.0,67.85714285714286,52.85714285714286,29.28571428571429,9.285714285714286
1勝_ONLY,0,0,0,0,,,,,,,,0,0.0,0.0,,0,0.0,0.0,,,,,,,,,,,,,,,
```

## Interpretation

A/Bの採用判断はROI単独で決めず、1勝クラス単独の的中率、ML指標、オッズ、bootstrap CI、払戻上位除外ROI、月別結果を併読する。

## Outputs

- `race_class_ab_summary.csv`
- `race_class_individual_summary.csv`
- `race_class_cumulative_summary.csv`
- `race_class_odds_band_summary.csv`
- `race_class_popularity_summary.csv`
- `race_class_monthly_summary.csv`
- `race_class_ab_one_win_details.csv`
- `race_class_ab_bootstrap.csv

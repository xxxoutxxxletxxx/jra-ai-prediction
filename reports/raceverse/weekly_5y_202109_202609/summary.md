# RACEVERSE v0.6 Walk-Forward バックテスト

- 評価期間: 2021-09-01 〜 2026-09-01 (助走期間 2021-03-01 〜、校正初期化のみ)
- 試行回数: 10,000 / seed 42 / 既存Rankerと同一の1616レースで比較
- 注意: DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only

## 勝率(同一レース・同一馬)

| model | calibrated | races | winner_logloss | logloss_binary | brier_binary | top1_hit_rate | top3_recall | rank_spearman |
|---|---|---|---|---|---|---|---|---|
| existing_ranker | True | 1616 | 2.2105 | 0.2341 | 0.0638 | 0.2593 | 0.4540 | 0.4270 |
| raceverse_base | False | 1616 | 2.2263 | 0.2355 | 0.0641 | 0.2618 | 0.4550 | 0.4264 |
| raceverse_base | True | 1616 | 2.2074 | 0.2339 | 0.0638 | 0.2618 | 0.4550 | 0.4264 |
| raceverse_formation | False | 1616 | 2.2466 | 0.2372 | 0.0644 | 0.2624 | 0.4505 | 0.4267 |
| raceverse_formation | True | 1616 | 2.2253 | 0.2354 | 0.0641 | 0.2624 | 0.4505 | 0.4267 |
| raceverse_pace | False | 1616 | 2.2510 | 0.2376 | 0.0645 | 0.2580 | 0.4498 | 0.4279 |
| raceverse_pace | True | 1616 | 2.2296 | 0.2358 | 0.0641 | 0.2580 | 0.4498 | 0.4279 |

## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)

| model | buy_rule | bets | investment | returned | roi_pct | max_drawdown | hit_rate |
|---|---|---|---|---|---|---|---|
| existing_ranker | top1 | 1616 | 161600.0000 | 127100.0000 | 78.6510 | 34820.0000 | 0.2593 |
| existing_ranker | rule | 505 | 50500.0000 | 45380.0000 | 89.8614 | 6600.0000 | 0.2020 |
| existing_ranker | ev>=1.0 | 534 | 53400.0000 | 41590.0000 | 77.8839 | 12830.0000 | 0.1311 |
| existing_ranker | ev>=1.2 | 347 | 34700.0000 | 28290.0000 | 81.5274 | 7710.0000 | 0.1009 |
| raceverse_base_calibrated | top1 | 1616 | 161600.0000 | 130840.0000 | 80.9653 | 31080.0000 | 0.2618 |
| raceverse_base_calibrated | rule | 488 | 48800.0000 | 45420.0000 | 93.0738 | 5640.0000 | 0.1824 |
| raceverse_base_calibrated | ev>=1.0 | 574 | 57400.0000 | 45480.0000 | 79.2334 | 12660.0000 | 0.1289 |
| raceverse_base_calibrated | ev>=1.2 | 389 | 38900.0000 | 32940.0000 | 84.6787 | 6580.0000 | 0.1054 |
| raceverse_formation_calibrated | top1 | 1616 | 161600.0000 | 133160.0000 | 82.4010 | 28760.0000 | 0.2624 |
| raceverse_formation_calibrated | rule | 472 | 47200.0000 | 46260.0000 | 98.0085 | 5860.0000 | 0.1758 |
| raceverse_formation_calibrated | ev>=1.0 | 540 | 54000.0000 | 44880.0000 | 83.1111 | 9440.0000 | 0.1241 |
| raceverse_formation_calibrated | ev>=1.2 | 377 | 37700.0000 | 33350.0000 | 88.4615 | 5470.0000 | 0.1061 |
| raceverse_pace_calibrated | top1 | 1616 | 161600.0000 | 129580.0000 | 80.1856 | 32340.0000 | 0.2580 |
| raceverse_pace_calibrated | rule | 463 | 46300.0000 | 42580.0000 | 91.9654 | 5280.0000 | 0.1641 |
| raceverse_pace_calibrated | ev>=1.0 | 519 | 51900.0000 | 36540.0000 | 70.4046 | 15830.0000 | 0.1002 |
| raceverse_pace_calibrated | ev>=1.2 | 368 | 36800.0000 | 29260.0000 | 79.5109 | 7860.0000 | 0.0924 |

## 相対走破時計(走破時計 - 出走馬平均, 秒)の予測誤差

| model | n | mae | rmse | corr | mae_zero_pred | rmse_zero_pred |
|---|---|---|---|---|---|---|
| raceverse_base | 21611 | 0.5844 | 0.9611 | 0.3397 | 0.6415 | 1.0214 |
| raceverse_formation | 21611 | 0.5827 | 0.9585 | 0.3470 | 0.6415 | 1.0214 |
| raceverse_pace | 21611 | 0.5815 | 0.9575 | 0.3496 | 0.6415 | 1.0214 |

## ペース(前半ラップ, 秒)

| predictor | n | mae | rmse | bias |
|---|---|---|---|---|
| model_sim_mean | 5976.0000 | 0.5603 | 0.7291 | -0.0403 |
| reference_baseline_only | 5976.0000 | 0.6127 | 0.7863 | 0.0976 |
| regression_mean_only | 5976.0000 | 0.5603 | 0.7291 | -0.0403 |

P10-P90 被覆率: 0.168 (理想 0.80)

表示5段階の予測発生率と実測発生率:

| bucket | predicted_rate | actual_rate |
|---|---|---|
| VERY_FAST | 0.0072 | 0.1183 |
| FAST | 0.1447 | 0.2207 |
| MIDDLE | 0.7879 | 0.3884 |
| SLOW | 0.0599 | 0.1886 |
| VERY_SLOW | 0.0003 | 0.0840 |

## 決着時計(勝ち時計, 秒)

| model | n | mae | rmse | bias |
|---|---|---|---|---|
| baseline | 5976.0000 | 0.8601 | 1.1379 | 0.1608 |
| track_bias | 5976.0000 | 0.7902 | 1.0445 | 0.0547 |
| field_ability | 5976.0000 | 0.7710 | 1.0195 | 0.0669 |
| full | 5976.0000 | 0.7387 | 0.9854 | 0.0970 |

P10-P90 被覆率: 0.781 (理想 0.80)

## 初期隊列

- 相対序盤位置のMAE 0.2051 (定数予測 0.2678)
- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 0.687

実行時間 1930秒

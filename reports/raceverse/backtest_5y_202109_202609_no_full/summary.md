# RACEVERSE v0.6 Walk-Forward バックテスト

- 評価期間: 2021-09-01 〜 2026-09-01 (助走期間 2021-03-01 〜、校正初期化のみ)
- 試行回数: 10,000 / seed 42 / 既存Rankerと同一の1616レースで比較
- 注意: DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only

## 勝率(同一レース・同一馬)

| model | calibrated | races | winner_logloss | logloss_binary | brier_binary | top1_hit_rate | top3_recall | rank_spearman |
|---|---|---|---|---|---|---|---|---|
| existing_ranker | True | 1616 | 2.2105 | 0.2341 | 0.0638 | 0.2593 | 0.4540 | 0.4270 |
| raceverse_base | False | 1616 | 2.2233 | 0.2352 | 0.0640 | 0.2630 | 0.4550 | 0.4253 |
| raceverse_base | True | 1616 | 2.2095 | 0.2340 | 0.0638 | 0.2630 | 0.4550 | 0.4253 |
| raceverse_formation | False | 1616 | 2.2425 | 0.2368 | 0.0643 | 0.2593 | 0.4519 | 0.4258 |
| raceverse_formation | True | 1616 | 2.2256 | 0.2353 | 0.0640 | 0.2593 | 0.4519 | 0.4258 |
| raceverse_pace | False | 1616 | 2.2484 | 0.2374 | 0.0644 | 0.2543 | 0.4478 | 0.4276 |
| raceverse_pace | True | 1616 | 2.2300 | 0.2358 | 0.0641 | 0.2543 | 0.4478 | 0.4276 |

## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)

| model | buy_rule | bets | investment | returned | roi_pct | max_drawdown | hit_rate |
|---|---|---|---|---|---|---|---|
| existing_ranker | top1 | 1616 | 161600.0000 | 127100.0000 | 78.6510 | 34820.0000 | 0.2593 |
| existing_ranker | rule | 505 | 50500.0000 | 45380.0000 | 89.8614 | 6600.0000 | 0.2020 |
| existing_ranker | ev>=1.0 | 534 | 53400.0000 | 41590.0000 | 77.8839 | 12830.0000 | 0.1311 |
| existing_ranker | ev>=1.2 | 347 | 34700.0000 | 28290.0000 | 81.5274 | 7710.0000 | 0.1009 |
| raceverse_base_calibrated | top1 | 1616 | 161600.0000 | 130450.0000 | 80.7240 | 31370.0000 | 0.2630 |
| raceverse_base_calibrated | rule | 478 | 47800.0000 | 45390.0000 | 94.9582 | 4960.0000 | 0.1904 |
| raceverse_base_calibrated | ev>=1.0 | 526 | 52600.0000 | 43080.0000 | 81.9011 | 10340.0000 | 0.1274 |
| raceverse_base_calibrated | ev>=1.2 | 355 | 35500.0000 | 29740.0000 | 83.7746 | 7060.0000 | 0.1014 |
| raceverse_formation_calibrated | top1 | 1616 | 161600.0000 | 133240.0000 | 82.4505 | 28580.0000 | 0.2593 |
| raceverse_formation_calibrated | rule | 501 | 50100.0000 | 50240.0000 | 100.2794 | 6860.0000 | 0.1876 |
| raceverse_formation_calibrated | ev>=1.0 | 582 | 58200.0000 | 49060.0000 | 84.2955 | 9460.0000 | 0.1306 |
| raceverse_formation_calibrated | ev>=1.2 | 417 | 41700.0000 | 35650.0000 | 85.4916 | 5990.0000 | 0.1079 |
| raceverse_pace_calibrated | top1 | 1616 | 161600.0000 | 127880.0000 | 79.1337 | 33620.0000 | 0.2543 |
| raceverse_pace_calibrated | rule | 479 | 47900.0000 | 45280.0000 | 94.5303 | 5170.0000 | 0.1795 |
| raceverse_pace_calibrated | ev>=1.0 | 548 | 54800.0000 | 41160.0000 | 75.1095 | 13660.0000 | 0.1150 |
| raceverse_pace_calibrated | ev>=1.2 | 383 | 38300.0000 | 30150.0000 | 78.7206 | 8050.0000 | 0.0940 |

## 相対走破時計(走破時計 - 出走馬平均, 秒)の予測誤差

| model | n | mae | rmse | corr | mae_zero_pred | rmse_zero_pred |
|---|---|---|---|---|---|---|
| raceverse_base | 21611 | 0.5844 | 0.9607 | 0.3402 | 0.6415 | 1.0214 |
| raceverse_formation | 21611 | 0.5827 | 0.9582 | 0.3473 | 0.6415 | 1.0214 |
| raceverse_pace | 21611 | 0.5816 | 0.9575 | 0.3492 | 0.6415 | 1.0214 |

## ペース(前半ラップ, 秒)

| predictor | n | mae | rmse | bias |
|---|---|---|---|---|
| model_sim_mean | 4515.0000 | 0.5633 | 0.7363 | -0.0253 |
| reference_baseline_only | 4515.0000 | 0.6105 | 0.7874 | 0.1093 |
| regression_mean_only | 4515.0000 | 0.5633 | 0.7363 | -0.0253 |

P10-P90 被覆率: 0.167 (理想 0.80)

表示5段階の予測発生率と実測発生率:

| bucket | predicted_rate | actual_rate |
|---|---|---|
| VERY_FAST | 0.0052 | 0.1172 |
| FAST | 0.1332 | 0.2184 |
| MIDDLE | 0.8004 | 0.3927 |
| SLOW | 0.0609 | 0.1909 |
| VERY_SLOW | 0.0003 | 0.0808 |

## 決着時計(勝ち時計, 秒)

| model | n | mae | rmse | bias |
|---|---|---|---|---|
| baseline | 3616.0000 | 0.8651 | 1.1336 | 0.1389 |
| track_bias | 3616.0000 | 0.7961 | 1.0441 | 0.0698 |
| field_ability | 3616.0000 | 0.7842 | 1.0293 | 0.1043 |
| full | 3616.0000 | 0.7519 | 0.9971 | 0.0864 |

P10-P90 被覆率: 0.780 (理想 0.80)

## 初期隊列

- 相対序盤位置のMAE 0.2065 (定数予測 0.2678)
- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 0.680

実行時間 917秒

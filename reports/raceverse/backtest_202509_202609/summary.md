# RACEVERSE v0.6 Walk-Forward バックテスト

- 評価期間: 2025-09-01 〜 2026-09-01 (助走期間 2025-03-01 〜、校正初期化のみ)
- 試行回数: 10,000 / seed 42 / 既存Rankerと同一の1616レースで比較
- 注意: DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only

## 勝率(同一レース・同一馬)

| model | calibrated | races | winner_logloss | logloss_binary | brier_binary | top1_hit_rate | top3_recall | rank_spearman |
|---|---|---|---|---|---|---|---|---|
| existing_ranker | True | 1616 | 2.2105 | 0.2341 | 0.0638 | 0.2593 | 0.4540 | 0.4270 |
| raceverse_base | False | 1616 | 2.2234 | 0.2352 | 0.0640 | 0.2587 | 0.4568 | 0.4256 |
| raceverse_base | True | 1616 | 2.2092 | 0.2340 | 0.0638 | 0.2587 | 0.4568 | 0.4256 |
| raceverse_formation | False | 1616 | 2.2420 | 0.2368 | 0.0643 | 0.2562 | 0.4498 | 0.4273 |
| raceverse_formation | True | 1616 | 2.2252 | 0.2353 | 0.0640 | 0.2562 | 0.4498 | 0.4273 |
| raceverse_pace | False | 1616 | 2.2508 | 0.2375 | 0.0645 | 0.2537 | 0.4468 | 0.4185 |
| raceverse_pace | True | 1616 | 2.2304 | 0.2358 | 0.0641 | 0.2537 | 0.4468 | 0.4185 |
| raceverse_full | False | 1616 | 2.2699 | 0.2390 | 0.0646 | 0.2370 | 0.4441 | 0.4299 |
| raceverse_full | True | 1616 | 2.2595 | 0.2381 | 0.0643 | 0.2370 | 0.4441 | 0.4299 |

## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)

| model | buy_rule | bets | investment | returned | roi_pct | max_drawdown | hit_rate |
|---|---|---|---|---|---|---|---|
| existing_ranker | top1 | 1616 | 161600.0000 | 127100.0000 | 78.6510 | 34820.0000 | 0.2593 |
| existing_ranker | rule | 505 | 50500.0000 | 45380.0000 | 89.8614 | 6600.0000 | 0.2020 |
| existing_ranker | ev>=1.0 | 534 | 53400.0000 | 41590.0000 | 77.8839 | 12830.0000 | 0.1311 |
| existing_ranker | ev>=1.2 | 347 | 34700.0000 | 28290.0000 | 81.5274 | 7710.0000 | 0.1009 |
| raceverse_base_calibrated | top1 | 1616 | 161600.0000 | 126470.0000 | 78.2611 | 35450.0000 | 0.2587 |
| raceverse_base_calibrated | rule | 478 | 47800.0000 | 42380.0000 | 88.6611 | 5890.0000 | 0.1820 |
| raceverse_base_calibrated | ev>=1.0 | 520 | 52000.0000 | 39290.0000 | 75.5577 | 13350.0000 | 0.1212 |
| raceverse_base_calibrated | ev>=1.2 | 342 | 34200.0000 | 27170.0000 | 79.4444 | 7650.0000 | 0.0994 |
| raceverse_formation_calibrated | top1 | 1616 | 161600.0000 | 130080.0000 | 80.4950 | 31740.0000 | 0.2562 |
| raceverse_formation_calibrated | rule | 508 | 50800.0000 | 47020.0000 | 92.5591 | 6620.0000 | 0.1752 |
| raceverse_formation_calibrated | ev>=1.0 | 588 | 58800.0000 | 47250.0000 | 80.3571 | 11870.0000 | 0.1241 |
| raceverse_formation_calibrated | ev>=1.2 | 419 | 41900.0000 | 34490.0000 | 82.3150 | 7730.0000 | 0.1002 |
| raceverse_pace_calibrated | top1 | 1616 | 161600.0000 | 126990.0000 | 78.5829 | 34510.0000 | 0.2537 |
| raceverse_pace_calibrated | rule | 491 | 49100.0000 | 43020.0000 | 87.6171 | 7200.0000 | 0.1690 |
| raceverse_pace_calibrated | ev>=1.0 | 550 | 55000.0000 | 43050.0000 | 78.2727 | 11850.0000 | 0.1236 |
| raceverse_pace_calibrated | ev>=1.2 | 387 | 38700.0000 | 29240.0000 | 75.5556 | 10030.0000 | 0.0904 |
| raceverse_full_calibrated | top1 | 1616 | 161600.0000 | 115100.0000 | 71.2252 | 46400.0000 | 0.2370 |
| raceverse_full_calibrated | rule | 509 | 50900.0000 | 36160.0000 | 71.0413 | 14670.0000 | 0.1493 |
| raceverse_full_calibrated | ev>=1.0 | 563 | 56300.0000 | 36480.0000 | 64.7957 | 19720.0000 | 0.1155 |
| raceverse_full_calibrated | ev>=1.2 | 411 | 41100.0000 | 23470.0000 | 57.1046 | 17530.0000 | 0.0754 |

## ペース(前半ラップ, 秒)

| predictor | n | mae | rmse | bias |
|---|---|---|---|---|
| model_sim_mean | 1616.0000 | 0.5658 | 0.7296 | -0.0368 |
| reference_baseline_only | 1616.0000 | 0.6002 | 0.7639 | 0.1267 |
| regression_mean_only | 1616.0000 | 0.5666 | 0.7293 | -0.0088 |

P10-P90 被覆率: 0.786 (理想 0.80)

表示5段階の予測発生率と実測発生率:

| bucket | predicted_rate | actual_rate |
|---|---|---|
| VERY_FAST | 0.1330 | 0.1219 |
| FAST | 0.2156 | 0.2184 |
| MIDDLE | 0.3985 | 0.3917 |
| SLOW | 0.1779 | 0.1900 |
| VERY_SLOW | 0.0749 | 0.0780 |

## 決着時計(勝ち時計, 秒)

| model | n | mae | rmse | bias |
|---|---|---|---|---|
| baseline | 1616.0000 | 0.8562 | 1.1278 | 0.3077 |
| track_bias | 1616.0000 | 0.7868 | 1.0343 | 0.2032 |
| field_ability | 1616.0000 | 0.7919 | 1.0367 | 0.2736 |
| full | 1616.0000 | 0.7340 | 0.9740 | 0.0959 |

P10-P90 被覆率: 0.763 (理想 0.80)

## 初期隊列

- 相対序盤位置のMAE 0.2095 (定数予測 0.2678)
- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 0.639

実行時間 378秒

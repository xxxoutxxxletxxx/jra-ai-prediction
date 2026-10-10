# RACEVERSE v0.6 Walk-Forward バックテスト

- 評価期間: 2025-09-01 〜 2026-09-01 (助走期間 2025-03-01 〜、校正初期化のみ)
- 試行回数: 10,000 / seed 42 / 既存Rankerと同一の1616レースで比較
- 注意: DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only

## 勝率(同一レース・同一馬)

| model | calibrated | races | winner_logloss | logloss_binary | brier_binary | top1_hit_rate | top3_recall | rank_spearman |
|---|---|---|---|---|---|---|---|---|
| existing_ranker | True | 1616 | 2.2105 | 0.2341 | 0.0638 | 0.2593 | 0.4540 | 0.4270 |
| raceverse_base | False | 1616 | 2.2225 | 0.2352 | 0.0640 | 0.2624 | 0.4544 | 0.4254 |
| raceverse_base | True | 1616 | 2.2085 | 0.2339 | 0.0638 | 0.2624 | 0.4544 | 0.4254 |
| raceverse_formation | False | 1616 | 2.2414 | 0.2367 | 0.0643 | 0.2574 | 0.4523 | 0.4253 |
| raceverse_formation | True | 1616 | 2.2241 | 0.2352 | 0.0640 | 0.2574 | 0.4523 | 0.4253 |
| raceverse_pace | False | 1616 | 2.2474 | 0.2373 | 0.0644 | 0.2537 | 0.4482 | 0.4280 |
| raceverse_pace | True | 1616 | 2.2290 | 0.2357 | 0.0641 | 0.2537 | 0.4482 | 0.4280 |
| raceverse_full | False | 1616 | 2.2668 | 0.2387 | 0.0645 | 0.2426 | 0.4406 | 0.4312 |
| raceverse_full | True | 1616 | 2.2562 | 0.2378 | 0.0643 | 0.2426 | 0.4406 | 0.4312 |

## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)

| model | buy_rule | bets | investment | returned | roi_pct | max_drawdown | hit_rate |
|---|---|---|---|---|---|---|---|
| existing_ranker | top1 | 1616 | 161600.0000 | 127100.0000 | 78.6510 | 34820.0000 | 0.2593 |
| existing_ranker | rule | 505 | 50500.0000 | 45380.0000 | 89.8614 | 6600.0000 | 0.2020 |
| existing_ranker | ev>=1.0 | 534 | 53400.0000 | 41590.0000 | 77.8839 | 12830.0000 | 0.1311 |
| existing_ranker | ev>=1.2 | 347 | 34700.0000 | 28290.0000 | 81.5274 | 7710.0000 | 0.1009 |
| raceverse_base_calibrated | top1 | 1616 | 161600.0000 | 130290.0000 | 80.6250 | 31530.0000 | 0.2624 |
| raceverse_base_calibrated | rule | 482 | 48200.0000 | 46050.0000 | 95.5394 | 4970.0000 | 0.1929 |
| raceverse_base_calibrated | ev>=1.0 | 530 | 53000.0000 | 43460.0000 | 82.0000 | 10460.0000 | 0.1283 |
| raceverse_base_calibrated | ev>=1.2 | 345 | 34500.0000 | 29470.0000 | 85.4203 | 6670.0000 | 0.1014 |
| raceverse_formation_calibrated | top1 | 1616 | 161600.0000 | 131240.0000 | 81.2129 | 30580.0000 | 0.2574 |
| raceverse_formation_calibrated | rule | 502 | 50200.0000 | 49120.0000 | 97.8486 | 7030.0000 | 0.1853 |
| raceverse_formation_calibrated | ev>=1.0 | 581 | 58100.0000 | 49020.0000 | 84.3718 | 9400.0000 | 0.1343 |
| raceverse_formation_calibrated | ev>=1.2 | 414 | 41400.0000 | 34270.0000 | 82.7778 | 7030.0000 | 0.1039 |
| raceverse_pace_calibrated | top1 | 1616 | 161600.0000 | 128820.0000 | 79.7153 | 32680.0000 | 0.2537 |
| raceverse_pace_calibrated | rule | 478 | 47800.0000 | 46450.0000 | 97.1757 | 4290.0000 | 0.1799 |
| raceverse_pace_calibrated | ev>=1.0 | 547 | 54700.0000 | 42920.0000 | 78.4644 | 11850.0000 | 0.1188 |
| raceverse_pace_calibrated | ev>=1.2 | 384 | 38400.0000 | 31590.0000 | 82.2656 | 6710.0000 | 0.0964 |
| raceverse_full_calibrated | top1 | 1616 | 161600.0000 | 119110.0000 | 73.7067 | 42390.0000 | 0.2426 |
| raceverse_full_calibrated | rule | 518 | 51800.0000 | 39380.0000 | 76.0232 | 12350.0000 | 0.1602 |
| raceverse_full_calibrated | ev>=1.0 | 572 | 57200.0000 | 39430.0000 | 68.9336 | 17670.0000 | 0.1224 |
| raceverse_full_calibrated | ev>=1.2 | 414 | 41400.0000 | 26400.0000 | 63.7681 | 14900.0000 | 0.0845 |

## ペース(前半ラップ, 秒)

| predictor | n | mae | rmse | bias |
|---|---|---|---|---|
| model_sim_mean | 1616.0000 | 0.5612 | 0.7210 | 0.0074 |
| reference_baseline_only | 1616.0000 | 0.6002 | 0.7639 | 0.1267 |
| regression_mean_only | 1616.0000 | 0.5612 | 0.7210 | 0.0074 |

P10-P90 被覆率: 0.164 (理想 0.80)

表示5段階の予測発生率と実測発生率:

| bucket | predicted_rate | actual_rate |
|---|---|---|
| VERY_FAST | 0.0025 | 0.1219 |
| FAST | 0.1067 | 0.2184 |
| MIDDLE | 0.8280 | 0.3917 |
| SLOW | 0.0626 | 0.1900 |
| VERY_SLOW | 0.0002 | 0.0780 |

## 決着時計(勝ち時計, 秒)

| model | n | mae | rmse | bias |
|---|---|---|---|---|
| baseline | 1616.0000 | 0.8562 | 1.1278 | 0.3077 |
| track_bias | 1616.0000 | 0.7868 | 1.0343 | 0.2032 |
| field_ability | 1616.0000 | 0.7919 | 1.0367 | 0.2736 |
| full | 1616.0000 | 0.7582 | 1.0037 | 0.2477 |

P10-P90 被覆率: 0.764 (理想 0.80)

## 初期隊列

- 相対序盤位置のMAE 0.2095 (定数予測 0.2678)
- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 0.639

実行時間 547秒

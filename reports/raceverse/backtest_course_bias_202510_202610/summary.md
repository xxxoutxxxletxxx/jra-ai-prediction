# RACEVERSE v0.6 Walk-Forward バックテスト

- 評価期間: 2025-10-01 〜 2026-10-01 (助走期間 2025-04-01 〜、校正初期化のみ)
- 試行回数: 10,000 / seed 42 / 既存Rankerと同一の1545レースで比較
- 注意: DB odds are FINAL odds, not pre-bet snapshots; ROI is reference only

## 勝率(同一レース・同一馬)

| model | calibrated | races | winner_logloss | logloss_binary | brier_binary | top1_hit_rate | top3_recall | rank_spearman |
|---|---|---|---|---|---|---|---|---|
| existing_ranker | True | 1545 | 2.2102 | 0.2332 | 0.0636 | 0.2621 | 0.4533 | 0.4272 |
| raceverse_formation | False | 1545 | 2.2434 | 0.2361 | 0.0641 | 0.2602 | 0.4522 | 0.4257 |
| raceverse_formation | True | 1545 | 2.2251 | 0.2345 | 0.0638 | 0.2602 | 0.4522 | 0.4257 |
| raceverse_pace | False | 1545 | 2.2495 | 0.2366 | 0.0642 | 0.2544 | 0.4481 | 0.4279 |
| raceverse_pace | True | 1545 | 2.2300 | 0.2349 | 0.0639 | 0.2544 | 0.4481 | 0.4279 |
| raceverse_formation_bias | False | 1545 | 2.2450 | 0.2362 | 0.0641 | 0.2570 | 0.4522 | 0.4271 |
| raceverse_formation_bias | True | 1545 | 2.2299 | 0.2349 | 0.0638 | 0.2570 | 0.4522 | 0.4271 |
| raceverse_pace_bias | False | 1545 | 2.2503 | 0.2367 | 0.0642 | 0.2466 | 0.4492 | 0.4279 |
| raceverse_pace_bias | True | 1545 | 2.2323 | 0.2351 | 0.0639 | 0.2466 | 0.4492 | 0.4279 |

## 回収率(参考値: 確定オッズ使用。発走前スナップショットではない)

| model | buy_rule | bets | investment | returned | roi_pct | max_drawdown | hit_rate |
|---|---|---|---|---|---|---|---|
| existing_ranker | top1 | 1545 | 154500.0000 | 124180.0000 | 80.3754 | 32020.0000 | 0.2621 |
| existing_ranker | rule | 478 | 47800.0000 | 43810.0000 | 91.6527 | 6600.0000 | 0.1967 |
| existing_ranker | ev>=1.0 | 516 | 51600.0000 | 40870.0000 | 79.2054 | 12830.0000 | 0.1318 |
| existing_ranker | ev>=1.2 | 334 | 33400.0000 | 27790.0000 | 83.2036 | 7710.0000 | 0.1018 |
| raceverse_formation_calibrated | top1 | 1545 | 154500.0000 | 128180.0000 | 82.9644 | 26540.0000 | 0.2602 |
| raceverse_formation_calibrated | rule | 478 | 47800.0000 | 48070.0000 | 100.5649 | 5680.0000 | 0.1841 |
| raceverse_formation_calibrated | ev>=1.0 | 561 | 56100.0000 | 48520.0000 | 86.4884 | 7900.0000 | 0.1373 |
| raceverse_formation_calibrated | ev>=1.2 | 399 | 39900.0000 | 33770.0000 | 84.6366 | 6030.0000 | 0.1053 |
| raceverse_pace_calibrated | top1 | 1545 | 154500.0000 | 124760.0000 | 80.7508 | 29640.0000 | 0.2544 |
| raceverse_pace_calibrated | rule | 455 | 45500.0000 | 44590.0000 | 98.0000 | 4170.0000 | 0.1736 |
| raceverse_pace_calibrated | ev>=1.0 | 528 | 52800.0000 | 42200.0000 | 79.9242 | 10550.0000 | 0.1193 |
| raceverse_pace_calibrated | ev>=1.2 | 368 | 36800.0000 | 31090.0000 | 84.4837 | 5850.0000 | 0.0978 |
| raceverse_formation_bias_calibrated | top1 | 1545 | 154500.0000 | 124380.0000 | 80.5049 | 30410.0000 | 0.2570 |
| raceverse_formation_bias_calibrated | rule | 473 | 47300.0000 | 45560.0000 | 96.3214 | 5150.0000 | 0.1860 |
| raceverse_formation_bias_calibrated | ev>=1.0 | 546 | 54600.0000 | 44370.0000 | 81.2637 | 10550.0000 | 0.1282 |
| raceverse_formation_bias_calibrated | ev>=1.2 | 372 | 37200.0000 | 29790.0000 | 80.0806 | 7730.0000 | 0.0968 |
| raceverse_pace_bias_calibrated | top1 | 1545 | 154500.0000 | 120200.0000 | 77.7994 | 34200.0000 | 0.2466 |
| raceverse_pace_bias_calibrated | rule | 470 | 47000.0000 | 43680.0000 | 92.9362 | 4420.0000 | 0.1723 |
| raceverse_pace_bias_calibrated | ev>=1.0 | 549 | 54900.0000 | 43130.0000 | 78.5610 | 11670.0000 | 0.1202 |
| raceverse_pace_bias_calibrated | ev>=1.2 | 378 | 37800.0000 | 30860.0000 | 81.6402 | 6860.0000 | 0.1005 |

## 相対走破時計(走破時計 - 出走馬平均, 秒)の予測誤差

| model | n | mae | rmse | corr | mae_zero_pred | rmse_zero_pred |
|---|---|---|---|---|---|---|
| raceverse_formation | 20733 | 0.5849 | 0.9628 | 0.3469 | 0.6440 | 1.0262 |
| raceverse_pace | 20733 | 0.5838 | 0.9622 | 0.3486 | 0.6440 | 1.0262 |
| raceverse_formation_bias | 20733 | 0.5846 | 0.9627 | 0.3471 | 0.6440 | 1.0262 |
| raceverse_pace_bias | 20733 | 0.5834 | 0.9620 | 0.3489 | 0.6440 | 1.0262 |

## コースバイアス追加の改善度 (formation->formation_bias, 詳細は course_bias_group_gains.csv)

| dimension | groups | logloss_improved | mae_time_improved |
|---|---|---|---|
| distance_band | 4 | 0 | 4 |
| style | 4 | 1 | 2 |
| surface | 2 | 0 | 1 |
| track | 10 | 4 | 5 |
| wakuban_k | 8 | 2 | 6 |

## コースバイアス追加の改善度 (pace->pace_bias, 詳細は course_bias_group_gains.csv)

| dimension | groups | logloss_improved | mae_time_improved |
|---|---|---|---|
| distance_band | 4 | 1 | 4 |
| style | 4 | 1 | 3 |
| surface | 2 | 1 | 1 |
| track | 10 | 4 | 7 |
| wakuban_k | 8 | 2 | 7 |

## ペース(前半ラップ, 秒)

| predictor | n | mae | rmse | bias |
|---|---|---|---|---|
| model_sim_mean | 1545.0000 | 0.5568 | 0.7134 | 0.0191 |
| reference_baseline_only | 1545.0000 | 0.5978 | 0.7594 | 0.1324 |
| regression_mean_only | 1545.0000 | 0.5568 | 0.7134 | 0.0191 |

P10-P90 被覆率: 0.165 (理想 0.80)

表示5段階の予測発生率と実測発生率:

| bucket | predicted_rate | actual_rate |
|---|---|---|
| VERY_FAST | 0.0021 | 0.1236 |
| FAST | 0.1001 | 0.2175 |
| MIDDLE | 0.8332 | 0.3935 |
| SLOW | 0.0643 | 0.1896 |
| VERY_SLOW | 0.0002 | 0.0757 |

## 決着時計(勝ち時計, 秒)

| model | n | mae | rmse | bias |
|---|---|---|---|---|
| baseline | 1545.0000 | 0.8573 | 1.1318 | 0.3088 |
| track_bias | 1545.0000 | 0.7873 | 1.0379 | 0.2140 |
| field_ability | 1545.0000 | 0.7932 | 1.0404 | 0.2864 |
| full | 1545.0000 | 0.7615 | 1.0081 | 0.2604 |

P10-P90 被覆率: 0.761 (理想 0.80)

## 初期隊列

- 相対序盤位置のMAE 0.2095 (定数予測 0.2676)
- 実際の序盤先頭馬が逃げ確率上位3頭に入った割合 0.638

実行時間 575秒

# Ranker 着差補正 12か月 walk-forward 再評価

## 実装
- raw結果読込直後に元の着順・TimeDiffを保持し、`corrected_margin`、`effective_rank`、`blowout_margin_value`を共通生成。
- 1着→3着差0.6秒以上を対象とし、1着→2着差0.5秒以上は1着のみ、それ未満は1・2着を除外して着差を再計算。
- 除外馬の自然な実測差を負の着差として近走パフォーマンスへ反映。
- Ranker入力から career_win_rate / career_races / recent3_win_rate / recent3_place_rate と生の着順・着差系を除外。
- 過去5走の実際の勝利時着差、勝利マージン平均・最大を追加（非勝利走は平均から除外）。

## 補正件数・その後の成績
- 全期間の補正対象馬行: 22,744、補正レース: 15,152。
- 評価期間の補正対象馬行: 1,567、補正レース: 1,041。
- 1走以内: 勝率 19.74%、同クラス以上勝ち上がり率 17.50% (対象 1,246)
- 2走以内: 勝率 33.66%、同クラス以上勝ち上がり率 29.98% (対象 924)
- 3走以内: 勝率 43.01%、同クラス以上勝ち上がり率 39.36% (対象 658)

## 変更前後（2025-09〜2026-08）
- 変更前 (92特徴): Top1 25.69%, 単勝ROI 75.93%, 複勝ROI 80.71%, AI本命平均人気 2.11
- 変更後 (95特徴): Top1 26.43%, 単勝ROI 80.50%, 複勝ROI 82.10%, AI本命平均人気 2.11

## 人気別 Top1
| variant | 人気帯 | 件数 | 的中率 | 単勝ROI | 複勝ROI | 予測勝率 | 実勝率 | 予測−実績 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| before_margin_correction | 1 | 860 | 36.86% | 81.52% | 85.16% | 29.23% | 36.86% | -7.63% |
| before_margin_correction | 2 | 342 | 18.71% | 66.14% | 81.46% | 25.88% | 18.71% | 7.17% |
| before_margin_correction | 3-6 | 373 | 8.58% | 61.55% | 65.60% | 21.82% | 8.58% | 13.24% |
| before_margin_correction | 7_plus | 52 | 9.62% | 150.77% | 110.58% | 17.27% | 9.62% | 7.66% |
| after_margin_correction | 1 | 857 | 37.11% | 82.30% | 85.72% | 28.04% | 37.11% | -9.06% |
| after_margin_correction | 2 | 350 | 19.71% | 69.49% | 82.09% | 24.10% | 19.71% | 4.39% |
| after_margin_correction | 3-6 | 368 | 10.05% | 70.73% | 70.30% | 20.70% | 10.05% | 10.64% |
| after_margin_correction | 7_plus | 52 | 11.54% | 194.04% | 106.15% | 17.01% | 11.54% | 5.47% |
`predicted_win_rate` と `actual_win_rate` の差は予測−実績。詳細は `popularity_metrics.csv`。

## 出力
- `predictions_before.csv` / `predictions_after.csv`: 同一月次walk-forwardの予測。
- `comparison.csv`、`popularity_metrics.csv`: 指定指標の比較。
- `correction_outcomes.csv` / `correction_summary.json`: 補正対象馬の後続1〜3走と同クラス以上の成績。

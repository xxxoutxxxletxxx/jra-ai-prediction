# RACEVERSE 回収率・購入条件検証

## 目的とデータ

予測確率・Top1選択の精度と、購入対象を絞った場合の回収率を切り分けて検証します。既存の月次Walk-Forward出力 `reports/raceverse/backtest_5y_202109_202609_no_full` を再利用し、GradeCDと確定払戻は `data/raw/race.db` から取得します。再学習および既存予測パイプラインの変更は行いません。

- 校正済み予測の実対象期間: 2023-02-04〜2026-08-30（両端を含む）
- レース数: 4,411、方式ごとの出走馬数: 59,173
- 対象方式: base / formation / pace。廃止済みfullは除外。
- 購入額: 1レースあたり単勝100円。
- 2023年・2026年は有効な評価期間のみで、通年ではありません。
- GradeCD A/B/C/LのみG1/G2/G3/Listedと表示します。D/Eは `GradeCD=D` / `GradeCD=E` のまま扱い、その他の未確認コードをクラス名に読み替えません。

## 時点情報と制約

既存出力の `win_odds_reference` は確定オッズです。予測CSVと利用可能なレースDBには、発走前オッズと取得時刻を確認できる履歴がありません。そのためS5およびEV閾値の成績は事後オラクル分析に限定し、実運用可能な購入結果とは区別します。オッズ変動も検証できません。

確定払戻はCSV内で多数の出走馬について欠損しているため、`race.db` の `NL_HR_PAY` から復元します。勝ち馬の払戻欠損はエラーとし、払戻記録のない非勝ち馬は払戻0円として扱います。元予測は月次Walk-Forwardで生成され、校正確率も過去の結果に基づく一方、購入条件にはさらに6か月ごとの拡大型Walk-Forwardを適用し、各テスト期間より前のデータだけで閾値・条件を選びます。

対象4,411レースは既存レポート等ですでに参照済みです。したがって本検証は未使用テストではなく、独立した最終認証として扱えません。

## 実行方法

```bash
.venv/bin/python scripts/raceverse_roi_strategy_validation.py
```

Optional paths:

```bash
.venv/bin/python scripts/raceverse_roi_strategy_validation.py \
  --input reports/raceverse/backtest_5y_202109_202609_no_full \
  --combinations reports/raceverse/market_analysis_5y_202109_202609_no_full/roi_by_combination.csv \
  --db data/raw/race.db \
  --out reports/raceverse/roi_strategy_validation
```

## 出力

- `summary.md`: 結論、推奨、制約、質問への回答。
- `annual_stability.csv`: 指定条件と、既存CSVから抽出した「30件以上・全期間ROI100%以上」の複合条件の年別成績。既存条件は事後選択であることを記録します。
- `model_agreement.csv`: 3方式の一致・不一致、確率ばらつき、年別成績。
- `calibration_analysis.csv`: 全出走馬のBrier / Winner Logloss / ECE / reliability bins、およびTop1勝率帯。
- `odds_band_analysis.csv`: 確定オッズ帯ごとのTop1成績（事後分析）。
- `purchase_rate_analysis.csv`: 5種類のオッズ非依存指標について、10/20/30/50/100%を狙ったWalk-Forward結果と非購入レースとの比較。
- `strategy_comparison.csv`: OOS S0〜S6の比較、日付クラスタ対応Bootstrap信頼区間、別枠のS5事後オラクル。
- `walk_forward_results.csv`: foldごとの成績と過去データのみで選んだ閾値・条件。
- `bet_level_results.csv`: 各方式Top1、合意候補、確定オッズを使う事後最大EV候補、払戻、fold、選択フラグ。
- グラフ:
- `reliability_diagram.png`
- `annual_roi_stability.png`
- `walk_forward_strategy_roi.png`
- `purchase_rate_roi.png`

全CSVに `analysis_period` と標本数、またはレース単位の期間情報を含めます。少数標本は除外せずフラグで示します。Winner Loglossは同着3レースを除外します。

# 現行予想の使用要素まとめ（2026-11-08時点）

構成は「Ranker（能力指標）→ RACEVERSE（展開・走破性能シミュレーション）→ 勝率校正」の3段。
目的は、全部賭けの平均回収率を約90%にし、その中で得意条件を探すこと。

## 0. 前提（目標との距離）

- 現在の単勝回収率（予測1位に全賭け、5年窓 4,411レース）: base 80.3% / formation 80.3% / pace 77.4%。
- 同条件で確定オッズの1番人気を全賭けすると 80.0%。90%には市場より明確に強い必要がある。
- Winner Logloss は市場比で約11〜12%悪い（base 2.1881 / pace 2.2092 / market 1.9682）。
- 回収率は確定オッズを使った事後値。発走前に同じオッズで買えたとは限らない。
- オッズ・人気は予測の入力に使っておらず、評価にだけ使っている。

## 1. Ranker（LGBMRanker・lambdarank、本番86特徴量）

定義: `src/backtest.py` の `RANKER_MARGIN_CORRECTION_FEATURES`（`CLEANUP_F_PLUS_MARGIN_FEATURES`）。

| グループ | 要素 |
|---|---|
| キャリア・出走間隔 | `career_places`, `recent5_win_rate`, `races_last_180d`, `races_last_365d` |
| 距離・頭数 | `last1_distance`, `current_distance`, `field_size` |
| 相手強度 v1（単純勝率） | `last1〜3_winner_strength`, `last1〜3_field_strength` |
| 相手強度 v2（平滑化） | `last1,2_winner_strength_v2`, `last1〜3_field_strength_v2`, `max/mean/weighted_winner_strength_last3`, `best_strong_opponent_performance_last3`, `last1〜3_field_max_strength_v2`, `last1〜3_field_top3_mean_strength_v2`, `opponent_history_missing_last3` |
| 勝ち馬のクラス・賞金実績 | `last1〜3_winner_max_race_class_before_target`, `last1〜3_winner_best_win_class_before_target`, `last1〜3_winner_max_prize_before_target`, `last1〜3_winner_mean_prize_before_target` |
| 展開・位置取り | `last1〜3_position_advantage`, `setup_improvement` |
| 調整後パフォーマンス | `last1〜3_adjusted_performance`, `best/mean/weighted_adjusted_performance_last3`, `hidden_strength_last1`, `hidden_strength_last3`, `max_hidden_strength_last3`, `strong_against_bias_last1〜3`, `max_strong_against_bias_last3`, `hidden_strength_x_race_strength` |
| 賞金・レース格 | `race_first_prize`, `race_first_prize_log`, `race_total_top5_prize_log`, `last2,3_race_first_prize`, `last1〜3_race_first_prize_log`, `max_race_prize_last3`, `prize_change_from_last1`, `prize_change_from_last3_mean`, `prize_ratio_vs_last1`, `prize_ratio_vs_last3_mean` |
| 勝ち差（圧勝度） | `last1〜5_winning_margin`, `mean_winning_margin_last5`, `max_winning_margin_last5` |
| クラス一致フォーム | `last1〜3_class_matched_adjusted_performance`, `mean_class_matched_adjusted_performance_last3`, `class_matched_sample_count` |
| コース×枠 | `course_gate_win_rate`, `course_gate_place_rate` |

意図的に除外済み:
- `career_win_rate`, `career_races`, `recent3_win_rate`, `recent3_place_rate`
- 生の着差・着順系（adjusted と相関約0.999の重複）
- 騎手系（`jockey_added_value` 等）、`course_geometry_fit`（未実装）

## 2. RACEVERSE（走破性能モデル。本番は `--level pace`）

目的変数は「走破時計 − 出走馬の平均時計」。特徴量はすべてレース内で中心化する。

| 区分 | 要素 |
|---|---|
| 基本5要素 | `ability_c`（Rankerスコア）, `q_c`（抽選した序盤位置）, `slot_c`（グループ内の内外位置）, `q_x_pace`（序盤位置×ペース）, `closing_x_pace`（過去の上がり相対×ペース） |
| 馬場別の能力 | `ability_c_x_going_2/3/4` |
| 本番未使用 | `full` 専用の `closing_c`, `young_c`, `layoff_c`, `weight_c`。`pace_bias` 系（脚質・枠順バイアス `style_*`, `draw_*`, `pace_*_bias`）は検証済みだが本番未採用 |

### ペース生成の特徴（約90項目）
実装: `raceverse/pace_features.py`

- **隊列の構造:** 先行集団の大きさ、逃げ候補数、外先行の圧力、`q_*` の分布など。
- **馬・騎手の過去位置取り:** 逃げ経験、先行率、騎手の先行度・テンポ。
- **Pace Impact:** 実ラップ残差の縮小推定。馬・騎手別。
- **コース条件:** 距離、初角までの距離、開催週・開催日、季節、馬場（芝/ダ・良〜不良）、競馬場。

### その他の部品
- **決着時計モデル（Ridge）:** `track_bias`, `bias_n_eff`, 能力の max/top3/mean/std, `field_size`, `pace`, `pace_sq`, 距離帯との交互作用, 隊列指標。
- **補正:** 騎手変更補正、馬場速度補正、基準時計（コース×クラス×年齢×馬場のRidge）。
- **校正:** 週次再学習、勝率の温度/γ校正。

## 3. 入っていない要素（追加候補）

- オッズ・人気（市場情報）
- 馬体重・増減、斤量、性齢
- 騎手・調教師の成績（Ranker側は除外済み）、血統
- 調教・厩舎コメント
- コース適性（`course_geometry_fit` は未実装）
- 脚質・枠順バイアス（検証済みだが本番未採用）

## 4. 削る候補・注意点

- 近走パフォーマンス系（`adjusted_*`, `hidden_*`, `strong_against_*`, `weighted/mean/best_*`）は相互の相関が非常に高く、同じ情報が重複している。
- 賞金系（`prize_ratio_*`, `prize_change_*`）も高相関。`prize_ratio_vs_last3_mean` は単独除去で改善が再現しなかった。
- 特徴量数の記録が3種類あり食い違っている。
  - 本番 `ranker_production_predict`: 86項目
  - `reports/current_model_report_2026_09/feature_list.md`: 92項目（別構成）
  - `reports/current_model_feature_influence_ranking_2026-09.md`: 104項目（`CLEANUP_B`）
- 条件別でG3・芝1500〜1800m・東京/中山の特定条件が100%超になる例があるが、各30件前後のものが多く、過学習の可能性が高い。得意条件の探索は件数と信頼区間を併記して判断する。

## 5. 参照

- `src/backtest.py`
- `src/ranker_production_predict.py`
- `raceverse/performance.py`
- `raceverse/pace_features.py`
- `raceverse/winning_time_model.py`
- `configs/raceverse_weekly.yaml`
- `reports/raceverse/model_level_features.md`
- `reports/raceverse/market_analysis_5y_202109_202609_no_full/summary.md`
- `reports/raceverse/raceverse_win_roi_conditions_5y_202109_202609_no_full.md`

# 本番Ranker 特徴量カタログ

## 対象範囲

この文書は、`src.ranker_production_predict` が本番予測で使う **86特徴量**を、特徴量名・意味・計算上の注意とともに列挙する。対象セットは `src.backtest.RANKER_MARGIN_CORRECTION_FEATURES`（`CLEANUP_F_PLUS_MARGIN_FEATURES` の別名）。

全特徴量は予測対象レースより前の情報から作る。`last1` は最も直近の過去走、`last2` はその1走前、という順である。過去走が存在しない場合などは、多くの特徴で `0` を代入する。

現行セットは、着順・生の着差・通算勝率や直近3走勝率をそのまま入力せず、能力推定・勝ち着差・相手関係などに置き換える方針で設計されている。ただし `career_places` と `recent5_win_rate` は含まれる。これは特徴量入力の説明であり、各要素の有効性を保証するものではない。

## 1. 出走履歴・稼働状況（4特徴量）

| 特徴量 | 意味 |
|---|---|
| `career_places` | 対象レース前の通算3着以内回数。率ではなく件数。 |
| `recent5_win_rate` | 直近最大5走の勝利割合。過去走が5走未満なら存在する走数で割る。 |
| `races_last_180d` | 直近180日以内の出走回数。 |
| `races_last_365d` | 直近365日以内の出走回数。 |

## 2. 距離・出走頭数（3特徴量）

| 特徴量 | 意味 |
|---|---|
| `last1_distance` | 直近過去走の距離（m）。 |
| `current_distance` | 対象レースの距離（m）。 |
| `field_size` | 対象レースの出走頭数。 |

## 3. 過去走の勝者・相手関係（34特徴量）

`strength` は、過去レースの勝者または出走馬の過去実績から作る能力指標。`v2` は勝率・複勝率を少標本向けに縮約した指標で、未縮約の旧指標とは定義が異なる。いずれも対象レース時点までの過去実績を使う。

| 特徴量 | 意味 |
|---|---|
| `last1_winner_strength` | 直近過去走の勝ち馬が、そのレース時点までに持っていた通算勝率。 |
| `last2_winner_strength` | 2走前の勝ち馬の当時の通算勝率。 |
| `last3_winner_strength` | 3走前の勝ち馬の当時の通算勝率。 |
| `last1_field_strength` | 直近過去走の出走馬について、各馬の当時の通算勝率を平均した値。 |
| `last2_field_strength` | 2走前の出走馬の当時の通算勝率の平均。 |
| `last3_field_strength` | 3走前の出走馬の当時の通算勝率の平均。 |
| `last1_winner_strength_v2` | 直近過去走の勝ち馬の、勝率・複勝率を標本数で縮約した強さ。 |
| `last2_winner_strength_v2` | 2走前の勝ち馬の縮約強さ。 |
| `last1_field_strength_v2` | 直近過去走の出走馬の縮約強さの平均。 |
| `last2_field_strength_v2` | 2走前の出走馬の縮約強さの平均。 |
| `last3_field_strength_v2` | 3走前の出走馬の縮約強さの平均。 |
| `max_winner_strength_last3` | 直近3走の勝ち馬縮約強さの最大値。 |
| `mean_winner_strength_last3` | 直近3走の勝ち馬縮約強さの平均。 |
| `weighted_winner_strength_last3` | 直近3走の勝ち馬縮約強さの加重平均。重みは直近から `0.5, 0.3, 0.2`。 |
| `best_strong_opponent_performance_last3` | 直近3走の「勝ち馬縮約強さ − 当該馬の勝ち馬からの着差」の最大値。 |
| `last1_field_max_strength_v2` | 直近過去走の出走馬中、縮約強さが最大の馬の値。 |
| `last2_field_max_strength_v2` | 2走前の出走馬中、縮約強さが最大の馬の値。 |
| `last3_field_max_strength_v2` | 3走前の出走馬中、縮約強さが最大の馬の値。 |
| `last1_field_top3_mean_strength_v2` | 直近過去走の出走馬から縮約強さ上位3頭を取り、その平均を計算。 |
| `last2_field_top3_mean_strength_v2` | 2走前の出走馬の縮約強さ上位3頭の平均。 |
| `last3_field_top3_mean_strength_v2` | 3走前の出走馬の縮約強さ上位3頭の平均。 |
| `opponent_history_missing_last3` | 直近3走について、勝ち馬・出走馬の強さ情報が得られない過去走数。 |
| `last1_winner_max_race_class_before_target` | 直近過去走の勝ち馬が、対象レース日までに出走したレースの最高クラススコア。 |
| `last2_winner_max_race_class_before_target` | 2走前の勝ち馬の対象日までの最高クラススコア。 |
| `last3_winner_max_race_class_before_target` | 3走前の勝ち馬の対象日までの最高クラススコア。 |
| `last1_winner_best_win_class_before_target` | 直近過去走の勝ち馬が、対象日までに勝利したレースの最高クラススコア。 |
| `last2_winner_best_win_class_before_target` | 2走前の勝ち馬が対象日までに勝利したレースの最高クラススコア。 |
| `last3_winner_best_win_class_before_target` | 3走前の勝ち馬が対象日までに勝利したレースの最高クラススコア。 |
| `last1_winner_max_prize_before_target` | 直近過去走の勝ち馬について、対象日までに出走したレースの1着賞金の最大値。 |
| `last2_winner_max_prize_before_target` | 2走前の勝ち馬について、対象日までに出走したレースの1着賞金の最大値。 |
| `last3_winner_max_prize_before_target` | 3走前の勝ち馬について、対象日までに出走したレースの1着賞金の最大値。 |
| `last1_winner_mean_prize_before_target` | 直近過去走の勝ち馬について、対象日までに出走したレースの1着賞金の平均。 |
| `last2_winner_mean_prize_before_target` | 2走前の勝ち馬について、対象日までに出走したレースの1着賞金の平均。 |
| `last3_winner_mean_prize_before_target` | 3走前の勝ち馬について、対象日までに出走したレースの1着賞金の平均。 |

## 4. 近走パフォーマンス・展開補正（18特徴量）

`adjusted_performance` は着差由来のraw performanceに、クラス・ペース・相手関係の差分を加えた値。高い値ほど良いパフォーマンスを表す。過去走の着差は大差補正後の値を使う。`position_advantage` は過去走の最初のコーナー位置を頭数に対して正規化し、同レース平均との差で表す。

| 特徴量 | 意味 |
|---|---|
| `last1_position_advantage` | 直近過去走の序盤位置の相対的な前後差。 |
| `last2_position_advantage` | 2走前の序盤位置の相対的な前後差。 |
| `last3_position_advantage` | 3走前の序盤位置の相対的な前後差。 |
| `last1_adjusted_performance` | 直近過去走の着差・クラス・ペース・相手関係を反映した能力値。 |
| `last2_adjusted_performance` | 2走前の補正後パフォーマンス。 |
| `last3_adjusted_performance` | 3走前の補正後パフォーマンス。 |
| `best_adjusted_performance_last3` | 直近3走の補正後パフォーマンスの最大値。 |
| `mean_adjusted_performance_last3` | 直近3走の補正後パフォーマンスの平均。 |
| `weighted_adjusted_performance_last3` | 直近3走の補正後パフォーマンスの加重平均。重みは直近から `0.5, 0.3, 0.2`。 |
| `hidden_strength_last1` | 直近過去走の補正量（adjusted performance − raw performance）。 |
| `hidden_strength_last3` | 3走前の補正量。 |
| `max_hidden_strength_last3` | 直近3走の補正量の最大値。 |
| `max_strong_against_bias_last3` | 直近3走のクラス・ペース・相手関係の補正成分合計の最大値。 |
| `strong_against_bias_last1` | 直近過去走のクラス・ペース・相手関係の補正成分合計。 |
| `strong_against_bias_last2` | 2走前の補正成分合計。 |
| `strong_against_bias_last3` | 3走前の補正成分合計。 |
| `setup_improvement` | 直近過去走の `position_advantage` の符号を反転した値。序盤位置がレース平均より後ろだった場合に正側となる。 |
| `hidden_strength_x_race_strength` | 直近過去走の補正量に、同走の勝ち馬縮約強さと対象レースの1着賞金ログ値を組み合わせた相互作用。 |

## 5. 賞金・クラス水準と前走からの変化（13特徴量）

賞金額は円単位に換算される。`log` は `log1p` 変換。対象レースの賞金は出走表から予測前に分かるレース条件であり、結果情報ではない。

| 特徴量 | 意味 |
|---|---|
| `race_first_prize` | 対象レースの1着本賞金。 |
| `race_first_prize_log` | 対象レースの1着本賞金に `log1p` を適用した値。 |
| `race_total_top5_prize_log` | 対象レースの上位5着までの本賞金合計に `log1p` を適用した値。 |
| `last2_race_first_prize` | 2走前のレースの1着本賞金。 |
| `last3_race_first_prize` | 3走前のレースの1着本賞金。 |
| `last1_race_first_prize_log` | 直近過去走の1着本賞金の `log1p`。 |
| `last2_race_first_prize_log` | 2走前の1着本賞金の `log1p`。 |
| `last3_race_first_prize_log` | 3走前の1着本賞金の `log1p`。 |
| `max_race_prize_last3` | 直近3走の1着本賞金の最大値。 |
| `prize_change_from_last1` | 対象レースの1着本賞金 − 直近過去走の1着本賞金。 |
| `prize_change_from_last3_mean` | 対象レースの1着本賞金 − 直近3走の1着本賞金平均。 |
| `prize_ratio_vs_last1` | 対象レースの1着本賞金を直近過去走の1着本賞金と比較した比率。 |
| `prize_ratio_vs_last3_mean` | 対象レースの1着本賞金を直近3走の1着本賞金平均と比較した比率。 |

## 6. 過去の勝ち着差・クラス適合成績（12特徴量）

`winning_margin` はその馬が過去走で勝った場合の、勝ち馬と2着馬の着差。非勝利走や算出できない走りは0として扱う。平均・最大値は、直近5走のうち実際に勝った走りだけを対象にする。

クラス適合パフォーマンスは、対象レースとのクラス帯が近い過去走を優先して直近最大3走を選んだ補正後パフォーマンス。2歳限定・3歳限定条件では通常の直近走を使い、古馬条件では近いクラス帯を使う。該当履歴がない場合は直近走へフォールバックする。

| 特徴量 | 意味 |
|---|---|
| `last1_winning_margin` | 直近過去走で勝利した場合の勝ち着差。非勝利等は0。 |
| `last2_winning_margin` | 2走前で勝利した場合の勝ち着差。非勝利等は0。 |
| `last3_winning_margin` | 3走前で勝利した場合の勝ち着差。非勝利等は0。 |
| `last1_class_matched_adjusted_performance` | クラス適合で選ばれた過去走のうち最も近い走りの補正後パフォーマンス。 |
| `last2_class_matched_adjusted_performance` | クラス適合で選ばれた2番目の走りの補正後パフォーマンス。 |
| `last3_class_matched_adjusted_performance` | クラス適合で選ばれた3番目の走りの補正後パフォーマンス。 |
| `mean_class_matched_adjusted_performance_last3` | クラス適合で選ばれた走りの補正後パフォーマンス平均。 |
| `class_matched_sample_count` | クラス適合で実際に使用した過去走数。最大3。 |
| `last4_winning_margin` | 4走前で勝利した場合の勝ち着差。非勝利等は0。 |
| `last5_winning_margin` | 5走前で勝利した場合の勝ち着差。非勝利等は0。 |
| `mean_winning_margin_last5` | 直近5走のうち勝利した走りの勝ち着差平均。勝利履歴なしは0。 |
| `max_winning_margin_last5` | 直近5走のうち勝利した走りの勝ち着差最大値。勝利履歴なしは0。 |

## 7. コース・枠番の事前成績（2特徴量）

| 特徴量 | 意味 |
|---|---|
| `course_gate_win_rate` | 対象レースより前の結果から集計した「競馬場 × 芝/ダート × 距離帯 × 枠番」の勝率。該当履歴なしは0。 |
| `course_gate_place_rate` | 同じ条件の過去出走における3着以内率。該当履歴なしは0。 |

## 件数の確認

意味別の件数は 4 + 3 + 34 + 18 + 13 + 12 + 2 = **86特徴量**。完全リストは本番コードの `RANKER_MARGIN_CORRECTION_FEATURES` から取得した順序と照合している。

## 完全リスト（本番コード順）

以下はコードが定義する順序であり、上の意味別セクションとは並びが異なる。

```text
career_places
recent5_win_rate
races_last_180d
races_last_365d
last1_winner_strength
last2_winner_strength
last3_winner_strength
last1_field_strength
last2_field_strength
last3_field_strength
last1_distance
current_distance
field_size
last1_winner_strength_v2
last2_winner_strength_v2
last1_field_strength_v2
last2_field_strength_v2
last3_field_strength_v2
max_winner_strength_last3
mean_winner_strength_last3
weighted_winner_strength_last3
best_strong_opponent_performance_last3
last1_field_max_strength_v2
last2_field_max_strength_v2
last3_field_max_strength_v2
last1_field_top3_mean_strength_v2
last2_field_top3_mean_strength_v2
last3_field_top3_mean_strength_v2
opponent_history_missing_last3
last1_winner_max_race_class_before_target
last2_winner_max_race_class_before_target
last3_winner_max_race_class_before_target
last1_winner_best_win_class_before_target
last2_winner_best_win_class_before_target
last3_winner_best_win_class_before_target
last1_winner_max_prize_before_target
last2_winner_max_prize_before_target
last3_winner_max_prize_before_target
last1_winner_mean_prize_before_target
last2_winner_mean_prize_before_target
last3_winner_mean_prize_before_target
last1_position_advantage
last2_position_advantage
last3_position_advantage
last1_adjusted_performance
last2_adjusted_performance
last3_adjusted_performance
best_adjusted_performance_last3
mean_adjusted_performance_last3
weighted_adjusted_performance_last3
hidden_strength_last1
hidden_strength_last3
max_hidden_strength_last3
max_strong_against_bias_last3
strong_against_bias_last1
strong_against_bias_last2
strong_against_bias_last3
setup_improvement
hidden_strength_x_race_strength
race_first_prize
race_first_prize_log
race_total_top5_prize_log
last2_race_first_prize
last3_race_first_prize
last1_race_first_prize_log
last2_race_first_prize_log
last3_race_first_prize_log
max_race_prize_last3
prize_change_from_last1
prize_change_from_last3_mean
prize_ratio_vs_last1
prize_ratio_vs_last3_mean
last1_winning_margin
last2_winning_margin
last3_winning_margin
last1_class_matched_adjusted_performance
last2_class_matched_adjusted_performance
last3_class_matched_adjusted_performance
mean_class_matched_adjusted_performance_last3
class_matched_sample_count
last4_winning_margin
last5_winning_margin
mean_winning_margin_last5
max_winning_margin_last5
course_gate_win_rate
course_gate_place_rate
```

## 入力されない関連項目

以下は特徴量生成時に存在しても、本番86特徴量には含まれない。

- 着順・生着差: `last1_finish`〜`last3_finish`、`last1_margin`〜`last3_margin`、margin集約値
- 結果率: `career_win_rate`、`career_races`、`career_place_rate`、`recent3_win_rate`、`recent3_place_rate`
- 枠バイアスの補助統計: `course_gate_sample_count`、`course_gate_win_rate_shrink`
- 過去走の賞金・着順以外の多数の生成済み列（騎手・血統・適性・コース形状など）

これらの除外は現在の特徴量セットの仕様であって、将来の有効性や無効性を決める結論ではない。

## 前処理とモデルへの入力

- 学習・評価時に特徴量列を明示し、数値化できない値は欠損として処理する。
- 数値欠損は学習データ列ごとの中央値で補完し、中央値も得られない場合は0にする。
- 本番86特徴量は数値特徴量であり、学習データの平均・標準偏差を使った標準化後にLightGBM Rankerへ渡す。
- 学習はレース単位のLambdaRank。各レースの確定着順からrelevanceを作る。
- Rankerスコアは、直前の過去期間で選んだ温度によるレース内softmaxで勝率へ変換する。
- 特徴量の実装定義は [backtest.py](../src/backtest.py)、本番利用箇所は [ranker_production_predict.py](../src/ranker_production_predict.py)、前処理・学習・校正は [ranker_walk_forward_backtest.py](../src/ranker_walk_forward_backtest.py)。

## 注記

- 意味説明は現行実装の特徴量定義を要約したもの。特徴量名だけから意味を推測したものではない。
- `course_gate_win_rate` / `course_gate_place_rate` は記述上、同一条件の過去成績率であり、実装では `course_gate_win_rate` の縮約版とは異なり縮約されない率を使う。履歴の薄い条件では0や不安定な値になり得る。
- 本番Rankerの勝率性能と、RACEVERSEで評価する相対走破時計性能は異なる目的変数・モデルである。RACEVERSEの特徴量一覧は [model_level_features.md](../raceverse/model_level_features.md) を参照。

## 実験用の新規4特徴量群

本番86特徴量は変更せず、`src.ranker_new_feature_groups` が実験用列と16構成を管理する。
特徴量は `build_v1_features` が対象レースの前日までに確定している履歴だけから生成する。
血統列（`sire`、`damsire` およびその派生列）は4群に含めない。

| 群 | 主な内容 |
|---|---|
| G1 | 競馬場、距離帯、競馬場×距離帯の補正後パフォーマンス、距離変更、経験数 |
| G2 | 芝・ダート、馬場状態の補正後パフォーマンス、走路変更、経験数 |
| G3 | 騎手全体・直近成績、騎手×馬、騎手×今回条件の補正後パフォーマンス、経験数 |
| G4 | 直近5走の補正後パフォーマンス傾向、平均との差、変動、ピーク差、馬齢・休養との相互作用、信頼度 |

各列の完全な定義、欠損率、分布は
`python -m src.ranker_new_feature_ablation` 実行時に
`reports/ranker_new_feature_ablation/feature_quality.csv` として出力する。
同コマンドはBaselineを含む16構成を、既存の月次Walk-Forward・3か月温度校正で再学習し、
`configuration_results.csv` / `.md` と構成別の月次結果を保存する。

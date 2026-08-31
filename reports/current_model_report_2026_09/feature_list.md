# 現行モデルの特徴量一覧（92項目）

対象モデル: `src/ranker_cleanup_e_no_place_rate_analysis.py` で検証済みの最新構成。
`CLEANUP_B_FEATURES`（`src/backtest.py`）から重複特徴量（`DEDUP_MARGIN_FEATURES`）と
`career_win_rate`/`career_races`（`CAREER_COUNT_FEATURES`）を除去し、
勝ち差・クラス一致フォーム特徴量（`WINNING_MARGIN_FEATURES` + `CLASS_MATCHED_FORM_FEATURES`）を追加、
さらに単独Gain首位だった `recent3_place_rate` を除外した92特徴量構成。
学習器は LightGBM の `LGBMRanker`（lambdarank）で、月次拡張ウィンドウ（walk-forward）で再学習する。

すべて「対象レース当日より前に確定した情報」のみから計算され、対象レース自身の結果・払戻・確定着順は使用しない
（`src/backtest.py` の `build_v1_features` 内で、当該日付の全レース処理が終わるまで馬ごとの履歴を更新しない設計）。

## 基礎キャリア成績

| 特徴量 | 説明 |
|---|---|
| `career_wins` | 対象レース以前の通算勝利数 |
| `career_places` | 対象レース以前の通算複勝内（3着以内）回数 |
| `recent3_win_rate` | 直近3走の勝率（0/1の平均） |
| `recent5_win_rate` | 直近5走の勝率 |
| `races_last_180d` | 過去180日以内の出走数 |
| `races_last_365d` | 過去365日以内の出走数 |

## 直近レースの距離・出走頭数

| 特徴量 | 説明 |
|---|---|
| `last1_distance` / `last2_distance` / `last3_distance` | 直近1〜3走のレース距離(m) |
| `current_distance` | 今回のレース距離(m) |
| `field_size` | 今回の出走頭数 |

## 対戦相手・勝ち馬の強さ（v1: 単純勝率ベース）

| 特徴量 | 説明 |
|---|---|
| `last1_winner_strength` / `last2` / `last3` | 直近1〜3走で、そのレースの勝ち馬が対象日以前に持っていた通算勝率 |
| `last1_field_strength` / `last2` / `last3` | 直近1〜3走時点の出走メンバー全体の平均通算勝率（対戦相手の強さ） |

## 対戦相手・勝ち馬の強さ（v2: 少標本を縮約した平滑化強度）

`smoothed_strength()`（`src/backtest.py`）は勝率0.6・複勝率0.4を出走数に応じた信頼度で重み付けした連続値。

| 特徴量 | 説明 |
|---|---|
| `last1_winner_strength_v2` / `last2` / `last3` | 直近1〜3走の勝ち馬の平滑化強度 |
| `last1_field_strength_v2` / `last2` / `last3` | 直近1〜3走時点のフィールド平均平滑化強度 |
| `max_winner_strength_last3` | 直近3走の勝ち馬強度(v2)の最大値 |
| `mean_winner_strength_last3` | 直近3走の勝ち馬強度(v2)の平均値 |
| `weighted_winner_strength_last3` | 直近3走を(0.5, 0.3, 0.2)で加重平均した勝ち馬強度(v2) |
| `best_strong_opponent_performance_last3` | 直近3走で「勝ち馬強度(v2) − 着差」が最大だった値。強い相手にわずかな着差で負けた実績を評価 |
| `last1_field_max_strength_v2` / `last2` / `last3` | 直近1〜3走時点のフィールド内最大の平滑化強度 |
| `last1_field_top3_mean_strength_v2` / `last2` / `last3` | 直近1〜3走時点のフィールド上位3頭平均の平滑化強度 |
| `opponent_history_missing_last3` | 直近3走のうち、勝ち馬・フィールド強度が両方0（履歴なし）だった件数 |

## 勝ち馬のクラス・賞金実績（対象レース以前の情報のみ）

| 特徴量 | 説明 |
|---|---|
| `last1_winner_max_race_class_before_target` / `last2` / `last3` | 直近1〜3走の勝ち馬が対象レース以前に記録した最高クラススコア |
| `last1_winner_best_win_class_before_target` / `last2` / `last3` | 同、勝ち馬が「勝利した」レースの中での最高クラススコア |
| `last1_winner_max_prize_before_target` / `last2` / `last3` | 直近1〜3走の勝ち馬が過去に記録した最大の1着賞金 |
| `last1_winner_mean_prize_before_target` / `last2` / `last3` | 同、平均1着賞金 |

## 展開・ポジション優位性

| 特徴量 | 説明 |
|---|---|
| `last1_position_advantage` / `last2` / `last3` | 直近1〜3走時点で、その馬の前方位置指数(frontness)がフィールド平均よりどれだけ高かったか |
| `setup_improvement` | 直近1走の`position_advantage`の符号反転。展開の向き・反動を表す |

## 調整後パフォーマンス（着差＋クラス差＋展開差＋相手差）

`performance_from_result()` が raw performance（着差のマイナス値）にクラス差・展開差・相手差の重み付き合計を加えて算出。

| 特徴量 | 説明 |
|---|---|
| `last1_adjusted_performance` / `last2` / `last3` | 直近1〜3走の調整後パフォーマンス |
| `best_adjusted_performance_last3` | 直近3走の調整後パフォーマンスの最大値 |
| `mean_adjusted_performance_last3` | 直近3走の調整後パフォーマンスの平均値 |
| `weighted_adjusted_performance_last3` | 直近3走を(0.5, 0.3, 0.2)で加重平均した調整後パフォーマンス |
| `hidden_strength_last1` / `last2` / `last3` | 調整後パフォーマンス − raw performance。着差だけでは見えないクラス・展開・相手による補正分（"隠れた強さ"） |
| `max_hidden_strength_last3` | 直近3走の隠れた強さの最大値 |
| `strong_against_bias_last1` / `last2` / `last3` | クラス差・展開差・相手差の合計（着差を含まない）。強い相手・展開不利下での実績を表す |
| `max_strong_against_bias_last3` | 直近3走の上記の最大値 |
| `hidden_strength_x_race_strength` | `hidden_strength_last1` と（勝ち馬強度v2＋賞金log/20）の積。隠れた強さと今回のレース格の交互作用 |

## 賞金ベースのレース格（クラス代替指標）

`prize_class_score()` により1着賞金をlog1pで連続値化（賞金がない場合はグレードコードで代替）。

| 特徴量 | 説明 |
|---|---|
| `race_first_prize` / `race_second_prize` / `race_third_prize` | 今回のレースの1〜3着賞金（円） |
| `race_total_top5_prize` | 今回のレースの上位5着賞金合計（円） |
| `race_first_prize_log` / `race_total_top5_prize_log` | 上記のlog1p変換値 |
| `last1_race_first_prize` / `last2` / `last3` | 直近1〜3走のレースの1着賞金 |
| `last1_race_first_prize_log` / `last2` / `last3` | 同log1p変換値 |
| `max_race_prize_last3` / `mean_race_prize_last3` | 直近3走の1着賞金の最大・平均 |
| `weighted_race_prize_last3` | 直近3走を(0.5, 0.3, 0.2)で加重平均した1着賞金 |
| `prize_change_from_last1` | 今回の1着賞金 − 直近1走の1着賞金 |
| `prize_change_from_last3_mean` | 今回の1着賞金 − 直近3走平均1着賞金 |
| `prize_ratio_vs_last1` | 今回の1着賞金 ÷ 直近1走の1着賞金 |
| `prize_ratio_vs_last3_mean` | 今回の1着賞金 ÷ 直近3走平均1着賞金 |

## 勝ち差・クラス一致フォーム（CLEANUP_E追加分）

| 特徴量 | 説明 |
|---|---|
| `last1_winning_margin` / `last2` / `last3` | 直近1〜3走で自身が勝利していた場合の、2着馬との着差（圧勝度）。勝っていない場合は0 |
| `last1_class_matched_adjusted_performance` / `last2` / `last3` | 現在のレースとクラス階層（±1）が近い過去レースに限定した調整後パフォーマンス（2歳・3歳限定戦は単純な直近順、初の古馬混合戦は過去の重賞実績も加味） |
| `mean_class_matched_adjusted_performance_last3` | 上記の直近3走平均 |
| `class_matched_sample_count` | クラス一致条件でマッチした過去レース数 |

## 除外・不使用の特徴量（参考）

- `recent3_place_rate`: CLEANUP_Eモデルで単独Gain比率18.95%（最大）だったため、依存度検証のため本構成では除外。
- `career_win_rate` / `career_races`: 賞金ベースのクラススコアが経験量シグナルを代替するとの設計判断により除外（`CAREER_COUNT_FEATURES`）。
- raw margin系・`last*_raw_performance`・`margin_x_*`: adjusted_performanceと相関約0.999のため重複削減（`DEDUP_MARGIN_FEATURES`）。
- `jockey_added_value` 等の騎手系特徴量、`course_geometry_fit`: レビュー中／計算未実装のため本構成には含まれない。

## モデル構成・評価条件

- 学習器: LightGBM `LGBMRanker`（`objective=lambdarank`, `metric=ndcg`, `n_estimators=180`, `learning_rate=0.04`, `num_leaves=15`, `max_depth=5`, `min_child_samples=80`, `reg_lambda=2.0`, `random_state=42`）
- 評価対象: 1着賞金が800万円を超えるレースのみ（`race_first_prize > 8,000,000`）、オッズ・確定着順が有効な行のみ
- 再学習: 月次拡張ウィンドウ（各予測月の初日より前の全データで学習）
- 確率較正: 予測月の直前3ヶ月をキャリブレーション期間とし、そのブライアスコアが最小になる温度(temperature)でsoftmax確率化
- リーク対策: 対象レース自身の結果・払戻・確定着順・当日以降の情報は特徴量に含まれない

# 現行特徴量一覧

対象: Model D / E / F / G のバックテスト特徴量。Model D/E/F/Gのcache・feature listを照合した研究用一覧。

## 1. Base Ability

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `career_races` | 対象日までの通算出走数 | 残す |
| `career_wins` | 通算勝利数 | 残す |
| `career_win_rate` | 通算勝率 | 残す。少標本注意 |
| `career_places` | 通算3着以内数 | 残す |
| `career_place_rate` | 通算複勝率 | 残す |
| `recent3_win_rate` / `recent5_win_rate` | 直近3/5走勝率 | 残す |
| `recent3_place_rate` / `recent5_place_rate` | 直近3/5走複勝率 | 残す。重要度高め |
| `races_last_180d` / `races_last_365d` | 直近期間の出走数 | 残す |

## 2. 近走結果・着差

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `last1_finish` ～ `last3_finish` | 直近3走の着順 | 残す。重要度高め |
| `last1_margin` ～ `last3_margin` | 勝ち馬との着差 | 残す |
| `best_margin_last3` | 直近3走の最小着差 | 残す |
| `mean_margin_last3` | 直近3走の平均着差 | 残す |
| `weighted_margin_last3` | 前走0.5、2走前0.3、3走前0.2の着差 | 残す。重複検証 |
| `last1_distance` ～ `last3_distance` | 直近3走の距離 | 残す |
| `current_distance` | 今回の距離 | 残す |
| `field_size` | 今回の出走頭数 | 残す |

## 3. Race Class / Condition

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `race_class_label` | G1/G2/G3/Listed等の名目格ラベル | 残す。ただしUNKNOWN率高い |
| `race_class_score` / `current_race_class_score` | 名目格の順序スコア | 残す。固定強度とは解釈しない |
| `last1_race_class` ～ `last3_race_class` | 直近3走の格ラベル | 残す |
| `last1_race_class_score` ～ `last3_race_class_score` | 直近3走の格スコア | 残す |
| `max_race_class_last3` | 直近3走の最高格 | 残す |
| `mean_race_class_last3` | 直近3走の平均格 | 残す |
| `weighted_race_class_last3` | 直近走を重くした格平均 | 残す。重複検証 |
| `last1_margin_x_race_class` ～ `last3_margin_x_race_class` | 着差と名目格の積 | 残すが過学習確認 |
| `race_sex_condition` / `is_filly_mare_only` | 牝馬限定等の条件 | 現在UNKNOWN/簡易判定が多い。要検証 |
| `race_age_condition` / `is_2yo_only` / `is_3yo_only` | 年齢条件 | 残す。欠損率確認 |
| `last1_sex_condition` ～ `last3_sex_condition` | 過去3走の性別条件 | UNKNOWNが多ければ削除候補 |
| `last1_age_condition` ～ `last3_age_condition` | 過去3走の年齢条件 | 残すが情報量確認 |
| `race_class_change` | 前走から今回の格スコア差 | 残す |
| `female_only_to_open` / `open_to_female_only` | 性別条件の変化 | 現在0が多い可能性。分布確認後判断 |
| `age_condition_change` | 年齢条件の変化 | 残すが小サンプル注意 |
| `grade_code` / `condition_code` | DB生コード | 生コードの意味が不明なら削除候補。UNKNOWNカテゴリ依存に注意 |
| `last1_class` ～ `last3_class` | 旧形式の生コード結合 | `last*_race_class`と重複。ABで削除候補 |

## 4. Winner / Field Strength

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `last1_winner_strength` ～ `last3_winner_strength` | 過去レース勝ち馬の強さ | 残す |
| `last1_field_strength` ～ `last3_field_strength` | 過去レース全体の強さ | 残す |
| `margin_x_winner_strength` / `margin_x_field_strength` | 着差と相手強度の積 | 残す。重複確認 |
| `*_winner_strength_v2` | 平滑化勝率・複勝率ベースの相手強度 | 残す |
| `*_field_strength_v2` | 平滑化されたメンバー強度 | 残す |
| `*_field_max_strength_v2` | 過去レース出走馬の最大強度 | 残す |
| `*_field_top3_mean_strength_v2` | 過去レース上位3頭の平均強度 | 残す |
| `best_strong_opponent_performance_last3` | 強い相手との内容を集約 | 残す。重要候補 |
| `opponent_history_missing_last3` | 相手履歴不足フラグ | 残す。情報欠損と能力を分離 |
| `last*_winner_max_race_class_before_target` | 勝ち馬の対象日前最高格 | 残す |
| `last*_winner_best_win_class_before_target` | 勝ち馬の対象日前最高勝利格 | 残す |
| `last*_winner_max_prize_before_target` | 勝ち馬の過去最高設定賞金 | 残す |
| `last*_winner_mean_prize_before_target` | 勝ち馬の過去平均設定賞金 | 残す。少標本注意 |

## 5. Prize Strength

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `race_first_prize` | 今回レースの1着設定賞金 | 残す |
| `race_second_prize` / `race_third_prize` | 2/3着設定賞金 | 残すがfirstとの重複確認 |
| `race_total_top5_prize` | 1～5着設定賞金合計 | 残す |
| `race_first_prize_log` / `race_total_top5_prize_log` | 賞金のlog1p変換 | rawとAB比較 |
| `last1_race_first_prize` ～ `last3_race_first_prize` | 過去3走の1着設定賞金 | 残す |
| `last*_race_first_prize_log` | 過去賞金の対数 | rawと同時投入はAB候補 |
| `max_race_prize_last3` | 直近3走の最高賞金 | 残す |
| `mean_race_prize_last3` | 直近3走の平均賞金 | 残す |
| `weighted_race_prize_last3` | 前走を重くした賞金平均 | 残す |
| `prize_change_from_last1` | 今回と前走の賞金差 | 残す |
| `prize_change_from_last3_mean` | 今回と直近3走平均の賞金差 | 残す |
| `prize_ratio_vs_last1` / `prize_ratio_vs_last3_mean` | 賞金水準の比率 | 残す。外れ値clip候補 |
| `last1_margin_x_prize_strength` ～ `last3_margin_x_prize_strength` | 着差と賞金強度の積 | 残すが重複確認 |

## 6. Past Adjusted Performance / Pace

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `last*_raw_performance` | 着順・着差・相手・賞金の補正前評価 | 残す |
| `last*_position_advantage` | 過去レースで前方/後方にいた度合い | 残す |
| `last*_adjusted_performance` | 展開補正後の過去走評価 | 残す |
| `best/mean/weighted_adjusted_performance_last3` | 補正後評価の最大/平均/重み付き平均 | 残す |
| `hidden_strength_last1` ～ `last3` | adjusted - raw | 残すが定義を再検証 |
| `max_hidden_strength_last3` | 直近3走の最大hidden strength | 残す。穴馬候補 |
| `strong_against_bias_last1` ～ `last3` | 展開に逆らった度合い | 残す |
| `max_strong_against_bias_last3` | 展開不利克服の最大値 | 残す |
| `race_position_bias_last1` ～ `last3` | 過去レースの位置取り傾向 | 残す |
| `setup_improvement` | 前走不利が今回解消する簡易指標 | 残すが現状簡易版 |
| `hidden_strength_x_race_strength` | hidden strengthとレース強度の積 | 残す。過学習確認 |

## 7. Course / Situation

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `racecourse` | 今回競馬場カテゴリ | 残す |
| `surface` | 芝/ダート | 残す |
| `course_first_corner_distance_m` | スタートから1角までの距離 | 残す。CSV由来 |
| `course_elevation_difference_m` | コース高低差 | 残す。補完値フラグ併用 |
| `course_final_straight_m` | 最終直線長 | 残す |
| `course_start_uphill/downhill` | スタート直後の坂フラグ | 残す |
| `course_final_uphill/downhill` | 最終直線の坂フラグ | 残す |
| `course_final_steep_hill` | 急坂フラグ | 残す |
| `course_rolling_terrain` / `course_mostly_flat` | 起伏/平坦フラグ | 残すが相関確認 |
| `course_gentle_corners` / `course_tight_corners` | コーナー形状フラグ | 残すが相関確認 |
| `course_up_down_transition_sentence_count` | 起伏変化記述数 | 情報量が薄ければ削除候補 |
| `course_geometry_fit` | 過去同一geometryでのadjusted performance | 残す。ただしキャッシュ計算確認 |
| `horse_expected_position` | 過去位置取りからの期待前方度 | 残す |
| `position_stability` | 位置取りのばらつき | 残す |
| `frontness_mean/std` | 平均前方度とばらつき | `horse_expected_position`と重複。AB候補 |
| `front_density` / `forward_density` / `mid_density` / `rear_density` | 今回メンバーの位置取り構成 | 残す |
| `expected_front_count` | 前方型馬の頭数 | 残す |
| `expected_position_mean/std` | メンバー位置分布 | 残す |
| `gate_position_pct` | 馬番の相対位置 | 残す。枠順そのものの固定補正ではない |
| `gate_x_expected_position` | 枠と位置取りの積 | 残すが重複確認 |

## 8. Model G追加

| 特徴量 | 一言説明 | 判断 |
|---|---|---|
| `position_bias_top5_v2` | 上位5頭ベースの位置bias | 残す候補 |
| `position_bias_top6_v2` | 上位6頭ベースの位置bias | 残す候補 |
| `position_bias_weighted_top6_v2` | 上位6頭を着順重み付けしたbias | 残す候補 |
| `position_bias_residual_v2` | 事前能力順位と実着順の残差を使ったbias | 重要候補。リーク確認必須 |
| `strong_against_bias_v2_last1`～`last3` | V2展開逆行度 | 残す候補 |
| `setup_benefit_last1`～`last3` | 過去レースで展開に恵まれた度合い | 残す。過大評価防止 |
| `adjusted_performance_v2_last1`～`last3` | V2展開補正後performance | 残す候補 |
| `mean/best/weighted_adjusted_performance_v2_last3` | V2補正後評価集約 | 残す候補 |
| `max_strong_against_bias_v2_last3` | 強烈な展開不利克服の最大値 | 残す候補 |
| `jockey_rides` | 対象日前の騎乗数 | 残す |
| `jockey_win_rate` | 平滑化した騎手勝率 | 残す。Added Valueと比較 |
| `jockey_top2_rate` | 平滑化した騎手連対率 | 残す |
| `jockey_place_rate` | 平滑化した騎手複勝率 | 残す |
| `jockey_added_value` | 事前能力順位と実着順の過去残差平均 | 残す候補。時系列確認必須 |
| `recent_jockey_added_value` | 直近騎乗のAdded Value平均 | 残す候補 |
| `jockey_form_trend` | 長期と最近の差 | 現在は0固定。学習から除外 |
| `jockey_change_added_value` | 前走騎手との差 | 現在は0固定。学習から除外 |

## 除外を優先検討する列

1. `jockey_form_trend`, `jockey_change_added_value`: 現在0固定で情報がない。
2. `race_sex_condition` 系: UNKNOWN率が高い場合はモデル投入効果を確認してから削除。
3. `last*_class` と `last*_race_class`: 生コードと意味付きカテゴリの重複。
4. raw賞金とlog賞金の同時投入: Feature Group Ablationでどちらが有効か確認。
5. `frontness_mean/std` と `horse_expected_position/position_stability`: 同じ位置履歴を表すため重複候補。
6. `course_up_down_transition_sentence_count`: 実質的な変動が少なければ削除。

## 学習禁止・分析専用

- `actual_rank`, `target`, `is_win`, `is_place`
- `KakuteiJyuni`, `TimeDiff`, `Jyuni1c` など今回レース結果由来の列
- `win_payout`, `place_payout`, 払戻
- `Odds`, `Ninki`: Model D/E/F/Gの能力特徴量には入れず、評価・市場比較だけで使用

## 注意

現在のModel F/Gのfeature listには、計算値が0固定またはUNKNOWNの列も含まれます。削除判断は、まず `variance`, `missing/unknown rate`, `feature importance`, `Model E/F/GのAB結果`, `Anchor/穴馬指標` の4点で行うべきです。

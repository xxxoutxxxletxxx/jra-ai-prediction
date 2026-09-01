# 旧netkeiba版特徴量の復元 監査 & Phase A 結果

## 0. 監査範囲
対象コード: [src/backtest.py](../src/backtest.py) (`build_v1_features`, `evaluate_stage`, モデル A〜I, CA/CB, G)。
現行のモデルGは `data/output/course_features_ver6.csv` のコース形状(勾配・コーナー・直線長)、賞金ベースのクラススコア、
`adjusted_performance`(着差 + クラス差 + ペース差 + 相手強度差)を中心に、着差・相手強度・クラス・賞金の縦方向の情報を
かなり厚く実装している。旧netkeiba版が持っていた「馬自身の独立要因」は下表の通り一部欠落している。

## 1. 既存 / 部分存在 / 未実装マトリクス

| カテゴリ | 状態 | 根拠 |
|---|---|---|
| 年齢(age) | **未実装(学習特徴量として)** | `Barei` はDBから読み込み済み(出力列のみ)。`values` 辞書のどの特徴量リストにも `age` は存在しなかった。Phase Aで追加。 |
| 斤量(carried_weight) | **未実装(生値として)** | `Futan` は `carried_weight_fit`(残差フィット)としてのみ使用。生の斤量そのものは特徴量化されていなかった。Phase Aで追加。 |
| 馬の基本勝率・複勝率・出走数 | **一部存在** | `career_win_rate`, `career_place_rate`, `career_races` は存在するが、CLEANUP_D以降 `career_win_rate`/`career_races` はモデルG系列から除外済み(設計判断)。要望の `horse_win_rate`/`horse_place_rate`/`horse_race_count` という名前としては未実装のため、別名で追加。 |
| 頭数補正平均着順(horse_normalized_mean_finish) | **未実装** | `last1_finish`等の直近着順はあるが、全履歴平均・頭数補正平均は無し。Phase Aで追加。 |
| 末脚(closing speed, HaronTimeL3正規化) | **未実装** | `HaronTimeL3`/`HaronTimeL4` はDBから読み込まれ`LEAK_COLUMNS`に列挙されているが、過去走の末脚として`build_v1_features`内で一度も参照されていない(grep 0件)。既存の`raw_performance`/`adjusted_performance`は着差(TimeDiff)ベースであり上がり3Fとは別概念。**Phase Bで新規実装が必要**。 |
| 位置取り(コーナー通過順の正規化) | **部分存在** | `Jyuni1c`(第1コーナー)のみを使い `frontness`/`horse_expected_position`/`position_stability`を算出。`Jyuni2c`〜`Jyuni4c`(道中〜直線前)は読み込まれているが未使用。「最初に取得可能な位置」と「最後に取得可能な位置」を分ける実装は無い。**Phase Bで拡張が必要**。 |
| 位置取り×末脚 | **未実装** | `hidden_strength`/`strong_against_bias_v2`はadjusted_performanceベースの別概念。`frontness * closing_speed`のような直接合成は無い。**Phase Bで新規実装が必要**。 |
| 距離適性 | **存在(フィット形式)** | `distance_change_fit`(距離変化への感応度)。旧版の「距離帯ごとの過去実績」とは定義が異なるが目的は重複。Phase Cで新設する場合は重複確認必須。 |
| 芝ダート適性 | **未実装** | `surface_fit`という名称は存在しない。`surface`はカテゴリカル特徴量としてのみ投入され、馬ごとの芝/ダート別実績は無い。 |
| 馬場適性 | **存在(フィット形式)** | `track_condition_fit`。 |
| 休養間隔適性 | **存在(フィット形式)** | `race_interval_fit`。 |
| 枠適性(馬自身) | **存在(フィット形式)** | `draw_bias`。 |
| コース×枠 勝率/複勝率 | **未実装(近似のみ)** | `rail_course_bias_fit`はfit残差であり、要望の「コース×surface×distance×gateの実測勝率/複勝率テーブル」ではない。**Phase Dで新規実装が必要**。 |
| 坂適性(horse×geometry) | **存在(fit形式)** | `course_shape_fit`(コース形状距離への近傍フィット)。旧版`place_slope_score`とは変数構成が異なるが目的は重複。 |
| コーナー適性(horse×geometry) | **部分存在** | `course_gentle_corners`/`course_tight_corners`はコース側のフラグのみで、馬側のinteractionとしては`course_shape_fit`に暗黙的に含まれる。明示的な`horse_corner_aptitude`は無い。 |
| 騎手能力 | **存在** | `jockey_win_rate`, `jockey_top2_rate`, `jockey_place_rate`, `jockey_added_value`, `recent_jockey_added_value`。ただし`career_win_rate`同様に一部除外されたモデルもある。要望の`jockey_race_count`/`jockey_mean_finish`/`jockey_normalized_mean_finish`は未実装。 |
| 調教師能力 | **未実装** | `ChokyoCode`はDBから読み込み・出力列にはあるが、`trainer_win_rate`等の学習特徴量は皆無。 |
| 馬×騎手 | **未実装** | 組み合わせ特徴量は無い。 |
| 血統(父・母父) | **未実装** | `Ketto3Info*`/`HansyokuNum*`はDBに存在するがロード対象外・特徴量化なし。 |
| 馬体重履歴 | **未実装** | `BaTaijyu`はDBから読み込まれるが特徴量には一切使われていない。当日馬体重は使用しない方針は現行コードと一致。 |

## 2. Phase A 実装内容(今回実施)
`src/backtest.py` に以下を追加した。

- `age`: `Barei` をそのまま数値化。
- `carried_weight`: `Futan`(既存の`weight`変数を再利用)。
- `horse_win_rate` / `horse_place_rate` / `horse_race_count`: 対象レース以前の確定結果のみで累積した `stats[horse]` から算出(既存`career_*`と同じ集計元だが、削除・整理されたモデル系列に依存しないよう独立名で追加)。
- `horse_mean_finish`: 対象レース以前の着順合計 ÷ 出走数(`stats[horse]["finish_sum"]`を新設)。履歴が無い場合は0.0。
- `horse_normalized_mean_finish`: `(着順-1)/(出走頭数-1)` を対象レース以前の全履歴で平均(`stats[horse]["normalized_finish_sum"]`を新設)。履歴が無い場合は0.5(中立値)。

すべて`shift`相当のロジック(対象レースの結果は月末バッチ更新まで`stats`へ反映しない`pending_updates`機構)をそのまま利用しており、対象レース自身の結果は含まれない。

新モデルラベル `RA` (`--model RA`) = モデルG特徴量一式 + 上記7特徴量。`REBUILD_A`系列と混同しないよう`NETKEIBA_PHASE_A_FEATURES`定数として独立管理した。

## 3. 実行方法
```bash
PHASE5_PROFILE=1 python3 -m src.backtest --model G  --start-month 2026-07 --end-month 2026-09 --out reports/old_feature_rebuild/phase_A/baseline_G
PHASE5_PROFILE=1 python3 -m src.backtest --model RA --start-month 2026-07 --end-month 2026-09 --out reports/old_feature_rebuild/phase_A/plus_basic_RA
```

## 4. Phase A 結果(2026-07〜2026-09, 432レース, walk-forward月次学習)

| 指標 | baseline G | +Phase A (RA) | 差分 |
|---|---:|---:|---:|
| LogLoss | 0.2448 | 0.2393 | ▼改善 |
| Brier Score | 0.0670 | 0.0661 | ▼改善 |
| ROC-AUC | 0.7440 | 0.7639 | ▲改善 |
| Top1的中率 | 25.23% | 23.61% | ▼悪化 |
| Top3的中率 | 57.18% | 59.49% | ▲改善 |
| 単勝ROI | 69.7% | 63.9% | ▼悪化 |
| 複勝ROI | 78.2% | 71.7% | ▼悪化 |
| Spearman(AI順位 vs 人気順位) | 0.7656 | 0.8016 | ▲市場と一致度が上昇(悪化方向) |

**Feature importance(gain, RAモデル)**: `horse_normalized_mean_finish`が全特徴量中3位の重要度(170,675)、`horse_mean_finish`は9位(26,099)、`age`は16位(17,494)、
`carried_weight`は20位(11,355)。一方 `horse_win_rate`/`horse_place_rate`/`horse_race_count` は **gain=0、split=0**(既存の`career_win_rate`/`career_place_rate`/`career_races`と定義が重複し、LightGBMが片方のみ採用したため)。

**結論・判断**:
- AUC/LogLossは改善したが、Top1的中率・単勝/複勝ROIはいずれも悪化し、AI予測と市場人気(オッズ人気)の順位相関(Spearman)はさらに市場寄りに上昇した。これは第19項で懸念していた「AUCだけ上がって市場と似た予測になる」パターンに該当する。
- 評価対象は2ヶ月・432レースのみであり、統計的有意性は未検証(サンプル不足)。月次差(7月 win ROI 72.9%→63.0%、8月 win ROI 63.3%→65.9%)も方向感が一致していない。
- `horse_win_rate`/`horse_place_rate`/`horse_race_count` は既存`career_*`特徴量と完全重複と確認できたため、**採用しない(重複削除対象)**。
- `horse_normalized_mean_finish`/`horse_mean_finish`は既存特徴量にない新規シグナルであり重要度も高いが、今回の期間ではROI改善に寄与していない。市場人気との相関を強めた可能性があるため、**Phase B以降で位置取り・末脚など「市場が織り込みにくい」特徴量を追加した上で再評価する必要がある**。
- `age`/`carried_weight`は旧版通り単体では影響が小さい。

**現時点の推奨**: Phase A単体(このセット)は本番採用を見送り。次はPhase B(末脚`HaronTimeL3`正規化・多点位置取り・`position_closing_power`)を優先実装し、Phase Aの`horse_normalized_mean_finish`/`horse_mean_finish`との重複・相関を再確認しながらAB評価する。

## 5. Phase B 実装内容(今回実施)
末脚(HaronTimeL3正規化)・後方コーナーを含む多点位置取り・position×closing_speedを実装した。

- `closing_time_value`: 過去走の`HaronTimeL3`(0以下/欠損はNone)。
- `last_corner_position`: `Jyuni4c`→`Jyuni3c`→`Jyuni2c`→`Jyuni1c`の順で最初に取得できた値(直線に最も近いコーナー)。既存の`first_corner_position`(`Jyuni1c`のみ)と併用。
- 過去走ごとに、**同一レース内**で`HaronTimeL3`を昇順ランクし`closing_speed`(1に近いほど末脚が速い、欠損は0.5)を算出。コーナー正規化と同じ「対象レースの結果は特徴量に使わず、完了後にのみ履歴へ格納する」構造をそのまま踏襲(`observed_closing_speed`は`pending_updates`経由でのみ次走以降に反映)。
- `late_frontness`: `last_corner_position`を`frontness`と同じ0〜1正規化(1に近いほど前)で算出。
- `position_closing_power = frontness(早いコーナー) × closing_speed`を過去走ごとに保持し、`last1/last2_mean/last3_mean/best`を算出。
- 新特徴量: `last1-3_closing_speed`, `mean/best_closing_speed_last3`, `last1-3_late_frontness`, `mean_late_frontness_last3`,
  `position_closing_power_last1`, `position_closing_power_last2_mean`, `position_closing_power_last3_mean`, `best_position_closing_power_last3`。

新モデルラベル `RB` (`--model RB`) = モデルG特徴量一式 + 上記13特徴量。Phase Aとは独立にAB比較した(Phase Aは不採用のため積み上げず、Gに対して単独評価)。

## 6. Phase B 結果(2026-07〜2026-09, 432レース)

| 指標 | baseline G | +Phase A (RA) | +Phase B (RB) |
|---|---:|---:|---:|
| LogLoss | 0.2448 | 0.2393 | 0.2397 |
| Brier Score | 0.0670 | 0.0661 | 0.0659 |
| ROC-AUC | 0.7440 | 0.7639 | 0.7599 |
| Top1的中率 | 25.23% | 23.61% | **25.69%** |
| Top3的中率 | 57.18% | 59.49% | 57.18% |
| 単勝ROI | 69.7% | 63.9% | **69.3%(ほぼ同水準)** |
| 複勝ROI | 78.2% | 71.7% | **80.2%(改善)** |
| Spearman(AI順位 vs 人気順位) | 0.7656 | 0.8016 | 0.7911 |

**Feature importance(gain, RBモデル、全特徴量中の順位)**:
1. `last1_finish` (既存)
2. `recent5_place_rate` (既存)
3. `recent3_place_rate` (既存)
4. `career_place_rate` (既存)
5. `field_size` (既存)
6. `best_adjusted_performance_last3` (既存)
7. **`mean_late_frontness_last3`(新規, gain=31,437)** — 全特徴量中7位
8. `prize_ratio_vs_last3_mean` (既存)
9. `prize_change_from_last3_mean` (既存)
10. `career_races` (既存)

その他の新規特徴量の順位: `position_closing_power_last3_mean`(16位), `mean_closing_speed_last3`(17位), `position_closing_power_last2_mean`(20位),
`last1_late_frontness`(21位), `best_closing_speed_last3`(24位), `last1_closing_speed`(28位), `best_position_closing_power_last3`(38位), `last2_late_frontness`(40位)。
`last3_closing_speed`/`position_closing_power_last1`は寄与がほぼゼロ(サンプル数減衰・情報重複の可能性)。

**結論・判断**:
- Phase Aと異なり、Top1的中率・単勝ROIともにbaseline Gとほぼ同水準を維持しつつ複勝ROIが改善(78.2%→80.2%)。Spearman(市場との一致度)もPhase Aの0.802より低い0.791で、Phase Aほど市場に寄っていない。
- `mean_late_frontness_last3`(後方コーナーまで含めた位置取り)が全特徴量中7位という高い重要度で寄与しており、既存の`frontness_mean`(第1コーナーのみ)や`position_stability`とは異なる独立情報を提供していると考えられる。
- `position_closing_power`系(位置取り×末脚)も複数が上位30位以内に入り、旧netkeiba版の設計思想(「前にいて、末脚も速い馬は強い」)が現行データでも有効なシグナルであることを裏付けた。
- ただし2ヶ月・432レースのみの評価であり、月次差(7月 win ROI 71.4%、8月 65.2%)にはばらつきがある。統計的有意性は未検証。
- `last3_closing_speed`/`position_closing_power_last1`はgainがほぼ0であり、重複または情報量不足の可能性がある。次回精査時に削除候補。

**現時点の推奨**: Phase B(末脚・多点位置取り・position×closing_speed)はPhase Aより有望。ROIを大きく落とさずにTop1的中率・複勝ROIを改善し、既存特徴量にない独立シグナル(`mean_late_frontness_last3`)を確認できた。**Phase C(距離/芝ダート/馬場/休養/枠適性)へ進める価値がある**。

## 7. 今後のフェーズ(未着手)
Phase C以降(距離・芝ダート・馬場・休養間隔・枠適性、コース×枠勝率、騎手・調教師、坂・コーナー適性、血統)は本セッションでは未着手。
実装時は本ドキュメントの「未実装」項目を優先し、既存の`course_shape_fit`/`distance_change_fit`等フィット系特徴量との相関(|corr|>0.98)を
必ず確認してから採否判断すること。Phase A/Bの結果から、単純な「経験・累積成績」系の特徴量は市場(人気)との相関を高めるだけになりやすい一方、
位置取り・末脚のような「馬の走り方」に関する特徴量は独立したシグナルを持つ傾向が見えた。Phase C以降も同様に、既存の「強さ」指標と重複しない
独立要因(適性・バイアス・血統)を優先する。



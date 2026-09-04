# 現行学習・評価モデルの特徴量影響度ランキング

## 結論

- 12か月 walk-forward評価で使用しているRankerは、コード上 `CLEANUP_B_FEATURES` の **104特徴量**を入力としている。
- 影響度の主順位は、同じwalk-forward設定で計算した **TreeSHAPの平均絶対値**を使用した。
- 上位は、直近レースの着差・調整後パフォーマンスと、キャリア成績・近走成績に集中している。
- 最重要特徴量は次の通り。
  1. `weighted_adjusted_performance_last3`
  2. `career_win_rate`
  3. `last1_raw_performance`
  4. `career_races`
  5. `prize_ratio_vs_last3_mean`
- 上位の近走パフォーマンス系は相関が非常に高く、個別特徴量の順位をそのまま「独立した重要度」と解釈してはいけない。
- `prize_ratio_vs_last3_mean` は順位が高いが、12か月全体の除去テストでは性能改善が再現しなかった。

## 対象と注意

- 対象評価: 月次 walk-forward、2025-09〜2026-08、1着賞金800万円超。
- 学習器: LightGBM `LGBMRanker`（`lambdarank`）。
- TreeSHAP: 各予測への寄与の絶対値を平均した値。大きいほど予測値を動かしている。
- Permutation importance: その特徴量を入れ替えたときの性能低下。大きいほど単独の情報量が強い。
- Gain: 木の分岐で得た損失改善の累積。相関する特徴量に重要度が分散・集中するため、単独の因果的な重要度ではない。
- 今回はモデルや特徴量を変更していない。元データは [`feature_importance_comparison.csv`](./ranker_feature_audit/feature_importance_comparison.csv)。

なお、`reports/current_model_report_2026_09/feature_list.md` に記載されたCLEANUP_E系の構成は別実験の説明である。12か月walk-forward予測を生成する [`ranker_walk_forward_backtest.py`](../src/ranker_walk_forward_backtest.py) は、現時点では `CLEANUP_B_FEATURES` を参照している。

## 影響度ランキング（TreeSHAP平均絶対値順）

| 順位 | 特徴量 | 特徴量群 | 平均絶対SHAP | Gain順位 | Permutation順位 |
|---:|---|---|---:|---:|---:|
| 1 | `weighted_adjusted_performance_last3` | 近走パフォーマンス | 0.18727 | 1 | 2 |
| 2 | `career_win_rate` | キャリア・近走成績 | 0.17035 | 4 | 1 |
| 3 | `last1_raw_performance` | 近走パフォーマンス | 0.15994 | 2 | 3 |
| 4 | `career_races` | キャリア・近走成績 | 0.09328 | 5 | 4 |
| 5 | `prize_ratio_vs_last3_mean` | 賞金・レース格 | 0.07827 | 3 | 5 |
| 6 | `weighted_margin_last3` | 近走パフォーマンス | 0.07416 | 8 | — |
| 7 | `recent3_place_rate` | キャリア・近走成績 | 0.06831 | 6 | 8 |
| 8 | `last1_adjusted_performance` | 近走パフォーマンス | 0.06581 | 10 | 10 |
| 9 | `mean_adjusted_performance_last3` | 近走パフォーマンス | 0.05486 | 7 | 21 |
| 10 | `prize_change_from_last3_mean` | 賞金・レース格 | 0.04593 | 9 | 9 |
| 11 | `last2_adjusted_performance` | 近走パフォーマンス | 0.04095 | 14 | — |
| 12 | `races_last_180d` | キャリア・近走成績 | 0.04027 | 13 | 6 |
| 13 | `mean_margin_last3` | 近走パフォーマンス | 0.03901 | 11 | — |
| 14 | `last1_distance` | 距離・コース適性 | 0.03501 | 19 | 7 |
| 15 | `last3_field_top3_mean_strength_v2` | 相手・出走馬強度 | 0.03289 | 16 | 18 |
| 16 | `career_places` | キャリア・近走成績 | 0.02734 | 27 | 22 |
| 17 | `last2_field_strength_v2` | 相手・出走馬強度 | 0.02610 | 29 | 23 |
| 18 | `last2_raw_performance` | 近走パフォーマンス | 0.02589 | 17 | — |
| 19 | `best_strong_opponent_performance_last3` | 近走パフォーマンス | 0.02528 | 12 | 37 |
| 20 | `last3_field_strength_v2` | 相手・出走馬強度 | 0.02408 | 25 | 14 |
| 21 | `last2_distance` | 距離・コース適性 | 0.02162 | 24 | 11 |
| 22 | `last2_field_top3_mean_strength_v2` | 相手・出走馬強度 | 0.01979 | 18 | 24 |
| 23 | `current_distance` | 距離・コース適性 | 0.01942 | 28 | 20 |
| 24 | `recent3_win_rate` | キャリア・近走成績 | 0.01805 | 26 | 16 |
| 25 | `last1_field_strength_v2` | 相手・出走馬強度 | 0.01682 | 31 | 13 |
| 26 | `last1_margin_x_prize_strength` | 近走パフォーマンス | 0.01591 | 21 | 41 |
| 27 | `last1_field_top3_mean_strength_v2` | 相手・出走馬強度 | 0.01458 | 22 | 17 |
| 28 | `last3_margin_x_prize_strength` | 近走パフォーマンス | 0.01196 | 38 | — |
| 29 | `prize_ratio_vs_last1` | 賞金・レース格 | 0.01186 | 15 | 28 |
| 30 | `last3_field_strength` | 相手・出走馬強度 | 0.01176 | 20 | 12 |

## 特徴量群としての整理

### 1. 近走パフォーマンス・着差系

最も強いグループ。`weighted_adjusted_performance_last3`、`last1_raw_performance`、
`last1_adjusted_performance`、`mean_adjusted_performance_last3` などが上位を占める。

これらは直近の着順・着差を、相手の強さ、レース格、展開などで補正した情報である。一方、
raw / adjusted / margin / weighted / mean の間に高い相関があり、同じ近走能力を複数の列で重複して表現している。

### 2. キャリア・近走成績系

`career_win_rate`、`career_races`、`recent3_place_rate`、`races_last_180d` が上位。
特に `career_win_rate` はPermutation順位1位で、他の列と入れ替えても情報が残りやすい。

### 3. 賞金・レース格系

`prize_ratio_vs_last3_mean`、`prize_change_from_last3_mean`、
`prize_ratio_vs_last1` が上位。今回のレース格と過去レース格の差をモデルが強く参照している。

ただし、賞金列同士も高相関で、`prize_ratio_vs_last3_mean` の単独除去は12か月全体で改善を再現しなかった。

### 4. 相手・出走馬強度系

`last3_field_top3_mean_strength_v2`、`last2_field_strength_v2` などが中位。
過去に対戦した相手や、そのレースの上位馬の強さを補助情報として使っている。

### 5. 距離・コース適性系

`last1_distance`、`last2_distance`、`current_distance` が上位30位内。
近走距離と今回距離の関係は影響しているが、近走パフォーマンスやキャリア成績ほど支配的ではない。

## モデル解釈上の重要な注意

- 重要度は「予測への影響」であり、勝率を因果的に上げる効果ではない。
- `weighted_adjusted_performance_last3` が1位でも、その特徴量だけで本命理由を説明できない。相関する近走特徴量群の合算効果が大きい。
- 市場人気と乖離したAI本命の誤りも、同じ近走パフォーマンス群が強く押し上げている。
- 既存監査では、人気4〜6番手のAI本命は予測勝率20.03%に対し実勝率8.33%、人気7番手以下は予測15.44%に対し実勝率4.44%だった。
- したがって、今後改善するなら、まず近走パフォーマンス群の重複を整理し、単一の強い指標に依存しない構成で12か月walk-forwardを再評価するのが優先である。

## 参照

- [`ranker_feature_audit/summary.md`](./ranker_feature_audit/summary.md)
- [`ranker_feature_audit/feature_importance_comparison.csv`](./ranker_feature_audit/feature_importance_comparison.csv)
- [`current_model_report_2026_09/feature_list.md`](./current_model_report_2026_09/feature_list.md)
- [`backtest.py`](../src/backtest.py)
- [`ranker_walk_forward_backtest.py`](../src/ranker_walk_forward_backtest.py)

# RACEVERSE v0.6 — 10,000回レースシミュレーションAI 実装仕様書

> **対象:** GitHub Copilot / Copilot Chat（既存競馬AIリポジトリに新機能を追加する実装エージェント）  
> **位置付け:** 実装・学習・検証・バックテストを含む要求仕様書  
> **版:** v0.6（v0.5を置き換える）  
> **基本原則:** 既存AIの「馬の強さ」の指標値を再利用し、既存予想・既存バックテストは一切破壊しない。  
> **標準試行数:** 1レース10,000回（設定可能）

---

## 0. Copilotへの作業指示（最初に必ず読む）

1. **実リポジトリを調査すること。** 学習・推論・バックテスト・既存能力指標・JRA-VANデータ／ラップ／コーナー通過順位の格納元を特定する。存在を確認していないパス、カラム、関数を仮定しない。
2. 既存能力指標への**読み取り専用アダプタ**を作る。既存Ranker・既存予測画面・既存バックテスト・既存学習パイプラインの挙動を維持する。
3. 独立した `raceverse/` 相当の名前空間で学習、特徴量生成、隊列抽選、連続値ペース予測、時計推定、レース同時シミュレーション、レポート、Walk-Forwardバックテスト、テストを実装する。
4. 不明なデータ項目は実データを調査する。観測できない情報を実測値として捏造しない。不足時はエラー、警告、フォールバックのいずれかを明示し、精度検証できない出力を確定値扱いしない。
5. **対象レースの発走前に利用可能だった情報だけ**で予測を生成する。時計の直近開催参照、騎手履歴、基準ラップ、既存能力指数、モデル学習、係数調整のすべてに適用する。
6. フェーズごとに自動テストを行う。完了時に「変更ファイル／実カラム対応表／実行コマンド／テスト・バックテスト結果／未完成機能／制約」を報告する。

### v0.5からの必須変更（今回の改訂の核心）

- **ペースを5クラスで学習しない。** 学習ターゲットは**連続値の前半ラップ（秒）またはコース基準との差（秒）**とし、初期モデルは**線形回帰（Ridge回帰を推奨）**とする。
- **5段階（超スロー／スロー／ミドル／ハイ／超ハイ）はユーザー向けの表示分類だけ。** 走破パフォーマンスの計算とシミュレーション内部では連続値ペースを保持する。分類してから再抽選する方式を廃止する。
- **走破／決着時計モデルを正式な実装対象にする。** 当日判明している馬場状態、**前日**、**先週の開催**、**開幕週なら一つ前の開催**、**前年同時期の開催**の実時計情報を参照し、出走馬の既存能力指標とシミュレーションで抽選したペースを統合して決着時計を推定する。
- 時計推定には参照レースの**距離・コース・クラス・ペース・馬場差**を補正し、単純な勝ち時計の平均を使用しない。参照可能な時点と条件を全件追跡する。
- 元の「隊列 → ペース → 展開 → 着順」の順序は維持。**隊列の確定後に、連続値ペースを予測・抽選する。**

### 非目標・禁止事項

- 既存モデルをRACEVERSEで上書きしない／既存の疑似勝率を真の勝率として流用しない。
- 当該レースの確定ラップ、勝ち時計、実際の序盤／4角順位、払戻などを**同レースの予測入力に使わない**。
- 5分類の確率をペース学習の正解ラベルにしない。5クラス分類器は初期実装では導入しない。
- **実際の隊列を学習時に使い、予測時だけ抽選隊列を使う**不一致を無視しない。
- 馬場参照用に未来日付・同日未確定レースを混入しない。開幕週に無い「先週の同場開催」を参照できることにしない。
- シミュレーション10,000回だけを根拠に「確率が正確」と主張しない。確率校正・未学習期間の検証は必須。

---

## 1. 全体アーキテクチャ

**RACEVERSE = Race × Universe**。

```text
出走表 + 過去走/コーナー順位 + レース全体ラップ + 騎手履歴
既存AIの馬能力指標 + 馬場状態 + 過去開催のラップ/勝ち時計
                           |
                           v
          [A] 発走前に一度だけ準備（過去情報のみ）
          - 既存能力指標、騎手先行度・逃げテンポ統計
          - コース別基準ラップ・時計、過去開催の馬場速度補正
          - 学習済み連続値ペース回帰モデルと時計モデル
                           |
                           v
                [B] 10,000回繰り返し
          1. 各馬の過去走を近2走優先で1つ抽選
          2. 抽選元と今回の騎手が違う場合のみ位置取り補正
          3. 前後の序盤隊列を決め、内外を馬番順に確定
          4. 隊列と騎手/枠/コースから前半ラップの連続値を予測
          5. 回帰予測値の周囲から実際の前半ラップを連続値で抽選
          6. 馬場履歴＋出走馬能力＋抽選ペースから決着時計を推定・抽選
          7. ペース/隊列/馬の適性/成長から相対的な走破性能・着差を生成
          8. 全馬の着順と個別時計を一括確定
                           |
                           v
          [C] 10,000回の集計・ユーザー向け表示
          - 勝率/複勝率/各着順確率/条件別勝率
          - 決着時計の期待値・分布・予測区間
          - 連続値ペース分布の要約／表示用5段階の割合
                           |
                           v
          [D] 既存方式とは独立のWalk-Forwardバックテスト
```

**時間順序:** 先に作るのは**序盤の隊列**だけ。3角・4角の位置取りはペース抽選後に更新する。走破時計推定は決着時計のレース共通アンカーを作り、そこから各馬の時計差を構築する（詳細は第8章）。

---

## 2. データ契約と既存AIへの接続

### 2.1 論理データ項目

> 下表は論理名。Copilotは実データソースに対応させ、変換表を作ること。

| 論理エンティティ | 想定フィールド | 主な用途 |
|---|---|---|
| Race | `race_id, race_datetime, track, surface, distance_m, course_layout, going, class_group, field_size, meet_id, meet_day, course_week, season` | レース条件、開催判定 |
| Race laps | `race_id, split_meters, sectional_laps_sec[]` | 実測ペース・ラップ基準 |
| Race result | `race_id, horse_id, finish_position, official_time_sec, margin, payout_win, result_confirmed_at` | 正解時計・着順・回収率 |
| Runner | `race_id, horse_id, horse_number, bracket_number, jockey_id, age, sex, weight_carried` | 出走表・初期隊列 |
| Past runner | `race_id, horse_id, jockey_id, run_datetime, field_size, corner_positions[], final_3f_sec, margin` | 位置取り履歴、騎手・適性集計 |
| Existing ability | `race_id, horse_id, ability_score, score_available_at, model_training_cutoff` | **既存AIから再利用する馬の強さ** |
| Track/meet metadata | `track, meet_id, start_date, end_date, surface, course_layout, course_configuration` | 前日・先週・前開催・前年開催の抽出 |
| Track condition | `track, race_datetime, surface, going, measured_condition_if_available` | 馬場・時計補正 |
| Odds snapshot | `race_id, horse_id, observed_at, win_odds` | 実際に買える時点での期待値・回収率 |

**前提:** レース全体のラップは利用可能と想定、各馬の200mごとの区間ラップは利用できない。通過順位だけから厳密な馬間距離・区間時計を復元しない。

### 2.2 既存能力指標 `ability_score`

- 基礎能力は**既存AIの指標値そのもの**を採用する。新規の基礎能力モデルを作らない。
- 指標の大小方向・レンジ・変換方法はリポジトリ調査で確定。Ranker生スコアを秒や勝率に直接読み替えない。
- 秒との対応や着差への寄与が必要なら、学習期間のみを用いる**小さな校正レイヤー**を別に学習する。
- 既存指数に馬場・枠・ペース情報が含まれるか確認し、補正を二重に足さない。
- バックテストで使う過去レースの能力値は、その予測時点に入手可能な**Walk-Forward/時系列OOFの値**に限る。全期間学習済みモデルによる過去への当てはめは禁止。

### 2.3 時間カットオフ

- 全履歴データは `available_at < target_prediction_time` を満たすこと。時刻が不明なら安全側として**対象レース前日までの確定データ**に限定する。
- 前日・先週・前開催・前年の抽出に使うレースも、結果確定済みかつ発走前に入手可能なものだけ。
- 前日開催がない、雨で馬場が変化、前年のコース改修などは欠損・条件変更として扱う。**存在しない直近サンプルを捏造しない**。

---

## 3. 序盤隊列：近2走重視の過去走サンプリング

### 3.1 過去走抽選

- 各試行・各馬について**過去の1レースを1つ抽選**し、そのレースの序盤位置取りパターンを採用する。
- **直近1走・2走は同じ最大重み**。3走前以降は古くなるにつれ**一律に1ずつ重みを減らす**。初期版は最大10走。
- デフォルト重み：

| N走前 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 重み | 10 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |

- 存在する過去走だけで正規化。10走あるとき1走前と2走前は各`10/64 = 15.625%`、合計31.25%。
- 距離・芝ダが異なるレースも**初期版は同じ時系列重み**で扱い、違いは記録する。暗黙に除外・割増ししない。
- デビュー戦など履歴なしは、明示した事前分布で位置を抽選して `cold_start=true` を記録する。
- コーナー別順位がある場合は**同一過去走の位置取り系列をセットで抽出**する。コーナーごとに別の過去走を選ばない。

### 3.2 頭数補正

最初に有効な序盤コーナー順位 `rank`、当時の出走頭数 `n` から：

```python
q_sampled = (rank - 1) / (n - 1)  # 0.0=先頭、1.0=最後方
```

頭数1以下・欠損・順位不正は明示的に処理。厳密な馬間距離は出せないため、必要な場合は別途**推定値**であることを示す。過去走に複数コーナーがあるなら`q_by_corner`も保管する。

---

## 4. 騎手乗り替わりのときだけ位置取り補正

### 4.1 発動条件

**今回騎手と、抽選された過去走の騎手が異なる場合にだけ**補正する。前走の騎手との比較ではない。

- 同じなら完全に無補正。
- 抽選した3走前だけ別騎手なら、その試行では補正する。
- 過去走の騎手IDが不明なら、勝手に乗り替わりと判定しない。補正なし＋警告。

### 4.2 先行度

騎手別に過去の序盤相対位置から求める：

```text
raw_frontness(j) = 1 - mean(historical_early_q for jockey j)
frontness(j) = (n * raw_frontness(j) + k * group_prior_frontness) / (n + k)
```

- `0〜1`。高いほど先行位置にいる傾向が強い。
- 馬の脚質や騎乗馬構成による偏りを含む**観測上の傾向**であり、純粋な騎手技術とは断言しない。
- 騎手履歴統計は予測時より前のデータのみ。`k`は設定値。

### 4.3 乗り替わり補正

```python
q_adjusted = clip(
    q_sampled - alpha * (frontness(current_jockey) - frontness(sampled_run_jockey)),
    0.0, 1.0,
)
```

- 初期 `alpha = 0.4`（暫定）。新騎手が先行型なら前（qが小さい）、控える型なら後ろ。
- 値が同じ騎手同士の乗り替わりでは移動なし。
- **この補正以外の騎手確率変数を隊列生成に重ねない。** 騎手の逃げテンポは隊列確定後のペースモデルで使用する。

---

## 5. 序盤隊列の確定と枠順による内外配置

1. 全馬の `q_adjusted` を小さい順に並べる。
2. `position_group_threshold = 0.08`（初期値）を使い、先頭からアンカー固定で前後位置が近い馬を同グループにする。連鎖的に範囲が広がる判定はしない。
3. **同グループ内は馬番の小さい馬が内、大きい馬が外**となるよう、内外スロットを割り当てる。
4. 同枠なら同様に馬番順。実在しない「同着の通過順位」を作らず、`early_group`, `lateral_slot`, `early_order` を分けて保持する。
5. 別グループ間の内外をむやみに比較しない。コーナーでの進路変更や馬間距離の厳密な復元は初期版の対象外。

**例:** 1枠の馬と4枠の馬が同じ前後グループにいる場合、1枠側が内。ただし決定ルールは**枠番ではなく馬番の昇順**なので全馬に一貫して適用できる。

---

## 6. ペース：実データで「連続値」を線形回帰する

### 6.1 厳守すべき学習仕様

- **5クラス分類器は作らない。** 線形回帰（標準化＋Ridge回帰を初期推奨）で、前半ペースの**連続値**を学習する。
- 基本の教師値は`pace_delta_sec`：対象コース条件の**過去データだけから求めた標準前半ラップ**に対する実測ラップ偏差。
- 定義は `pace_delta_sec = actual_early_split_sec - reference_early_split_sec`。**負ほど速いペース、正ほど遅いペース。**
- 予測後は `predicted_early_split_sec = reference_early_split_sec + predicted_pace_delta_sec` として秒数に復元する。
- 区間長を統一せずに異なる距離・コースの前半3Fを直接比較しない。対象距離・ラップ刻みに応じた**前半計測区間ルール**を定義する。初期実装はコース群ごとに比較可能な前半区間（600mが使える場合は600m）を使い、区間長メタデータも保存する。
- 「線形予測」は**目的変数が連続で、初期推定器が線形回帰であること**を意味する。ペースの5段階表示区分とは独立。

### 6.2 数式・実装例

```text
y_r = actual_early_split_sec(r) - reference_early_split_sec(r)
y_hat_r = intercept + Σ_j beta_j * x_rj
T_early_hat = reference_early_split_sec + y_hat_r
```

初期のscikit-learn構成（依存関係を確認してから採用）：

```python
pace_regressor = Pipeline([
    ("preprocess", fitted_numeric_categorical_transformer),  # 欠損処理, 標準化, OneHot等
    ("ridge", Ridge(alpha=config.pace_ridge_alpha)),
])
pace_regressor.fit(X_train, y_train, ridge__sample_weight=weights_if_supported)
pace_delta_hat = pace_regressor.predict(X_formation)[0]
```

※ 上記は概念例。実際に`Pipeline.fit()`で渡せるパラメータ名、Transformer、依存版を調べて実装すること。学習期のスケーリングを評価期へ流用し、全期間の平均・分散で事前標準化しない。

### 6.3 機械的に生成するペース説明変数

**特徴量のルールは人間が固定してよい。影響係数は実ラップから線形回帰で学習する。**

| カテゴリ | 例 | 生成法 |
|---|---|---|
| 序盤隊列 | `front_group_size`, `lead_candidates`, `q_top3`, `front_competition` | **その試行で抽選した隊列**から生成 |
| 先行配置 | `front_q_spread`, `leader_margin_in_q`, `group_size_top2` | qの分散、先頭同士の密集度 |
| 枠／馬番 | `outside_front_count`, `outside_front_pressure`, `front_group_avg_horse_no_pct`, `lead_horse_number_pct` | 先行集団の相対馬番。外に先行馬が多いほど圧力が強いという仮説を**係数で検証** |
| 騎手ペース傾向 | `leader_jockey_lead_tempo`, `top3_jockey_lead_tempo`, `chaser_tempo` | 過去ラップ＋過去の序盤順位から計算 |
| 騎手先行傾向 | `leader_jockey_frontness`, `top3_frontness` | 過去の位置取りを平滑化集計 |
| コース | `track`, `surface`, `distance_m`, `course_layout`, `first_turn_distance_m` | 事前確定情報のみ |
| 環境 | `going`, `meet_day`, `course_week`, `season` | 事前に取得可能な馬場・開催情報 |

騎手の「競りかけ度」が直接観測できない場合は正解データを作り上げず、`front_competition`・`chaser_tempo`などの代理特徴量に留める。交互作用が必要なら、`outside_front_pressure × short_first_turn` 等の**機械生成交差特徴**を追加し、線形モデルで係数を学習する。

### 6.4 騎手の逃げペース傾向を数値として保存

過去にその騎手が先頭付近にいたレースの実測前半ラップから算出：

```text
jockey_lead_tempo_raw = mean(reference_early_split_sec - actual_early_split_sec)
jockey_lead_tempo = (n * jockey_lead_tempo_raw + k * group_prior) / (n + k)
```

- **正なら標準より速く刻む傾向、負なら遅い傾向。**
- コース・芝ダ・距離・馬場等でラップ基準を補正。先頭にいた馬自身の能力・他馬との競り合いも含むため、純粋な騎手の意思決定値とは断言しない。
- 標本数と縮小係数を保存。十分なレースがない騎手は事前平均に近づける。
- 統計はすべて予測対象レースより過去のデータのみ。

### 6.5 隊列生成を組み込んだ回帰学習

対象レースの**実際の通過順位は特徴量に使わない**。過去走サンプリング＋騎手変更補正＋枠順による内外位置の決定を、過去学習レースにも再現する。

1. 学習用レースrについて、rより前のデータだけで過去走候補と騎手統計を構成する。
2. 同じ学習レースについて、異なるseedで疑似隊列を複数回生成する（例：16回）。
3. 各疑似隊列からペースの説明変数を生成し、**正解は当該レースの実測連続値ペース偏差**を各行に与える。
4. 16行を作ったなら各行のsample_weightは`1/16`、レース単位の重みの合計は1にする。
5. 学習・検証の境界は**レース単位・時系列**。同一レース由来の疑似隊列を学習と評価へまたがせない。
6. チューニング・学習時の履歴集計と標準ラップも対象レース以前に限定する。これは「本番と同じ種類の不確実な隊列を入力する」ための近似学習方式であり、疑似隊列が真の隊列だと主張しない。

### 6.6 シミュレーション内のペース抽選（連続値）

回帰モデルの予測値をそのまま10,000回固定するのではなく、学習期間の**時系列検証残差**から得た分布で変動させる。

```python
# each simulation, after early formation is fixed
x = make_pace_features(race, formation, jockey_profiles)
mu_delta = pace_regressor.predict(x)[0]               # real-valued seconds
error = pace_error_sampler.sample(rng, race_context)    # fitted ONLY on past OOF residuals
pace_delta = mu_delta + error
sampled_early_split_sec = reference_early_split_sec + pace_delta
```

- 残差の分散は、過去の予測誤差から推定する。ノイズ幅を根拠なく設定しない。データ不足なら学習全体の残差分布へフォールバックし警告する。
- 明らかに物理的に不合理なラップは検知し、**学習期の分位点などに基づく**トランケーション／再抽選を使用する。勝手な秒数のクリップは禁止。
- **5クラスのいずれかを先に抽選しない。** 抽選するのは前半区間ラップの連続値（秒）。
- 回帰平均・残差・抽選ペースを別々にログ保存して、ばらつきの原因を追跡できるようにする。

### 6.7 表示だけ5段階にする

内部ペースの連続値から、表示用カテゴリへ後処理変換する。

```python
def pace_display_bucket(pace_delta_sec, thresholds):
    # thresholds = [b1, b2, b3, b4] in strictly increasing order
    if pace_delta_sec < thresholds[0]: return "VERY_FAST"
    if pace_delta_sec < thresholds[1]: return "FAST"
    if pace_delta_sec < thresholds[2]: return "MIDDLE"
    if pace_delta_sec < thresholds[3]: return "SLOW"
    return "VERY_SLOW"
```

- 定義が`actual - reference`なので**数値が小さいほどハイペース**。
- 閾値は学習期間のペース偏差分布で設定し、コース群・区間長に応じて管理。未学習期間で閾値を再推定してはならない。
- 内部の勝ち時計／着順計算は**区分名ではなく連続値秒数**に基づく。
- レース単位の各分類の表示確率は、1万回の抽選ペースを分類した比率として求める。

---

## 7. 馬場・開催履歴から走破時計の環境基準を作る

### 7.1 狙い

決着時計を単に「距離ごとの平均タイム」で決めない。**直近開催の馬場速度（速い／遅い）**を反映したレース基準時計を求める。

入力：

- 現在の `track`, `surface`, `distance_m`, `course_layout`, `going`, 開催週、開催日
- **前日に同場開催があれば、その結果確定済みのレース**
- **先週に同場開催があれば、その結果確定済みのレース**
- **今週が開幕週／直近比較対象がないときは、一つ前の同場開催（前開催）**
- **前年の同時期（同場・近い開催条件）のレース**
- 予想対象の**出走馬全頭の既存能力指標**（強い馬がいるほど基準時計が速くなり得る）
- そのシミュレーションで**隊列後に決定した連続値ペース**

ここで「一つ前の開催」は、**同一競馬場で行われた直近の過去の開催区間**を意味する。別競馬場の先週レースを代わりにしない。

### 7.2 参照優先順位と欠損時のフォールバック

次を候補プールとして構築し、条件補正後に重み付けする。**同じレースが複数窓に入った場合はrace_idで重複排除**する。

| 優先 | 窓 | 参照するもの | 備考 |
|---:|---|---|---|
| 1 | `previous_day` | 前日に開催された同場・同芝ダの結果確定レース | 最も現在の馬場に近い。ただし雨・馬場変更を検知 |
| 2 | `previous_week` | 直近前週に同場開催されたレース | 前日が無い、サンプル不足時も使用 |
| 3 | `previous_meet` | **開幕週なら直前の同場開催** | 数か月の間隔・芝コース区分変更を減衰／補正 |
| 4 | `previous_year_same_season` | 前年の同時期の同場開催 | 季節参考値。改修や異常気象で差があるため信用度低め |
| 5 | `historical_course_prior` | それ以前のコース条件別学習データ | 最終フォールバックの基準時計 |

- **優先順位はサンプル採用の順位で、固定の足し算秒数ではない。** 重みは初期値を設定ファイルに置き、過去の検証で調整する。
- 前日と先週を**両方**利用可能な場合は情報を統合する（前日のウェイトを高めにする）。
- 開幕週では「先週同場が無い」ことを異常扱いせず、`previous_meet`と`previous_year_same_season`から補う。
- 別距離・別クラスの勝ち時計を未補正で直接平均しない。基準時計との差分に変換してから集約する。
- 重要な馬場変更（良→重、まとまった降雨、芝のコース替わりなど）があるなら、過去窓の重みを下げる／条件効果で補正する。**現在の馬場状態が取得できない場合は不明と記録**する。
- 一般に前開催・前年データは「現在の速い／遅い馬場」の直接観測ではなく、**季節やコースの事前情報**として使用する。直近日程ほど信頼するが、同条件度も考慮する。

### 7.3 異なるレースの時計を比較可能にする（必須）

過去参照レースhについて、学習済みの基準時計モデルでまず期待勝ち時計を求める。

```text
T_base(h) = historical_course_time_baseline(
    track, surface, distance_m, course_layout, class_group,
    going, season, ...
)
track_speed_residual(h) = actual_winning_time_sec(h) - T_base(h)
```

- `track_speed_residual` が**負ほど基準より速い**、正ほど遅い。
- 可能なら過去レースの実測ペースと出走馬能力で `T_base(h)` を補正し、**馬の質・ペースと馬場の速さを混同しない**。
- 同距離・同コースが少ないなら、コース群（芝ダ・競馬場・距離帯）へ段階的にプール。ただし補正の信頼度を低く扱う。
- 大きく異なる距離・コースを秒数のまま合算せず、**レース条件を補正した残差**または標準化された残差で統合する。
- 参照レースの `result_confirmed_at` が予測時刻より前であることを必ず確認する。
- 参照時計の比較基準 `T_base` 自体も、対象レースより未来のデータで推定した値ではないこと。Walk-Forwardで履歴の予測残差を生成する。

### 7.4 馬場速度補正の機械的集約

各参照プール内の補正済み残差を、頑健統計量（例：winsorized weighted mean）で集約し、信用度と有効サンプル数を持つ。構造例：

```text
recent_track_bias_sec = weighted_robust_mean(
    track_speed_residual(h),
    weights = recency_weight(h) * condition_similarity(h) * source_priority(h)
)
```

- 極端に件数が少ないときは `historical_course_prior` 側へ縮小（Bayesian/ridge的shrinkage）。
- 同日午前の結果を利用する高機能モードは、公開時刻が追える場合に限る。**初期デフォルトは前日まで**。
- どの開催・レースを参照したか `reference_race_ids`, `source_window`, `effective_sample_size`, `track_bias_sec`, `fallback_level`, `reference_cutoff` を記録する。
- 雨や馬場変更が起きた場合、過去データが新しいという理由だけで高ウェイトにしない。馬場状態差の補正／信頼度引き下げを行う。

---

## 8. 決着時計・各馬の走破時計モデル

### 8.1 目的と二段構造

**1万回の各試行で、実際の秒数を持つ決着時計（勝ち時計）を推定する。** 以下を明確に分ける。

1. **決着時計モデル:** レース全体の予想勝ち時計 `T_win` を推定する。入力は馬場状態・前日／先週／前開催／前年の馬場速度・コース／距離／クラス・全出走馬の既存能力指標・その試行の連続値ペース・隊列特性。
2. **着順／着差モデル:** 同じ試行における全馬の相対的なパフォーマンスを推定して勝ち馬を選び、各馬の勝ち馬からの遅れ秒数 `margin_sec_i >= 0` を作る。`T_i = T_win + margin_sec_i` として各馬時計を確定する。

こうすると同一レース内の時計と着順は必ず一致する。**勝ち馬を選ぶときに`T_win`を馬ごとに独立に使用しない**（同一勝ち時計を全馬に足すだけでは勝者が決まらない）。

### 8.2 決着時計の回帰・補正式

概念式（係数は**過去の実測時計から推定**し、任意の秒数を足さない）：

```text
T_win_mean =
    T_course_baseline(track, surface, distance, course_layout, class, going)
  + recent_track_bias_sec(previous_day, previous_week, previous_meet, previous_year)
  + field_ability_adjustment(existing_ability_scores_of_all_runners)
  + pace_adjustment(sampled_early_split_sec, course_specific_reference_early_split)
  + formation_adjustment(early_formation_features)
  + other_observable_adjustments

T_win_sampled = T_win_mean + draw(time_model_residual_distribution)
```

**必須事項:**

- `field_ability_adjustment`：既存指数の上位値・上位3頭平均・頭数補正など、**能力が高い馬がどれくらいいるか**を表す特徴量に基づいて学習する。能力指数の単純合計を時計の秒へ直結させない。
- `pace_adjustment`：予測した連続値前半ペースを使う。**スローほど必ず時計が遅い、ハイほど必ず速いという直線仮定だけには依存しない**。線形項に加えて二乗項、コース群との交互作用等の機械生成特徴量を使い、実績で効果を検証できる形にする。
- `going`・`recent_track_bias_sec`：馬場状態だけでなく過去の実時計から推定した当該開催の時計の出やすさを反映する。
- `T_course_baseline` は過去期間のみで学習。決着時計モデルは第6章のペース回帰とは**別モデル**（Ridge、GAM、勾配ブースティング回帰等、性能とデータ量を見て決定）。
- 時計の予測分散は**時系列OOF残差**から推定する。馬場補正の参照サンプルが少ないときは不確実性を増やす仕組みが望ましい。
- 時計回帰の教師値は実際の勝ち時計。**当該レースの実ラップを予測入力に入れて学習すると、予測時のラップと分布がずれる。** 学習時にも第6章に沿った**当該レース前情報から生成した隊列・予測ペース**を使用する。実測ペース入力版は診断用に分離し、本番精度と混同しない。
- 既存能力指数の尺度や馬場補正の二重計上を確認し、採用特徴量と校正をレポートする。

### 8.3 参照時計モデルと決着時計モデルの二重使用を避ける

過去開催の馬場速度補正は、本来の走破能力・ペース・クラスを取り除いた残差として集約する。同じ「馬場の速さ」を基準時計、`recent_track_bias_sec`、追加の馬場補正項に**重複して加えない**。

初期構成として：

```text
historical_baseline + learned_field_effect + learned_pace_effect
                    + one_recent_track_bias_term + calibrated_time_noise
```

を推奨する。時計補正を複雑にするのはアブレーションで効果確認後。

### 8.4 各馬のパフォーマンスと着差

- 馬の基本的な強さは既存`ability_score`。
- 当該試行の**連続値ペース**、初期隊列、3角・4角へ向かう進出／後退、内外のロス、馬場適性、コース適性、年齢・休養に伴う成長・仕上がりを条件付き補正に利用する。
- ペース適性：超スローなら単騎逃げ・瞬発力型、ミドルなら能力とロスの少なさ、ハイなら差し馬だけでなく**前受けで粘る持続力／減速戦耐性のある馬**を評価できる形にする。初期版はレース全体ラップ・コーナー順位・上がり・着差を代理特徴とし、個別馬の200mラップを捏造しない。
- 3角・4角は**ペース抽選後**に生成。最初に実際の3角4角順位を流用しない。
- 2〜3歳馬の成長度は平均変化と分散、休み明けの仕上がりは別効果として扱う。「若い・休養明けなら必ず上乗せ」は禁止。
- 個馬の着差は学習期間の指数・着差対応から秒へ校正し、全馬のパフォーマンスを**同一試行で一括比較**する。勝ち馬の着差は0秒、他馬は非負に正規化する。
- `T_i = T_win_sampled + margin_sec_i`。**着順と時計の単調性を必ず満たす**。同着再現は初期版対象外。
- レース内の共通ショック（ペース・馬場・隊列）を共有し、全馬の誤差を無関係に設定して不自然な勝者分布を作らない。

### 8.5 欠損時の扱い

- 直近馬場参照が不足すれば**前開催 → 前年同時期 → 長期コース基準**へ明示的にフォールバックし、時計と予測区間に不確実性を反映する。
- 基準時計モデルに必要な実時計・距離・コース等が欠落し、検証可能な秒数予測が実装できない場合、**架空の時計を出さない**。`winning_time_status=unavailable` とエラーレポートを出し、勝率・着順のモデルは独立継続できる設計にする。
- 参照レース数・時点・どの開催を利用したかを表示できるようログを残す。

---

## 9. 10,000回シミュレーション

### 9.1 擬似コード（実リポジトリへ適合させること）

```python
def simulate_race(race, runners, cfg, rng, deps):
    # 事前処理：すべて予測時点で入手可能な情報
    abilities = deps.existing_ability_provider.get_scores_as_of(race, runners)
    past_runs = deps.history_provider.get_past_runs_as_of(race, runners)
    jockey_profiles = deps.jockey_provider.get_profiles_as_of(race, runners)
    early_reference = deps.pace_reference.get_as_of(race)
    track_context = deps.track_speed_builder.build_as_of(race)  # 前日・先週・前開催・前年
    accumulator = SimulationAccumulator(runners)

    for sim_id in range(cfg.n_simulations):
        sampled_positions = []
        for horse in runners:
            past = weighted_sample_one_past_run(
                past_runs[horse.horse_id], cfg.recency_weights, rng
            )
            q = relative_early_q(past)  # missing履歴は明示prior
            if past.jockey_id is not None and past.jockey_id != horse.jockey_id:
                q = adjust_q_with_jockey_frontness_difference(
                    q, past.jockey_id, horse.jockey_id,
                    jockey_profiles, alpha=cfg.jockey_change_alpha,
                )
            sampled_positions.append((horse, q))

        early_formation = build_early_formation(
            sampled_positions,
            group_threshold=cfg.position_group_threshold,
            lateral_order="horse_number_ascending",
        )

        pace_x = mechanical_pace_features(
            race, early_formation, runners, jockey_profiles
        )
        mu_pace_delta = deps.pace_linear_regressor.predict(pace_x)[0]
        pace_delta = mu_pace_delta + deps.pace_residuals.draw(rng, race)
        early_split_sec = early_reference.seconds + pace_delta
        pace_bucket = display_bucket_only(pace_delta, cfg.display_pace_thresholds)

        win_time_x = winning_time_features(
            race=race,
            track_context=track_context,
            field_abilities=abilities,
            sampled_pace_delta=pace_delta,
            early_formation=early_formation,
        )
        win_time_mean = deps.winning_time_model.predict(win_time_x)[0]
        win_time_sec = win_time_mean + deps.winning_time_residuals.draw(rng, race)

        finish = simulate_joint_finishing_order_and_margins(
            race, runners, abilities, early_formation,
            early_split_sec, pace_delta, track_context, rng,
        )
        # finish.margins_sec[finish.winner] == 0, others >= 0
        horse_times = {
            horse_id: win_time_sec + finish.margins_sec[horse_id]
            for horse_id in finish.order
        }
        accumulator.record(
            early_formation, mu_pace_delta, pace_delta, pace_bucket,
            track_context, win_time_sec, finish.order, horse_times,
        )

    return accumulator.finalize()
```

**例示擬似コード**であり、実際の型・関数・インポートの存在を前提としない。`past=None`などの欠損は明示的に処理し、Numpy配列バッチ化など必要な高速化を行う。

### 9.2 試行と乱数

- `n_simulations=10_000`、開発・単体テストでは小さな回数を指定可能。
- `random_seed`、モデル版、学習cutoff、参照データの最終日時を出力する。
- 全馬は**同じ試行のペース・馬場・環境**を共有する。勝者を各馬独立に決めない。
- 同じレース・設定・seed・モデル版・参照データなら予測が一致する。
- バックテストは大量試行になるため、履歴・騎手統計・前日馬場補正は1レース開始前にキャッシュ。隊列生成と線形回帰はベクトル化可能ならバッチ処理する。

---

## 10. 出力（JSON/CSV/予測画面）

### 10.1 レース全体

| フィールド | 定義 |
|---|---|
| `predicted_early_split_mean_sec` | シミュレーション抽選前半ラップの平均 |
| `predicted_early_split_p10_p90_sec` | 同10〜90%区間 |
| `reference_early_split_sec` | 学習期に基づくコース別標準前半ラップ |
| `pace_display_probabilities` | **抽選した連続値ペースを最後に5段階へ分類した比率** |
| `pace_delta_mean_sec` | 標準からの平均偏差。負=速い |
| `expected_winning_time_sec` | 10,000回の決着時計平均（時計モデル稼働時） |
| `winning_time_p10_p90_sec` | 決着時計の10〜90%区間 |
| `track_speed_adjustment_sec` | 過去開催実績から推定した当日馬場速度補正 |
| `track_reference_sources` | 前日／先週／前開催／前年の対象レース件数と参照日時 |
| `formation_summary` | 初期逃げ候補・内外・前後分布 |
| `simulations`, `seed`, `model_version`, `data_cutoff`, `warnings` | 再現性と監査 |

UIでは例えば「前半3F予測 35.2秒（P10〜P90：34.5〜35.9）／スロー31%、ミドル42%…」を表示する。ただし秒数・区分確率は**実モデルで計算**し、サンプル値を埋め込まない。

### 10.2 各馬

- `ability_score`：既存AI由来。
- `win_probability`：1着になった回数 / 10,000。
- `top2_probability`, `top3_probability`, `finish_position_distribution`。
- `conditional_win_probability_by_display_pace`：当該表示ペース区分で勝った回数 / その区分の抽選回数（0なら`null`）。
- `mean_horse_time_sec`, `horse_time_p10_p90_sec`：時計モデル稼働時。
- `mean_early_position`, `jockey_change_adjustment_summary`, `mean_lateral_slot`。
- `win_odds`, `expected_value`：ベット前に観測できたオッズがあるときのみ。
- `pace_condition_sample_count`：区分別勝率の母数。少ない区分は参考値フラグ。

**整合条件:** 各試行の勝者は1頭、全馬勝率の和は1、時計順と着順は一致、表示ペース確率合計は1、全体勝率はペース区分別勝率×発生率の加重和と一致。

### 10.3 JSON例（ダミー値）

```json
{
  "engine": "RACEVERSE",
  "version": "0.6",
  "race_id": "EXAMPLE_RACE",
  "simulations": 10000,
  "pace": {
    "reference_early_split_sec": 35.6,
    "mean_early_split_sec": 35.2,
    "mean_delta_sec": -0.4,
    "display_probabilities": {
      "VERY_SLOW": 0.04,
      "SLOW": 0.22,
      "MIDDLE": 0.42,
      "FAST": 0.26,
      "VERY_FAST": 0.06
    }
  },
  "winning_time": {
    "status": "estimated",
    "expected_sec": 94.8,
    "p10_sec": 93.9,
    "p90_sec": 95.9,
    "reference_source_counts": {
      "previous_day": 4,
      "previous_week": 5,
      "previous_meet": 0,
      "previous_year_same_season": 7
    }
  },
  "horses": [{
    "horse_id": "EXAMPLE_HORSE_A",
    "ability_score": 1.27,
    "win_probability": 0.2322,
    "conditional_win_probability_by_display_pace": {
      "VERY_SLOW": 0.33,
      "SLOW": 0.30,
      "MIDDLE": 0.24,
      "FAST": 0.18,
      "VERY_FAST": 0.09
    }
  }]
}
```

※ **すべて架空の形式例**。表示ペース確率と条件付き勝率の加重平均は `0.04×0.33 + 0.22×0.30 + 0.42×0.24 + 0.26×0.18 + 0.06×0.09 = 0.2322`。この例では他馬の情報を省略しているが、実装では全馬の勝率合計が1になることも検証する。

---

## 11. 学習・Walk-Forwardバックテスト

### 11.1 時系列学習（必須）

予測時点tに対して、以下を**tより過去の確定データ**だけで作る。

- 既存AI能力指標の時系列OOF値
- コース別前半基準ラップ・時計のベースライン
- 騎手別の位置取り先行度・逃げペース傾向
- 近走位置取り抽選候補と擬似隊列
- 線形ペース回帰・OOF残差分布
- 前日／先週／前開催／前年の馬場速度補正
- 決着時計予測モデル・OOF残差分布
- ペース適性、成長・休養、指数→着差変換の係数
- 5段階表示用の閾値

**ペース→時計モデルの2段階学習はリークに要注意。** 時計モデルの学習に使うペースは、**その学習レースの実ラップではなく、当時の情報だけで生成したOOF予測ペース**を用意する（学習時の真値と推論時の予測値の不一致を避ける）。同様に、直近馬場の残差推定に使う基準時計モデルも、対象参照レースを学習したモデルのin-sample残差で過度に楽観化しない。

### 11.2 時計モデルのトレーニング

- 教師値：各レースの確定勝ち時計 `official_winning_time_sec`。
- 説明変数：当該レース前に計算した馬場参照情報、コース・距離・クラス・馬場状態、**出走全馬の既存能力指標**、当時生成した擬似隊列、**OOF予測ペースの分布／抽選値**。
- 同一レースから複数隊列・ペースを生成する場合は**レース単位で合計重み1**とし、同一レース由来の行を別foldに混ぜない。
- 学習時にペースのノイズを抽選するなら、抽選ノイズも**当該時点で得られた残差分布**から生成する。単一レースに過剰な複製を作らない。
- 残差は過去の時系列OOFから推定し、距離・馬場・サンプル数に応じた不確実性を検証する。

### 11.3 バックテストの進め方

1. 学習期間までのデータで必要なモデル・統計を学習／取得する。
2. 対象レースを発走前に戻した状態で、過去開催の馬場時計参照を構成する。
3. 1万回の **隊列→連続値ペース→勝ち時計→着順／着差** シミュレーションを行う。
4. 予測レコードを書き出したあとに初めて、当該レースの実ラップ・勝ち時計・着順・払戻と照合する。
5. 時間窓を進め、既存AIと**同一対象レース、同一購入ルール、同一時点オッズ**で比較する。

### 11.4 評価指標

| タスク | 必須指標 |
|---|---|
| ペース回帰 | **前半ラップのMAE/RMSE（秒）**、ペース偏差のMAE/RMSE、予測区間の被覆率、残差偏り |
| ペース5段階表示 | 抽選比率の校正、カテゴリ別の予測発生率と実測発生率（**分類モデルのLog Lossを学習主指標にしない**） |
| 初期隊列 | 序盤通過順位MAE、先頭集団一致度（実順位は評価にのみ使用） |
| 馬場速度推定 | 前日／先週／前開催／前年の参照有無別で時計残差の偏り |
| 決着時計 | **勝ち時計MAE/RMSE（秒）**、P10〜P90区間被覆率、馬場・季節・コース別の誤差 |
| 勝率 | 勝者Log Loss、Brier、勝率帯別校正、上位馬勝率合計 |
| 着順 | 1着的中率、着順相関、Top3再現率 |
| 回収率 | 購入数、投資額、払戻額、単勝回収率、最大DD、オッズ帯別成績 |
| 比較 | 同一レースで既存Ranker単体との差分、年・コース・距離・頭数別 |

### 11.5 回収率計算とオッズ制約

```text
回収率(%) = 払戻総額 / 投資総額 × 100
期待単勝回収倍率 = RACEVERSE推定勝率 × 購入時点で観測可能な単勝オッズ
```

- まず同額100円単勝・所定のEV閾値で検証。閾値選択は**検証期間より前のチューニング期間のみ**で行う。
- 発走後に確定する最終オッズを「発走前に分かっていた」として使わない。適切な購入前オッズがないなら、確率の評価のみを正式結果とし、回収率は参考値と明示する。
- 極端な高配当レースへの依存と購入サンプル数を併記。10,000回は勝率推定器の統計的校正を保証しない。

### 11.6 アブレーション

同じ検証期間で少なくとも：

1. **Base:** 既存AI能力指標のみ。
2. **Formation:** Base＋過去走位置抽選＋騎手変更時差分＋馬番での内外配置。
3. **Continuous pace:** Formation＋学習済み**連続値ペース線形回帰＋残差抽選**。
4. **Time model:** Continuous pace＋**前日／先週／前開催／前年の馬場時計補正＋全馬能力を使う決着時計推定**。
5. **Full:** Time model＋ペース適性・コース馬場適性・成長／休み明け（実装されたもののみ）。

時計補正は勝率改善と時計MAE改善を**別々に評価**する。時計予測が良くても、必ずしも馬券回収率が上がるとは限らない。

---

## 12. 推奨モジュール分割

> パスは**提案**であり実在の既存パスではない。実リポジトリの命名に合わせる。

```text
raceverse/
    config.py                    # sim回数、重み、回帰・馬場参照設定
    schemas.py                   # Race / PastRun / Formation / SimulationResult
    adapters/
        existing_ability.py      # 既存能力指標の読み取り専用取得
        race_data.py             # JRA-VAN等の実データ接続
    history_features.py          # 厳密な時系列履歴特徴量
    formation_sampler.py         # 近走サンプリング・騎手変更補正・内外
    jockey_profiles.py           # 先行度・逃げ時ペース偏差
    pace_reference.py            # 過去ラップに基づく前半標準秒数
    pace_features.py             # 隊列から機械生成するペース特徴量
    pace_regression.py           # Ridge等：連続値前半ペース回帰
    pace_residuals.py            # OOF残差からの連続値抽選
    pace_display.py              # ユーザー向け5段階への事後変換
    meet_history.py              # 前日・先週・前開催・前年の抽出
    track_speed.py               # 比較可能な時計残差と馬場速度補正
    winning_time_model.py        # 出走馬能力・馬場・ペース→決着時計
    performance.py               # 条件付き相対性能・成長・着差
    simulator.py                 # 10,000回同時シミュレーション
    reports.py                   # 確率・ラップ・時計・開催参照情報
    backtest.py                  # 既存と独立のWalk-Forward
    cli.py                       # train / predict / backtest

tests/
    test_formation_sampler.py
    test_jockey_change.py
    test_early_formation.py
    test_pace_linear_regression.py
    test_pace_residual_sampler.py
    test_pace_display_bins.py
    test_meet_reference_selection.py
    test_track_speed_adjustment.py
    test_winning_time_consistency.py
    test_no_future_leakage.py
    test_simulation_invariants.py
    test_backtest_smoke.py
```

---

## 13. 設定ファイル例

```yaml
raceverse:
  version: "0.6"
  n_simulations: 10000
  random_seed: 42

  formation:
    max_history_runs: 10
    recency_weights: [10, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    group_threshold: 0.08
    lateral_order: horse_number_ascending
    missing_history_policy: explicit_prior_with_warning
    jockey_change_alpha: 0.40
    jockey_frontness_shrinkage_k: 30  # 仮値

  pace:
    target: early_split_delta_seconds
    model: ridge_regression
    ridge_alpha: 1.0               # 仮値。時系列の訓練内で調整
    training_formation_draws: 16
    residual_sampling: time_oof_residuals
    lead_tempo_shrinkage_k: 20     # 仮値
    early_section_rule: course_specific_comparable_split
    display_only_buckets:
      - VERY_SLOW
      - SLOW
      - MIDDLE
      - FAST
      - VERY_FAST
    display_thresholds: fit_on_past_training_period

  winning_time:
    enabled: true
    base_target: official_winning_time_seconds
    reference_windows:
      - previous_day
      - previous_week
      - previous_meet
      - previous_year_same_season
      - historical_course_prior
    previous_meet_primary_on_opening_week: true
    default_latest_usable_results: previous_day_end
    reference_deduplicate_by: race_id
    reference_similarity: [track, surface, course_layout, going, distance_band, class_group]
    normalize_reference_times: condition_adjusted_residuals
    use_field_ability: true
    use_sampled_continuous_pace: true
    fit_noise_from: time_oof_residuals
    insufficient_data_policy: fallback_prior_with_warning

  backtest:
    mode: walk_forward
    odds_policy: pre_bet_snapshot_only
    require_strict_asof_features: true
```

設定値は初期案であり、`ridge_alpha`、枠／隊列グループ閾値、窓の重み、抽選残差は**訓練側のみで調整**する。

---

## 14. 開発フェーズと受け入れ基準

### Phase 0 — リポジトリ・データ調査

- [ ] 既存AI能力指標の出力元・尺度・OOF取得方法を確認
- [ ] 全体ラップ／過去走コーナー順位／勝ち時計／馬場状態／開催ID・前開催の判定資料を確認
- [ ] 前日・先週・前開催・前年同時期の抽出ができるか調査
- [ ] 既存予測・バックテストの実行コマンドと回帰テストを記録
- [ ] 入手不能な項目の代替・欠損仕様を報告

### Phase 1 — 初期隊列と騎手プロフィール

- [ ] 近2走重み10・10、以後9〜2で過去走抽選
- [ ] 過去走の相対序盤順位を抽出
- [ ] 抽選元と今回の騎手が違うとき**だけ**先行度差で補正
- [ ] 前後グループと馬番小→内のルールを実装
- [ ] 同seed再現、異なる頭数、欠損、同枠をテスト

### Phase 2 — 連続値ペース回帰

- [ ] 過去ラップの区間長定義と基準ペースを実装
- [ ] **連続秒数の教師ラベル**を生成し、Ridge等の線形回帰を学習
- [ ] 隊列・騎手・外枠先行圧力の機械生成特徴量を用意
- [ ] 学習期にも当該レース前情報から疑似隊列を生成
- [ ] OOF残差を計測し、連続ペース抽選を実装
- [ ] **5クラス学習は行わず**、表示時だけ5段階へ集計
- [ ] 前半ラップMAE/RMSEと分布校正を報告

### Phase 3 — 馬場参照・決着時計

- [ ] 前日／先週／前開催／前年の参照抽出＋重複除去
- [ ] **開幕週は一つ前の同場開催**を優先的に参照
- [ ] 異距離・異クラスの時計を基準残差へ変換して集約
- [ ] 直近馬場変更に応じた重み・フォールバックを実装
- [ ] 出走馬全頭の既存能力指標と予測ペースを時計モデルへ入力
- [ ] **学習時にもOOF予測ペース**を使い、実ペースの予測時流用を防止
- [ ] 決着時計MAE/RMSEと予測区間被覆率を報告

### Phase 4 — 10,000回同時シミュレーション

- [ ] **近走抽選 → 騎手変更補正 → 序盤隊列 → 連続ペース抽選 → 勝ち時計抽選 → 着順／着差生成**を厳守
- [ ] 既存能力指標＋展開・成長の相対性能から全馬の着順を生成
- [ ] 各馬時計`T_i=T_win+margin_i`で整合を保つ
- [ ] 勝率、Top3、時計分布、表示ペース別勝率を出す
- [ ] 乱数再現性と処理時間を計測

### Phase 5 — 完全独立バックテスト

- [ ] 既存Rankerの予測・バックテストは変更せず維持
- [ ] 同じ未学習レースのペース秒数・決着時計・勝率・回収率を比較
- [ ] 馬場参照ソース別、開幕週別、雨天馬場変更別の時計誤差を分析
- [ ] 各機能のアブレーションで改善・悪化を確認
- [ ] 変更ファイル、テスト結果、残課題を報告

---

## 15. 自動テストの最低不変条件

1. 同じrace・データ・モデル・seed・設定なら出力は完全再現可能。
2. 直近1・2走の抽選重みが同率最大で、3走前以降は`9,8,…,2`と一律減少。
3. 抽選元騎手と今回騎手が同一なら `q_adjusted == q_sampled`。
4. 新騎手先行度が高ければqは前方向、低ければ後方へ（クリップ含む）。
5. 同じ前後グループの内外順位は**馬番昇順**。
6. ペース回帰は**隊列確定後**に実行し、実際の当該レース通過順位を入力に使わない。
7. ペース学習のターゲットは**秒の連続値**であり、5クラスラベルを教師にしない。
8. ペース連続値の残差抽選が設定seedで再現し、5分類は**抽選後**の表示変換に限られる。
9. ペース偏差が小さい（負）ほど速い表示区分に分類される。閾値の順序逆転を防ぐ。
10. 前日・先週・前開催・前年の候補は**予測対象より前の確定レース**のみ。未来レースを混入させたら検査失敗。
11. 開幕週に同場前週の開催がなければ**前開催へフォールバック**し、前年同時期情報も取得可能な範囲で使用。
12. 時計の比較は異なる距離・コース・クラスを**未補正の秒で平均しない**。
13. 参照窓間で同じrace_idを重複カウントしない。
14. 時計モデルには**当該試行の予測連続ペース**と**全出走馬の既存能力指標**が入力される。
15. 時計モデル学習時に当該レースの実ペース・同レース結果を説明変数として使わない。
16. 1シミュレーションにつき1頭だけが1着、着順は重複なし。
17. 各馬時計は`T_win + margin_sec`、勝者のmarginは0、他馬は非負。時計順と着順は矛盾しない。
18. `sum(horse_win_probabilities) == 1`、`sum(display_pace_probabilities) == 1`（許容誤差内）。
19. 表示ペース別勝率はカテゴリ出現回数を母数にして、0回ならnull。
20. 欠損参照レース・馬場変更・ラップ欠損・能力値欠損は明示的なログ／警告／ステータスを出す。
21. 発走前に取得不能だったオッズを事前購入に使用しない。
22. 既存AIの通常予測・バックテストの回帰テストがすべて成功する。

---

## 16. モデル上の注意・今後の拡張

- **ペースが連続値**なら、同じ「ハイペース」内でも前半34.1秒と34.8秒を異なる条件として扱える。5分類は解釈とUIのための後処理。
- レース全体ラップだけでは馬ごとの区間速度は観測できない。位置取り・上がり・着差から推定した展開適性は代理指標であり、区間の実測時計として表示しない。
- **隊列の分布とペースの回帰残差の両方が**シミュレーションの不確実性を作る。騎手変更以外に騎手変数を使って初期隊列を追加補正しない。
- 時計環境推定には当日の馬場状態だけでなく、**前日、先週、開幕週の前開催、前年同時期**を使用する。しかし過去開催の馬場速度が現開催に持ち越されるとは限らないため、間隔・馬場差・コース替わりで信用度を落とす。
- 時計モデルの予測が強い馬を選択するわけではない。**誰が勝つかは相対性能モデル**が選び、時計モデルはレースの時計水準を推定する。能力情報は両モデルに入るが、独立した役割を持たせ二重計上を避ける。
- 馬券回収率と時計精度と確率校正は別々に監視する。10,000回で得た比率には、モデル誤差・データ不足・馬場変化が残る。
- 将来はペース回帰の非線形モデルとの比較、馬場速度のオンライン更新、騎手×馬の相性、馬連・三連単の全着順確率、コース替わり効果の精緻化などを検討できるが**v0.6初期実装の必須範囲に増やさない**。

---

## 17. Copilotへの最終実装依頼（そのまま貼り付けてよい）

> このMarkdownをRACEVERSE v0.6の**唯一の正本仕様書**として読み、既存競馬AIリポジトリの構造を最初に調査してください。実在しない関数・カラムを推測で作らず、データ対応表を作成してください。既存能力指標を再利用し、既存予想・既存バックテストに影響しない独立パイプラインを実装してください。
>
> シミュレーションは**「近2走優先の過去走サンプリング → 抽選元と今回の騎手が違う場合だけ先行度差分補正 → 前後グループと馬番順の内外位置確定 → 隊列・騎手テンポ・外枠先行圧力等から学習済み線形回帰で前半ペースの秒数を予測 → OOF残差分布から連続値ペースを抽選 → 馬場状態＋前日・先週・開幕週の前開催・前年同時期の補正済み実時計＋全馬の既存能力指数＋予測ペースから決着時計を予測・抽選 → 全馬の条件付き相対性能・着差・時計・着順を確定」**の順で1万回繰り返してください。
>
> **ペースの5分類はUI・結果集計時のみ**。5クラス分類モデルは作らないでください。ペース教師値・時計教師値は実ラップと実時計の**連続値**です。馬場・ペース・能力の時計寄与は過去データから推定し、任意の秒数を加算しないでください。対象レース・未来の情報を学習特徴量に混ぜず、Walk-ForwardでMAE/RMSE・校正・着順・回収率を既存AIと比較してください。各Phase完了時にテストを実行し、最終的に変更一覧、コマンド、結果と未完了事項を報告してください。

# RACEVERSE v0.6

既存競馬AI(LightGBM Ranker)の能力指標を**読み取り専用**で再利用し、
「過去走位置取りの抽選 → 騎手変更補正 → 序盤隊列 → 連続値ペース → 決着時計 → 各馬の走破性能・着順」
を1レース10,000回モンテカルロで再現して勝率・展開・時計を出す独立エンジン。
既存の学習・予測・バックテスト(`src/`)は変更していない。仕様は `RACEVERSE_v0.6_Copilot_Implementation_Spec.md`。

## 構成

```text
raceverse/
  config.py            設定(configs/raceverse.yaml で上書き)
  adapters/
    race_data.py       race.db(JRA-VAN) -> races / runs
    existing_ability.py 既存Rankerの能力指標(月次Walk-ForwardのOOF)
  baselines.py         月次Walk-ForwardのRidge基準(基準勝ち時計 / 基準前半ラップ)
  history_features.py  as-of 履歴(近走の序盤位置・騎手・上がり・休養)
  jockey_profiles.py   騎手の先行度・逃げ時ペース傾向(月次スナップショット)
  formation_sampler.py 近2走重視の過去走抽選・騎手変更補正・前後グループと馬番順の内外
  pace_features.py     隊列・Pace Impactから機械生成するペース特徴量(先頭/2-3番手/先行集団/内外/全頭分布)
  pace_impact.py       馬・騎手のPace Impact(実隊列の時系列OOF残差を役割別に縮小推定、馬と騎手はバックフィッティングで分離)
  pace_correlation.py  馬・騎手のペース相関(条件調整後の残差と先頭/先行フラグ。サンプル不足は数値を出さない)
  pace_regression.py   連続値(秒)の前半ペース Ridge 回帰 + ローリングOOF
  pace_residuals.py    表示閾値・ペース予測範囲(PaceBounds)・時計残差サンプラー。ペース自体は乱択しない
  pace_display.py      表示用5段階(事後分類のみ)
  meet_history.py      前日 / 先週 / 前開催(開幕週) / 前年同時期の参照抽出
  track_speed.py       馬場速度補正(基準時計との残差を頑健集計)
  winning_time_model.py 決着時計モデル(Ridge)
  performance.py       各馬の相対走破性能(レース内中心化の時計偏差)
  course_bias.py       コース別の脚質・枠順バイアス(as-of階層ベイズ縮約)と走破性能用の特徴量(formation_bias / pace_bias)
  bias_eval.py         コースバイアス追加版の評価(相対走破時計MAE/RMSE・コース/脚質/枠番別の改善度)
  store.py / training.py / pipeline.py  学習ストア・月次再学習・キャッシュ
  simulator.py         10,000回同時シミュレーション
  evaluation.py / backtest.py  独立Walk-Forwardバックテスト
  reports.py / cli.py  出力(JSON/CSV/Markdown)・CLI
```

## 実行方法

すべて `.venv/bin/python` で実行する(素の `python3` には依存が無い)。

```bash
# 0. 既存Rankerの過去OOF能力値(初回のみ。既存コードは呼び出すだけ。数分)
.venv/bin/python -m raceverse.adapters.existing_ability --start 2022-09-01 --end 2025-09-01

# 1. キャッシュ作成(データ読込・基準モデル・疑似隊列ストア)
.venv/bin/python -m raceverse.cli prepare

# 2. 未開催レースの予測(出力: reports/raceverse/predict_YYYYMMDD/*.json|csv|md)
.venv/bin/python -m raceverse.cli predict --date 2026-10-10 --days 2 --sims 10000
#   ペース込み予測: --level pace (既定は formation)
.venv/bin/python -m raceverse.cli predict --date 2026-10-10 --days 2 --level pace
#   未開催レースの良・稍重・重・不良を独立計算して保存:
.venv/bin/python -m raceverse.cli --config configs/raceverse_weekly.yaml predict \
    --date 2026-10-25 --days 1 --level pace --going-scenarios

# 3. 確定済みレースを当時の情報だけで再現(検証用)
.venv/bin/python -m raceverse.cli simulate --race-id 2025-0906-01-02-05-09
#   再現レベルは formation (既定) または pace。full は利用できない。

# 4. 独立Walk-Forwardバックテスト(既存Rankerと同一期間・同一レース・同一馬)
.venv/bin/python -m raceverse.cli backtest --sims 10000
#   高速確認: --sims 1000 --max-races-per-month 40 --out /tmp/bt
#   レベル指定: --levels base,formation,pace
#   コースバイアス追加版との比較: --levels formation,formation_bias,pace,pace_bias

# 5. 週次再学習版(先週までの結果で今週を予測。月次版は変更なし)
.venv/bin/python -m raceverse.adapters.existing_ability --weekly --start 2019-01-01 --end 2026-09-01
.venv/bin/python -m raceverse.cli --config configs/raceverse_weekly.yaml backtest \
    --start 2021-09-01 --end 2026-09-01 --levels base,formation,pace --out reports/raceverse/weekly_5y_202109_202609
#   refit_unit: week で、Ranker能力指標・ペース/時計/走破性能モデル・騎手プロフィール・基準モデル・勝率校正を
#   週(月曜始まり)ごとに更新する。ability_source: weekly は週次のRanker OOFだけを使う。
#   出力先は `backtest_` で始まらない名前にする(cli.latest_gamma が backtest_*/ の最新を本番予測の校正に使うため)。
```

`predict --going-scenarios` は未開催レースだけを馬場コード1〜4で再計算し、`*_going-1` 〜 `*_going-4` のJSON/CSV/Markdownを出力する。基準時計・前半基準・馬場速度・コースバイアス・ペース・走破性能を各条件で再評価する。`simulate` と `backtest` は従来どおり実馬場1条件のみ。未開催出走馬にRanker能力値がない場合、馬は除外せず能力を中立値で補完し、予測レポートに件数を警告する。

## Ranker能力閾値・牝馬限定戦補正のWalk-Forward検証

週次Walk-Forward予測とRankerの週次OOF能力スコアを再利用し、Top1確率のソフト減衰、
購入候補だけのハード除外、閾値未満を確率0にして閾値超過分で傾斜するzero-tilt、
牝馬限定戦の実効クラス補正を比較する。
評価区分は2021〜2024年(開発)、2025年(選択)、2026年(最終評価)。
Top1確率のBrier scoreを主基準、Winner Loglossを同点時の比較として2025年に選択する。
zero-tiltの閾値位置・傾斜強度・確率温度と、既存の週次校正確率への追加 power gamma も比較する。
ゼロ確率にした勝ち馬数と厳密Winner Logloss(該当時は無限大)も併記する。
ハード除外は購入候補だけに適用し、zero-tiltで能力欠損時は元確率を残す。
zero-tiltで全頭が閾値未満のレースは、元の確率へフォールバックする。
クラス判定は確認済みの GradeCD / 明示的な条件名のみを使い、1着賞金帯をクラス扱いしない。
牝馬限定戦はレース名の明示マーカーでのみ判定するため、未検出分があり得る。

```bash
PYTHONPATH=. .venv/bin/python scripts/raceverse_ability_threshold_analysis.py
```

既定の入力は `reports/raceverse/weekly_5y_202109_202609/predictions.csv` と
`data/cache/raceverse/ability_oof_weekly.parquet`。Markdown・CSVは
`reports/raceverse/ability_threshold_202109_202609/` に出力する。

未開催レースの予測には `output/predictions.csv`(本番Ranker出力。`src.ranker_production_predict` で生成)の
`ranker_score` を能力指標として使う。能力指標が無い馬は除外し(4頭未満ならスキップ)、警告を出す。

## テスト

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p "test_raceverse*.py"
# 既存AIの回帰テスト
PYTHONPATH=. .venv/bin/python -m unittest tests.test_ranker_production_parity
```

`tests/raceverse_fixtures.py` の合成データはテスト専用で、実データの結果とは混ぜない。

本番の `predict` / `simulate` は `formation` を既定とし、`formation` / `pace` / `formation_bias` / `pace_bias` を選択可能。
勝率・走破性能モデルの `full` は廃止し、学習・予測・バックテストでは使用しない。
過去の予測・検証成果物は記録として保持する。決着時計モデル内部の `full` は別機能であり、引き続き使用する。

## コースバイアス(formation_bias / pace_bias)

目的変数(各馬の走破時計 - 出走馬平均)と既存特徴量(`ability_c`, `q_c`, `slot_c` ほか)は変えず、走破性能モデルに説明変数を足した版。

- 統計の単位: 競馬場 x 芝/ダート x 距離 x 内外回り(`TrackCD`) x 芝の使用コースA-D(`CourseKubunCD`) x 開催時期(前半/中盤/後半) x 馬場状態、
  および同開催(開催回)のこれまでの開催日。脚質(逃げ/先行/差し/追込)と枠番(1-8)ごとに、出走数・1着数・3着以内数を集計する。
- 実績 / 期待(勝利=1/頭数、複勝=3/頭数)の比率を、馬場種別 -> コース -> 使用コース -> 開催時期x馬場 -> 同開催の順にベイズ縮約し、対数比率を特徴量にする。サンプル数は `RaceBias` とレース出力 `course_bias_sample_counts` に保持する。
- リーク防止: 予測対象レースの日付より前の確定結果だけを使う(同日は使わない)。実際の脚質(`KyakusituKubun`)は使わず、過去走の序盤位置から脚質を付ける。予測側の脚質はシミュレーションで抽選した序盤位置(先頭1頭=逃げ)から決める。
- 追加特徴量(すべてレース内中心化): `style_win_bias_c`, `style_place_bias_c`, `draw_win_bias_c`, `draw_place_bias_c`, `style_draw_interaction_c`(formation_bias 以降)、
  `pace_style_win_bias_c`, `pace_style_place_bias_c`, `pace_draw_interaction_c`(pace_bias のみ。抽選したペース(速/中/遅)ごとの同コース比差分)。
- 全レベルの走破性能モデルには、良を基準とした `ability_c × 馬場状態(稍重/重/不良)` の交互作用も含む。係数は過去の走破時計偏差からWalk-Forwardで学習し、手動の馬場係数は使わない。
- 勝率・複勝率は勝敗確率に直接掛けず、Ridge の説明変数としてのみ使う。
- 検証結果(2025-10〜2026-09, 1545レース): 相対走破時計の誤差は微減だが、勝率・Top1・回収率の改善は確認できなかった。詳細は `reports/raceverse/backtest_course_bias_202510_202610/summary.md`。

## 実データ対応表

| 論理項目 | 実カラム |
|---|---|
| race_id | `idYear-idMonthDay-idJyoCD-idKaiji-idNichiji-idRaceNum`(`src.backtest.race_id` と同形式) |
| 芝/ダ | `TrackCD` 10-22=芝, 23-29=ダート, 51-59=障害(対象外) |
| 距離 / コース形態 | `Kyori` / `TrackCD`+`CourseKubunCD` |
| 馬場 | 芝 `TenkoBabaSibaBabaCD`, ダ `TenkoBabaDirtBabaCD` (1良 2稍重 3重 4不良) |
| 開催 / 開催日 | `idYear-idJyoCD-idKaiji` / `idNichiji` |
| クラス | `Honsyokin0`(100円単位)の賞金帯 + `GradeCD` |
| 前半ラップ | `HaronTimeS3`(先頭3ラップ合計)。区間長は `first_lap_m + 400`(200mの倍数なら600m、端数距離は500m等)をメタデータとして保持 |
| 勝ち時計 | `NL_SE_RACE_UMA.Time`(MSST)の1着 |
| 序盤位置 | `Jyuni1c..4c` の最初の有効値。`q=(rank-1)/(n-1)` |
| 騎手 | `KisyuCode` |
| 能力指標 | 既存Rankerの `ranker_score`(raw) |
| 初角までの距離 | `data/output/course_features_ver6.csv` の `first_corner_distance_m` |

## 設計上の要点

- **リーク防止**: 履歴は馬ごとに日付昇順で直前k走だけ、騎手統計・基準モデルは月次スナップショット(当月は見ない。`refit_unit: week` なら週次で当週は見ない)、
  馬場参照は対象日より前の確定レースのみ、能力指標は月次(週次設定なら週次)Walk-ForwardのOOF、
  時計・走破性能の学習に使うペースは当時の情報だけで作った時系列OOF予測。
- **ペースは連続値かつ乱択なし**: 教師値 `actual_early_split - reference_early_split`(秒, 負=速い)をRidge回帰。
  確定した全頭隊列と馬・騎手のPace Impactから回帰した値がそのままペースになり、同じ隊列・騎手・開催条件なら同じ値。
  10,000回の分布は隊列の抽選だけから生まれる。5段階は表示用の事後分類(境界値は学習期の分位点で固定)。
- **Pace Impact**: `impact = n/(n+lambda) * mean(eps - 相手側のimpact)`。epsは実隊列の構造回帰の時系列OOF残差。
  役割(lead/chase/front)別、月mのスナップショットは月mより前のレースだけ。因果ではなく調整後の関連度。
  診断・新旧比較は `scripts/raceverse_pace_impact_analysis.py` と `scripts/raceverse_pace_compare.py`。
- **馬場速度**: 参照レースの勝ち時計 - as-of基準時計 の残差(距離・コース・クラス・馬場を補正済み)を、
  窓の優先度・新しさ・条件類似度の重みで集約し0へ縮小。前日→先週→前開催(開幕週は必ず)→前年同時期→コース事前値。
- **決着時計と着順の整合**: 各馬の時計偏差を一括で生成し、勝者の偏差を引いた差が着差。`T_i = T_win + margin_i`。
- **確率の校正**: 直前6か月のバックテスト予測だけで `p^gamma` を決め、生の確率と校正後の確率の両方を報告する。

## 制約・未実装(詳細は reports/raceverse/ の各サマリー)

- DBのオッズは確定オッズで、発走前スナップショットではない。回収率は参考値(仕様11.5)。
- 馬ごとの200m区間ラップは無いため、ペース適性は過去の上がり相対(代理指標)のみ。
- 序盤位置は最初の有効コーナー(短距離は3角)で、真の序盤通過とは一致しない場合がある。
- 参照レースの時計残差は参照レース自身のペース・出走馬質を除去していない(時計モデルが bias の係数を学習)。
- 能力指標の過去OOFは `2022-09` 以降のみ生成。時計・走破性能モデルの学習はこの期間に限られる。

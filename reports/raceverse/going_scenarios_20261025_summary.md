# RACEVERSE 馬場別4シナリオ予測 — 2026-10-25

## 結果要約
- 出力: 35レース x 4条件 = 140シナリオ。障害競走1レースは平地モデルの対象外。
- 馬場依存入力が変化したレース: 35/35。
- 校正後勝率ベクトルが条件間で変化したレース: 35/35。
- 馬場で本命(校正後勝率1位)が変化したレース: 15/35。
- 勝率合計誤差最大: p_cal=2.22e-16, raw=2.22e-16。
- Ranker能力値欠損の馬: 438頭。中立補完し、全出走馬を保持。
- 発走前オッズ参照: すべて遮断。
- 使用可能な確定結果は2026-10-18まで。2026-10-24の確定結果がDBに無いため使用していない。
- 走破性能の馬場影響: 過去データから学習する ability × 馬場交互作用。ROIや精度向上を実証済みとは扱わない。
- 2025-01〜2026-08の時系列ホールドアウト(2024-12以前で学習、31,191頭)では相対時計MAEがbase 0.563447→0.563298秒、formation 0.562941→0.562801秒、pace 0.561634→0.561519秒。改善は小さく、勝率/ROI改善の証明ではない。詳細: `reports/raceverse/going_interaction_holdout_2025_202609.csv`。
- 438頭は本番Ranker能力スコアを取得できず中立補完。確率は出力したが、該当レースでは能力差による予測効果が限定される。

## 出力
- レース別JSON/CSV/Markdown: `reports/raceverse/predict_20261025_going_scenarios/`
- シナリオ別集計CSV: `reports/raceverse/going_scenarios_20261025_summary.csv`
- Web表示データ: `docs/data/raceverse/latest.json`

## 再生成
```bash
PYTHONPATH=. .venv/bin/python -m raceverse.cli --config configs/raceverse_weekly.yaml predict --date 2026-10-25 --days 1 --sims 10000 --level pace --going-scenarios --out reports/raceverse/predict_20261025_going_scenarios
PYTHONPATH=. .venv/bin/python scripts/build_raceverse_site_data.py --reports-dir reports/raceverse/predict_20261025_going_scenarios
```

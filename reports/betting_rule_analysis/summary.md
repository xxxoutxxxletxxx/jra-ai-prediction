# 本命単勝 買い目ルール分析

## データ
- v0: 現行統計モデル 12ヶ月 walk-forward（2025-09〜2026-08、全レース）`reports/backtest_12m_v0/predictions.csv`
- ranker: LightGBM Ranker 12ヶ月 walk-forward（同期間、1着賞金800万円超レース）`reports/ranker_walk_forward_12m/walk_forward_predictions.csv`
- いずれもAI本命（prediction_rank=1）の単勝100円買いで評価。

## 採用ルール（src/betting_rules.py）
- オッズ 3.0 倍未満: 予測勝率 40% 以上のみ購入
- オッズ 5.0〜20.0 倍: 購入（ボリューム帯）
- 上記以外（3〜5倍・20倍以上・オッズ未取得）: 見送り

## ルール適用シミュレーション
- v0: 全買い 3234点 ROI 71.8% → ルール適用 1257点 ROI 82.8%（損益 -21,660円）
    内訳 3倍未満&勝率40%以上: 213点 ROI 83.4% / 5-20倍: 1044点 ROI 82.6%
- ranker: 全買い 1627点 ROI 69.7% → ルール適用 442点 ROI 73.0%（損益 -11,930円）
    内訳 3倍未満&勝率40%以上: 102点 ROI 91.9% / 5-20倍: 340点 ROI 67.4%

## 注意
- 現状のモデルでは採用ルール適用後も単勝ROIは100%未満。
- このルールは損失削減のフィルタであり、黒字化の根拠ではない。
- 詳細は odds_band_performance.csv / low_odds_threshold_test.csv / rule_simulation.json を参照。

# EV Betting Analysis

## Scope
- 1着本賞金800万円以下を除外した既存CBバックテスト予測のみを使用。モデル・特徴量・ランキングは変更していない。
- DBの単勝オッズは10倍表記のため、EVは `win_odds = odds / 10` で計算。
- 評価月: 2026-07, 2026-08; discovery: 2026-07; validation: 2026-08。

## Probability
- レース内の生確率和: min 0.365, max 1.612, mean 0.946。
- `normalized_win_probability` は各レース内で合計1.0となる分析用の相対勝率であり、Calibration確認前に真の勝率とはみなさない。

## Calibration
- `win_probability_calibration.csv` と `calibration_method_comparison.csv` は、前半でfitし後半で評価している。
- 後半Brier: normalized 0.06824, Platt 0.07036, isotonic 0.06835。
- Platt/isotonicは正規化値を改善しなかった。後半15-20%帯も予測17.4%に対し実績23.9%で、勝率を真の確率として固定しない。

## Validation Strategy Snapshot
- Strategy 0 baseline: bets 75/75, hit 0.29333333333333333, ROI 84.66666666666667, profit -1150 yen, max DD 1780 yen
- Strategy 1 max EV: bets 75/75, hit 0.08, ROI 66.13333333333333, profit -2540 yen, max DD 3900 yen
- Strategy 2 max EV + EV>1: bets 62/75, hit 0.08064516129032258, ROI 71.93548387096774, profit -1740 yen, max DD 3700 yen
- Strategy 3 max positive edge: bets 70/75, hit 0.07142857142857142, ROI 63.714285714285715, profit -2540 yen, max DD 4200 yen

## Interpretation
- 後半ではTop1がROI 84.67%に対し、勝率10%以上でEV最大は66.13%、EV>1でも71.94%であり、EV最大化はベースラインを改善しなかった。
- `EV>1` は75件中62件へ購入を減らしたが、利益・最大ドローダウンともTop1より悪く、見送りの有効性は確認できない。
- gap上位10%は後半9件でROI 87.78%だが、前半でも71.33%で、サンプルが小さく採用根拠には不足する。断層は的中率を上げる傾向でもROIは改善していない。
- 後半のDIFFERENTは73件・ROI 358.9041095890411であり、高配当1件の影響を受けやすい。Top1以外をEVだけで選ぶ価値は未確認。
- 最もROIが高い条件を全期間で採用しない。`strategy_comparison.csv` のdiscovery候補を、同じ閾値のvalidation行で確認する。
- この分析は購入候補の検証までであり、本番購入ルールは変更していない。

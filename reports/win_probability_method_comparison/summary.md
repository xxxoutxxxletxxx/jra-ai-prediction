# Win Probability Method Comparison

## Design
- Common features: existing CLEANUP_B_FEATURES; common seed: 42; target condition: first prize > 8,000,000 yen.
- Train: 2023-08 through 2025-07. Temperature calibration: 2025-08 through 2025-12. Final validation: 2026-01 through 2026-08.
- Odds use `win_odds = odds / 10`. Temperature is selected only on calibration; validation is not used for tuning.

## A. Win Probability Accuracy Ranking
1. ranker: Brier 0.064591, LogLoss 0.235782, ECE 0.004393, AUC 0.759984, Top1 24.09%, Top3 54.34%
2. bt: Brier 0.064902, LogLoss 0.237408, ECE 0.004282, AUC 0.753863, Top1 23.36%, Top3 52.23%
3. pl: Brier 0.065130, LogLoss 0.239655, ECE 0.003859, AUC 0.744641, Top1 23.44%, Top3 52.47%

## B. Betting Performance Ranking
1. bt: ROI 78.26%, profit -26810 yen, bets 1233/1233, max DD 29830 yen
2. ranker: ROI 75.20%, profit -30500 yen, bets 1230/1233, max DD 41200 yen
3. pl: ROI 71.97%, profit -34530 yen, bets 1232/1233, max DD 36720 yen

## Direct Answers
1. 実際の勝率に最も近い方式: ranker。Brier/LogLoss/AUC/Top1/Top3で首位だが、BT/PLよりECEはわずかに高い。
2. 単勝ROIが最も高い方式: bt（78.26%）。ただし100%未満で、購入用途として採用できる利益性は未確認。
3. 高配当依存: bt の最大1件・3件を除くROIは 71.37% / 67.46%（全件 78.26%）。最大払戻への依存はあるが、元から利益化していない。
4. Top1/Top3性能は `calibration_comparison.csv` のvalidation行を参照。順位性能はRankerが首位。
5. 勝率10%以上＋最大EVでは bt が最良だが、ROI 78.26%で改善未達。
6. EV>1の追加は Ranker 75.20%→77.69%、BT 78.26%→77.54%、PL 71.97%→68.85%。Ranker以外では悪化し、いずれも収益化しない。
7. gapとTop1的中の相関: Ranker 0.208, BT 0.179, PL 0.172。断層はRankerが最も実勝率と対応。
8. 勝率推定用途の候補: ranker。ただしvalidationで再校正された方式ではなく、固定temperatureによる結果であり継続監視が必要。
9. 馬券購入用途の候補: なし。最高ROIのBTも100%を下回り、月別安定性・高配当除外後の双方で採用根拠がない。

## Interpretation
- Accuracy and ROI rankings are intentionally separate. Do not promote the highest-ROI method to production without validation stability and payout-sensitivity confirmation.
- `high_payout_sensitivity.csv` reports ROI after removing the largest one and three payouts; use it to reject one-hit ROI gains.
- This is an experiment only and does not modify the production purchase rule.

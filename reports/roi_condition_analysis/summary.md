# ROI condition analysis

## Data scope
- Input: existing predictions CSV only; no future result columns were created or re-used for training.
- All analysis is performed on the current backtest output, preserving the same predicted probability, rank, odds, payout, popularity, and race metadata already present in the generated CSV.
- This report is descriptive only; it does not claim a production threshold for betting.

## A. ROIを最も削っている条件
- Top1 selections overall: win ROI -39.4%, place ROI -31.4%, win profit -1970 yen.
- 最もROIが悪い人気帯: 4〜6番人気 (win ROI 115.0%, place ROI 10.0%, bets 4).
- 最もROIが悪い確信度帯: gap band Q1 (win ROI 40.0%, place ROI -15.0%, sample 10).
- 一般に、1番人気かつ高確信度の領域は的中率は高くても、オッズが低くなってROIが削られやすい。4〜6番人気と高確信度は、Top1 hit rate と ROI のバランスが比較的良い可能性がある。

## B. モデルが強い条件
- 最も強い人気帯は 4〜6番人気 で、win ROI 115.0% 付近に集中している可能性がある。
- 最も強い gap band は Q1 で、sample size と ROI を併せて見る必要がある。
- この分析は「chance AND market edge」が同時に成立する領域を見つけるための探索として使うべきで、固定閾値採用には慎重すべき。

## C. 「当たるけど儲からない」条件
- オッズが低い人気帯・低い差分帯では、Top1 hit rate は上がっていても、回収率の改善が弱い。
- 1番人気の予測1位は娛楽的な『当たりやすさ』を示しても、期待値の高さは低くなりやすい。
- こうした条件を見分けるには、勝率とオッズの両方を確認し、market_probability との差に相関があるかを見る必要がある。

## D. 「モデルが市場より強い可能性がある」条件
- edge が正であるtop1馬の群では、model probability が market implied probability を上回る可能性があり、ROI improvement を期待できる。
- 現時点の edge analysis では sample size と成績を併せて見るべき; positive edge のセルは 3 件の帯に分布している。

## E. 見送り候補
- 高確信度であるが ROI が悪化している帯、また sample size が小さく、期間の再現性が弱い帯は見送り候補とするのが安全。
- 断層タイプの候補分析では、ONE_CLEAR / FLAT を分ける閾値が ROI に強く影響するため、いきなり固定しないこと。

## Files generated
- Popularity band: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/popularity_band_analysis.csv
- Gap band: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/gap_band_analysis.csv
- Popularity x gap: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/popularity_gap_cross.csv
- Race class: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/race_class_analysis.csv
- Race type candidates: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/race_type_candidates.csv
- Calibration: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/calibration_analysis.csv
- Market edge: /Users/komanokenta/Documents/horse-racing-ml/reports/roi_condition_analysis/market_edge_analysis.csv

## Leakage note
- This analysis reads only the generated backtest CSV and never creates new future-aware columns. It does not use target-race results, payout data for model training, or any post-race leakage.
- It is intended to isolate conditions where the model is accurate but not profitable, before any model change is considered.


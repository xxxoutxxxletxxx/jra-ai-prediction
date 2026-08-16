# Concentration Analysis

## Overall
- Races: 432
- Top1 win rate: 26.39%
- Top2 box hit rate: 12.96%
- Top2 exact order rate: 6.25%
- Top3 box hit rate: 6.25%
- 馬連/馬単は予測CSVに払戻列がないため、的中率のみ計算し、配当・ROIはN/A。

## Recommendation exploration
分類は同一期間のpercentileを使った探索用であり、固定閾値・自動購入判断ではありません。
| Type | Races | Top1 | Top2 box | Top2 order | Top3 box |
|---|---:|---:|---:|---:|---:|
| CHAOTIC_SKIP | 87 | 18.39% | 6.90% | 4.60% | 4.60% |
| FLAT_VALUE | 38 | 21.05% | 10.53% | 5.26% | 10.53% |
| ONE_HORSE | 31 | 51.61% | 6.45% | 6.45% | 6.45% |
| THREE_HORSE | 37 | 29.73% | 18.92% | 10.81% | 16.22% |
| TWO_HORSE_CONCENTRATED | 24 | 41.67% | 25.00% | 8.33% | 12.50% |
| UNSET | 215 | 24.65% | 14.42% | 6.05% | 3.72% |

## Gap analysis
gap_1_2 / gap_2_3 / gap_3_4 とTop2・Top3独占率、順序一致率、ROIは各 *_analysis.csv を参照。

## Leakage and odds
予測確率・収束度はオッズを使わず計算。オッズは後段のfair odds/edge分析だけに使用。結果列は評価専用で、特徴量生成には使用しない。

## Interpretation
Top2 boxは予測上位2頭が実際の1・2着を占めた割合、Top3 boxは予測上位3頭が実際の1～3着を占めた割合。サンプル数とpercentile分布を併記し、収束度を因果的な確信度とは断定しない。

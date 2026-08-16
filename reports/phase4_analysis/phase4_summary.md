# Phase 4

Model E adds raw/adjusted performance, position advantage, race position bias, hidden strength, strong-against-bias, and setup improvement to Model D.

- odds_5_plus: races 432, win 27.08%, top2 43.75%, top3 56.48%, win ROI 80.6%, place ROI 77.4%
- odds_10_plus: races 432, win 27.08%, top2 43.75%, top3 56.48%, win ROI 80.6%, place ROI 77.4%
- hidden_and_setup: races 778, win 6.04%, top2 11.83%, top3 18.38%, win ROI 69.8%, place ROI 69.7%

展開補正だけで穴馬と断定せず、着差・賞金・相手強度と併用する。オッズは評価専用で、Model E特徴量には使用しない。

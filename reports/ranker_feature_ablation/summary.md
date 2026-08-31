# Focused Ranker Ablation

## Method
- Screen: 2026-08 only with the baseline's prior-only temperature (T=0.7); it selects candidates without accessing later outcomes.
- Full year: only the highest ranked screen candidate that improves ROI while keeping Brier within +0.0005 of baseline is run with monthly retraining. It uses the saved baseline's per-month, prior-only temperatures to avoid a second calibration-model training pass.
- The screen chooses candidates, not a deployable purchase condition.

## Full-Year Results
- baseline: Brier 0.064461, AUC 0.761456, Top1 24.89%, ROI 69.73%, EV>=1 ROI 58.67803837953092, removed none
- drop_prize_ratio_vs_last3_mean: Brier 0.064490, AUC 0.761172, Top1 24.77%, ROI 69.18%, EV>=1 ROI 59.044585987261144, removed prize_ratio_vs_last3_mean

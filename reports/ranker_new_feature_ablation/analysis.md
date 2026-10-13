# Ranker new feature group analysis

## group_marginal_effects

group  mean_logloss_delta  mean_brier_delta  mean_top1_delta  pairs_improved_logloss  pairs_worsened_logloss  pairs_total
   G1           -0.002261         -0.000043         0.000350                       7                       1            8
   G2           -0.000065          0.000017        -0.001608                       4                       4            8
   G3           -0.021582         -0.000197        -0.010137                       8                       0            8
   G4           -0.004464         -0.000078        -0.001608                       8                       0            8

## pair_interactions

group_pair  mean_logloss_interaction
   G1 x G2                  0.001546
   G1 x G3                 -0.001446
   G1 x G4                  0.000628
   G2 x G3                 -0.000255
   G2 x G4                  0.002543
   G3 x G4                  0.000843

## monthly_effects

group  months_improved  months_worsened  month_comparisons
   G1               54               42                 96
   G2               52               44                 96
   G3               85               11                 96
   G4               65               31                 96

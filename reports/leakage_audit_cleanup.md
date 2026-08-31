# Cleanup Leakage Audit (Step 2)

## Status

Race Bias features are SAFE only as historical features: source race P is processed after P ends, then stored for future target R. The current target race results are not used to create its own features.

| Feature | Source | Result use | Temporal status |
|---|---|---|---|
| `position_bias_top5_v2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `position_bias_top6_v2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `position_bias_weighted_top6_v2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `position_bias_residual_v2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `race_position_bias_last1` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `race_position_bias_last2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `race_position_bias_last3` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `strong_against_bias_v2_last1` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `strong_against_bias_v2_last2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `strong_against_bias_v2_last3` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `adjusted_performance_v2_last1` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `adjusted_performance_v2_last2` | prior source race history | source race result only, never target row | SAFE under date-batched state update |
| `adjusted_performance_v2_last3` | prior source race history | source race result only, never target row | SAFE under date-batched state update |

Residual note: expected rank is computed from pre-race accumulated wins/races. It is not fit on the target race result.
Target result columns remain evaluation/history inputs only and are excluded from model feature lists.

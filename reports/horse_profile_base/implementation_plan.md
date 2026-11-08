# Horse Profile / BASE implementation plan

Scope: build a research-only Horse Profile and independent Horse-only BASE through time-ordered evaluation. Do not switch production or fold profile fields into the existing Ranker.

## Phase 0 — Audit and evaluation contract

- [x] Confirm actual SQLite tables/columns and record status.
- [x] Measure core field availability on confirmed JRA starts from 2015 onward.
- [x] Record point-in-time limitations and disable unverified latent axes/priors.
- [ ] Reproduce the target race IDs and existing-model baseline under one explicit evaluation contract.

## Phase 1 — Outcome normalization

- Add a typed run representation and deterministic `E = T - L3`, `D600` derivation.
- Preserve missing sectionals and expose whether the observed field establishes the true leading `E`.
- Fit condition baselines using only training-period data; test unit conversions, missingness, and cutoff invariance.

## Phase 2 — Horse Profile v1

- Add an as-of profile snapshot with condition-aware time and closing estimates, support counts, uncertainty, lineage, and coverage flags.
- Shrink sparse histories toward population-level estimates; leave start and sustain ability unestimated.
- Build snapshots only from results earlier than the as-of date; add future-data perturbation tests.

## Phase 3 — Horse-only BASE v1

- Predict finish-time distributions from race conditions and the horse snapshots; simulate within-race outcomes with a fixed seed.
- Return raw/calibrated win probability, rank, uncertainty, coverage, model version, and training cutoff.
- Validate probability sums, reproducibility, and a race-level time split before any broad backtest.

## Phase 4 — Pedigree prior (deferred)

- Verify ancestor slot semantics and as-of availability; implement only behind a disabled-by-default option.
- Require leave-one-horse-out or equivalent time-safe aggregation and a sparse-history ablation.

## Phase 5 — Comparison and adoption (deferred)

- Align exact evaluation race IDs and windows with the existing Ranker and RACEVERSE outputs.
- Report proper scoring, calibration, clock error, ROI, sample sizes, and time-block uncertainty.
- Production replacement requires a separate explicit decision; ROI alone is insufficient.

## Current blocker for historical replay

The database has a race date and `headMakeDate` in `YYYYMMDD` form, not a verified timestamp or complete revision history for historical entry lists and going. Use a previous-day cutoff for horse histories and flag any evaluation based on final historical starters as not a fully reconstructed pre-post-time backtest.

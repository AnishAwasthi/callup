# Verified methodology and agreed provisional design

Anish approved this provisional Week 1 design on October 6, 2026. Initial focus: hitters with at least 150 AAA PA in feature season Y (2023 or 2024), predicting on January 1 of Y+1. Features use only regular-season AAA events dated within Y. Outcome: the following regular-season MLB batting wOBA, with at least 75 MLB PA. This is an offseason translation problem, not a within-season first-promotion prediction.

## Existing behavior

`build_cohort` explicitly joins Y AAA to Y+1 MLB via numeric MLBAM ID. `PlayerSeason.outcome_year` is Y+1. Its three legacy partitions are MLB PA/IP eligibility (`labeled`), an MLB stats row below the floor (`promoted_thin`), and no next-season stats row (`never_promoted`). The last name describes that window only: it does not mean never in a career. API row presence is not a documented first-ever promotion date. Hitters may already have MLB experience.

The cached moderate report reproduces 1,385 / 353 for hitters and 1,144 / 285 for pitchers; their sum is 2,529 / 638. These are player-season-group rows, not 2,529 unique people and not 638 hitters. The Stats API season lines do not supply wOBA. The 353 legacy `labeled` hitters only meet a workload threshold.

By feature year, the legacy hitter counts (pool / eligible / thin / no row) are 2023: 470 / 114 / 101 / 255; 2024: 456 / 125 / 106 / 225; 2025: 459 / 114 / 101 / 244. The last group uses 2026 season stats cached September 3, 2026 and is incomplete. Exclude it from initial outcome modeling even though today is after the regular season. The raw pitch archive contains 2023–2025 only. Do not silently mix refreshed outcomes with the frozen preparation snapshot.

`_index_by_player` sums workload across splits and retains the largest split's other stats. This is approximate for rates and can leave smaller-split counts out. The preparation table instead sums selected additive AAA counts. Investigate duplicate/total splits if future API responses change; do not sum both team splits and a total row. Use archive events for pitch-derived features, and independently reconcile to season totals.

The ingester uses urllib, cached MLB Stats API JSON, and daily Savant CSV export requests. It does not use pybaseball. It decompresses and parses the CSV bytes, checks a 25,000-row cap, and wraps the original response bytes in gzip. Existing raw files are unchanged by preparation. Old `validate_archive.py` checks schedules plus one season sampled every 15 days; its PASS must not be described as every-record validation.

## Flags and outcome

`reached_mlb` means observed next-season MLB **batting PA > 0**, including players with earlier MLB experience. `outcome_eligible` means MLB PA ≥75. `label_available` additionally requires positive observed Savant wOBA denominator and no missing value on positive-denominator terminal events. Never encode an unavailable outcome as 0. Label availability is not the same as promotion; selection into sufficient playing time is a second process.

The initial 926-row pool has 443 positive-PA participants, 239 eligible/provisional labels, 204 thin participants and 483 with no observed batting PA. The legacy cache report instead has 207 thin / 480 without a stats row: three zero-PA MLB stats rows move from legacy thin to our `not_observed`. This is a documented definition change, not a failure to reproduce the old counts. After the player-disjoint split: training 208 rows / 62 labels; test 456 / 125; excluded overlap 262 / 52. There are 464 AAA archive-vs-official PA discrepancies and 104 MLB discrepancies among participants. No outcome reconciliation has been claimed from those counts alone.

The prepared `mlb_woba` is provisional: sum served `woba_value` over terminal events divided by sum served `woba_denom`. It is observed wOBA, not xwOBA. Source weights and no-pitch events may cause discrepancies with official season statistics; an independent reconciliation remains for methodology review. The table retains numerator, denominator, official PA, observed terminal-event count and dates for that review. All labels carry `label_provisional=True`. Eligibility counts must be reported separately from available verified outcomes.

## Leakage-safe evaluation

All 2024 feature-season rows form `test` (2025 outcomes). 2023 rows whose player appears anywhere in the 2024 pool become `excluded_overlap`; all remaining 2023 rows form `train` (2024 outcomes). Split the full cohort before filtering to available labels. This is stricter than removing overlap only among labeled players. Train and test player IDs must have empty intersection. This evaluates a changed player population; report how many rows and labels are removed. Do not move excluded rows back into training to increase sample size.

Person 4 should use player-grouped cross-validation inside training, fit scaling/imputation only inside the pipeline on training folds, and report MAE/RMSE/R² on available test labels with sample sizes. Keep the 2024 test set untouched by tuning. Define an explicit feature allowlist: only pre-prediction AAA quantities, never MLB PA, outcome flags, label availability, MLB dates, outcome values, split indicators, or player ID as a predictor. Future-looking raw fields such as `*_days_until_next_game` are excluded; later source snapshots also contain retrospectively computed fields. Full-season Y AAA data precedes Y+1 outcomes, but a frozen prospective deployment would still require as-of metadata snapshots.

Promotion descriptive analysis uses **all** pool rows and treats next-season batting participation separately from eligible outcome selection. Call it observed MLB participation rather than causal promotion. Absence in this window is not proof of permanent failure. No selection correction guarantees unbiased outcomes: unobserved scouting/health/context and identification assumptions remain. No exclusion restriction or final correction method has been agreed; Anish owns this after the meeting.

## Decisions still open for later scientific work

The 150/75 floors and target are approved provisionally; run documented sensitivity comparisons before final results. Independently reconcile outcome wOBA, determine whether to restrict to MLB-naive hitters, and decide how to handle measurement/PA gaps. A future first-call-up study needs a cutoff before call-up, complete history and a different cohort; do not reuse full-season AAA features for that question. Park research must use only information available before the prediction date when included in evaluation.

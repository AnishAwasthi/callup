# Person 1: Build and validate basic hitting features

Owner: Person 1 (handle pending). Start with `docs/methodology.md`, `docs/data-contract.md`, the README offline exercise and the agreed 2023–2024 cohort. The real inputs are `data/parquet/AAA/*.parquet`, frozen team metadata and `data/processed/hitter_seasons.csv`. Download the shared Google Drive package using the README. `data/local_sample/` contains a small real-data sample; `data/sample/` contains invented data for checking setup only.

Produce a script callable from the repository root, methodology notes and ignored `data/processed/features_basic.csv` or `.parquet`. Schema: unique integer `player_id, season`; `pa` integer; `k_pct, bb_pct, swing_rate, contact_rate` nullable numeric fractions; `n_pitches, n_swings, n_contacts` integers; `pa_gap` integer (archive PA minus cached AAA PA). Include count/coverage fields for every denominator.

Derive true AAA using both opponents' candidates; resolve `COL` using the opponent rather than a single code map. Restrict dates to feature year, before Jan 1 of Y+1. Keep all eligible cohort players, even with unavailable outcomes. Count terminal PA events once, not pitches. Document K/BB event tokens and intentional-walk treatment, swing/contact description tokens and treatment of bunts/foul tips/pitchouts. Missing denominator produces null, not zero. Compare with cached source counts; explain gaps without forcing equality.

Dependencies: shared contract and permitted data access only; independent of Persons 2–5. Coordinates with Person 4 on column names and with Anish on event definitions. Do not implement batted-ball features, outcomes, selection correction or models.

Acceptance:

- Reproducible CLI on real small sample and full permitted inputs; no network required after download.
- Exact key uniqueness and one-to-one join to shared cohort; no loss of unpromoted rows; no future MLB fields used.
- Validate 3–5 real players, including multiple outcomes and a Columbus player; show raw PA/pitch counts, numerator/denominator arithmetic and discrepancies.
- Rates within [0,1], contact count ≤swing count, explicit missingness and coverage report.
- Focused tests for real failure risks (duplicate PA counting, zero denominators, token classification), passing CI and reviewable PR linked to this Issue. Commit code/docs/tests, not full data.

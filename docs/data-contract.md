# Hitter-season contract v0.1

Primary key: `(player_id, season)`, unique and nonmissing. `player_id` is MLBAM/Stats API `player.id`, matching Savant `batter`, carried as integer; names are display metadata and never join keys. Player-year tables from Persons 1/2 join one-to-one on this key. CSV uses empty cell for missing; Parquet uses null. Never use -1 or zero as a missing label. Numeric rates are fractions, not formatted percentages. Counts are nonnegative integers.

| Fields | Type / meaning | Allowed as predictors? |
|---|---|---|
| player_id, name | integer key; text display name | No |
| season, outcome_year | integers Y, Y+1; Y is 2023/2024 | Season only if explicitly approved |
| prediction_date | ISO date January 1 of Y+1 | No |
| aaa_pa | official cached AAA PA, ≥150 | Yes |
| aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr | summed additive cached hitter counts; walks include intentional walks | Yes, preliminary |
| aaa_observed_pitches, aaa_observed_pa | archive pitch rows and terminal-event count after true AAA filter | Coverage diagnostics; review before predictor use |
| aaa_first_date, aaa_last_date | observed AAA date bounds within Y | Metadata |
| mlb_pa | official next-year PA (0 means not observed) | No |
| reached_mlb | boolean next-year MLB batting PA >0 | Promotion-analysis target only |
| outcome_eligible | boolean MLB PA ≥75 | No |
| label_available | boolean eligible with reconstructible observed wOBA | No |
| mlb_woba | nullable float, provisional served-values ratio | Outcome only |
| mlb_woba_numerator, mlb_woba_denom | observed sums used in outcome reconstruction | No |
| mlb_observed_pa, mlb_first_date, mlb_last_date | outcome coverage/count and date diagnostics in Y+1 | No |
| outcome_status | eligible / thin / not_observed; eligibility is separate from availability | No |
| split | train / test / excluded_overlap; frozen rule in methodology | No |
| label_provisional | boolean; all starter outcomes are provisional | No |
| data_kind | real / synthetic; never combine them in analysis | No |

`callup.contract.load(path)` validates essential safeguards. CSV dates are strings; parse explicitly. Parquet starter counts/booleans/numeric outcomes are typed. Raw-derived pitch Parquet intentionally keeps non-ID tokens as text, preserving exact decimal spellings; cast explicitly with errors raised before numeric analysis.

## Pitch-level inputs and joining

Pitch key: `(game_pk, at_bat_number, pitch_number)` within source/date and level; the audit checks nonmissingness and duplicates per shard. Date belongs to each game; duplicated keys across source shards must be checked before pooling levels. AAA source files contain both AAA and Single-A: derive both home and away levels using the same season's Stats API team map and require both to equal AAA. Never interpret every row under `data/raw/AAA` as AAA. Keep the original requested feed separate from derived true level.

`player_name` in the raw pitch export follows the pitcher search perspective and must not be assumed to be the batter name. Use player ID to attach the correct name. Do not use date filenames alone for predictions; check event date and prediction cutoff.

## Teammate outputs

Write generated full CSV/Parquet tables in ignored `data/processed/`. Commit scripts, docs and tests; use a small synthetic fixture for CI until real-source sharing is cleared. Every feature table has unique integer `player_id, season`, named numeric outputs, denominator/sample-count columns and documented null behavior. Do not drop unpromoted players when constructing features. Set a rate to null if its denominator is zero; distinguish no measurement from an observed zero.

Persons 1 and 2 should produce all cohort rows where possible, annotate missing coverage, and leave the central outcome/split fields to the shared table. Person 3's prototype table key is `(park_id, season)` or `(home_team, season)` until venue mapping is resolved, with factor scale, reference=1.0 or 100 explicitly documented. Do not silently duplicate player-season rows when joining parks.

The preliminary starter provides counts sufficient to build modeling/promotional scaffolding. Person 4 can use the explicit AAA count allowlist while Persons 1/2 complete their feature tables. Do not claim this is the final feature matrix. Per-person output schemas and acceptance criteria live in `docs/issues/`.

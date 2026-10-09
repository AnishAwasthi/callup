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

The preliminary starter provides counts sufficient to build modeling/promotional scaffolding. Person 4 can use the explicit AAA count allowlist while Persons 1/2 complete their feature tables. Do not claim this is the final feature matrix. Output column definitions are below; task briefs and completion checks live in `docs/issues/`.

## Week 1 output columns

These are the implementation details for the five issues. Keep generated tables in ignored `data/processed/`. Use fractions from 0 to 1 for rates, blank/null for missing measurements, and unique keys. Never fill an unavailable outcome with zero. Each script should run from the project folder and record how to reproduce its output.

### Basic hitting output

File: `features_basic.csv` or `.parquet`. One row for every study player-season, keyed by integer `player_id, season`.

| Columns | Type and meaning |
|---|---|
| `pa` | Integer count of observed completed plate appearances |
| `k_pct, bb_pct, swing_rate, contact_rate` | Nullable numeric fractions; record the event classifications and intentional-walk treatment |
| `n_pitches, n_swings, n_contacts` | Integer counts supporting the rates; retain strikeout/walk numerator counts too |
| `pa_gap` | Integer observed PA minus saved API AAA PA |

Count terminal events once. Define bunts, foul tips, pitchouts and other swing/contact cases explicitly. A zero denominator gives a missing rate. Investigate source-total differences rather than changing counts to force agreement. Keep unavailable-outcome players and use no future MLB fields.

### Batted-ball output

File: `features_batted.csv` or `.parquet`. One row for every study player-season, keyed by integer `player_id, season`.

| Columns | Type and meaning |
|---|---|
| `ev_mean, ev_p90, ev_max` | Nullable floats, exit velocity in mph |
| `hard_hit_rate` | Nullable fraction: balls with EV ≥95 mph divided by balls with valid EV |
| `la_mean, la_median, la_std` | Nullable floats, launch angle in degrees |
| `n_bbe, n_ev, n_la, n_hard_hit` | Integer batted-ball, valid-EV, valid-angle and hard-hit counts |
| `ev_coverage, la_coverage` | Nullable fractions: valid measurement counts divided by `n_bbe` |

Document the batted-ball definition, percentile interpolation and standard-deviation convention. Convert pitch measurements from text to numeric with conversion errors raised. Deduplicate event keys and explain foul/nonterminal measurements; some upstream measurements may be estimates. Retain all study rows, including rows without measurements, and report missingness by season.

### Park prototype output

File: `park_prototype.csv`. Use unique `(home_team, season)` keys until a venue mapping is validated.

| Columns | Type and meaning |
|---|---|
| `season, home_team` | Integer year and team code |
| `park_id` | Optional nullable integer, only with a documented venue mapping |
| `factor, reference_scale` | Nullable numeric factor and text neutral scale (`1.0` or `100`) |
| `n_home_pa, n_away_pa` | Integer counts used in the home/away comparison |
| `method, provisional` | Method name and boolean indicating a preliminary result |

State denominators, minimum sample size, reference normalization and venue uncertainty. Keep all evaluation inputs before the prediction date; for example, do not use 2025 outcomes to adjust 2024 features. Coordinate keys and units before joining this prototype to hitter tables.

### Model output

Files: `model_metrics.json` and `predictions.csv`. Use a scikit-learn Pipeline for training-only imputation and scaling. Initial predictor columns are `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr`; an explicit allowed-column list must reject outcome fields, IDs and split/provenance metadata. Record any added dependencies and random seeds.

Prediction columns: integer `player_id, season, outcome_year`; text `split, model`; numeric `y_true, y_pred`; data/code version identifiers. Rows with unavailable outcomes do not belong in evaluation; do not impute outcomes.

Metrics must record model, predictor list, training/test row and unique-player counts, MAE, RMSE, R², missing/dropped-row counts, data/code versions and random seed/settings. Report R² as undefined for insufficient or constant targets. Preserve excluded-overlap counts in diagnostics. Split before selecting rows with available labels; tune only within training using player-separated groups. Distinguish a small-sample setup check from full-table evaluation. Selection correction, outcome changes and split changes require agreement with Anish.

### Participation summary output

Directory: `promotion/`. Use all study rows, including those with unavailable outcomes.

| Columns | Type and meaning |
|---|---|
| `season, outcome_status` | Integer year and study outcome category |
| `n_rows, n_players, n_reached, n_eligible, n_label_available` | Integer counts; state whether each count represents player-seasons or distinct people |
| `participation_rate, eligibility_rate, label_rate` | Numeric fractions with stated denominators |

Missing-value summary columns: `season, field, n_missing, n_total, missing_rate`. Report groups separately for `reached_mlb` (PA >0), `outcome_eligible` (PA ≥75) and `label_available` (usable provisional wOBA). Compare counts with `reports/cohort_preparation.json`. If attempting the optional participation model, use only pre-outcome AAA information, training-only preprocessing, the frozen player-disjoint split and metrics that account for unequal group sizes.

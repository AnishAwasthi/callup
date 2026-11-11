# Controlled Ridge batted-ball ablation — provisional target, v1

Adding Azra's seven batted-ball measurements did **not demonstrate improved
prediction beyond the original six AAA counts** in this controlled experiment.
Both configurations use the same 62 labeled training players, player-grouped
validation splits, original provisional outcomes and 125 frozen test players.
The primary training-only nested cross-validation MAE is .026970 without the
measurements and .027013 with them; RMSE is .034622 versus .034774. The small
differences favor the simpler model but do not establish that batted-ball data
has no predictive information. The sample is small and predictions from both
models remain close to the training mean.

This addresses Anish's second Issue #4 request, using PR #15's merged
`scripts/build_batted_features.py`. It does not duplicate Azra's Elastic Net or
boosted-tree work under Issue #16. The standard-wOBA target recommendation in
[the committed audit](woba-full-cohort-reconciliation.md) is separate: its target
replacement and Sweeney attribution correction have **not** been implemented.

## Reviewed implementation and integration

The existing `callup/modeling.py`, `scripts/train_models.py`, tests,
[model specification](modeling-ridge.md), [data contract](data-contract.md),
[methodology](methodology.md) and Azra's script were reviewed before execution.
Work began at audit commit `edb6fdf670d0e3f1a88f186a3160417199528419` on
`issue-4-ridge-model` with a clean working tree. Existing code and documentation
are unchanged; this experiment adds a separate module, runner, tests and report.

The runner calls Azra's existing loading, filtering, aggregation and study-join
functions directly, preserving her definitions:

- A batted ball has `description == "hit_into_play"`; fouls with launch data
  are excluded.
- Exit velocity is in mph; hard hits have EV ≥95 mph. Hard-hit rate is divided
  by measured EV count, not all balls in play.
- EV p90 uses linear interpolation; launch-angle SD is sample SD (`ddof=1`).
- Missing measurements remain missing; zero counts mean observed pitches but
  no batted balls. Absent pitch data would produce missing counts.

Before Azra's loader runs, a preflight check rejects missing or duplicate pitch
keys across both seasons, invalid raw measurement ranges, incorrect cohort flags, mismatched feature-season dates, or teams outside
the **same season's** AAA team map. This avoids relying on her loader's warning
and first-copy deduplication behavior. Source validation also identified three repeated in-play PA anomalies, documented
below; no rows were removed or corrected. The shared extracts have no game-type field; regular-season
scope relies on the existing archive preparation/audit. Dates within feature year
Y precede the January 1 Y+1 prediction date.

All **926 study player-seasons** receive exactly one feature row. The join on
integer `(player_id, season)` requires exact key-set equality and one-to-one
cardinality; missing, additional or duplicate keys fail. Every original study
column is compared before/after, including labels, flags, outcomes and split.
No outcome-dependent complete-case filtering or eligibility changes occur.
Feature validation checks nonnegative integer counts, denominator relationships,
rate calculations, missingness against measurement counts, finite values and
plausible ranges. Four fixed key-selected player-seasons (two per year) are
recalculated from their balls in play as spot checks; these keys were not chosen
using outcomes or model results. Synthetic tests cover missing measurements,
fouls, no batted balls and absent pitch data.

### Source anomaly retained for review

Three study-player plate appearances have two distinct pitches described as
`hit_into_play`: game 722787 / PA 7 (2023-05-05, batter 642215), game 725152 /
PA 23 (2023-06-15, batter 669200), and game 752069 / PA 48 (2024-07-10,
batter 670237). In each case the earlier pitch has no terminal event and no EV
or LA measurement; the later pitch has a terminal event. There are no duplicate
pitch keys. The upstream causes have not been independently established.

Azra's description-based definition retains all six rows, so the three
unmeasured extra rows enter `n_bbe` and the coverage denominator. The runner
records these pairs in `batted_source_anomalies.csv` and verifies that excluding
the three unmeasured nonterminal rows in a diagnostic calculation leaves **all
seven model predictors exactly unchanged**. The actual feature table retains
Azra's definitions, counts and coverage. Thus this source issue does not change
the Ridge comparison, but it should be reviewed before treating `n_bbe` as an
exact count of distinct completed batted-ball PAs. Any future correction should
be versioned with Azra; none was made here. The runner fails if repeated
nonterminal rows contain measurements rather than silently choosing one.

## Available features and coverage

Azra's table has 13 non-key columns. The added predictor block was fixed before
looking at experiment results:

| Role | Columns |
|---|---|
| Seven added batting measurements | `ev_mean`, `ev_p90`, `ev_max`, `hard_hit_rate`, `la_mean`, `la_median`, `la_std` |
| Four diagnostic counts | `n_bbe`, `n_ev`, `n_la`, `n_hard_hit` |
| Two diagnostic coverage fractions | `ev_coverage`, `la_coverage` |

Counts and coverage support measurement validation and remain outside this
predictor block. They are not dropped because of test performance. The original
six predictors remain `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr`.
Thus the models have **6 versus 13 predictors**, not six versus nineteen.
We did not search subsets, add interactions or tune the feature block after
seeing results. Correlated summaries such as EV mean/p90/max and LA mean/median
are deliberately included together in the requested block comparison; their
coefficients should not be interpreted causally.

| Feature season / subset | Rows | Batted balls | Measured EV | EV coverage | Measured LA | LA coverage |
|---|---:|---:|---:|---:|---:|---:|
| 2023, all | 470 | 98,390 | 98,007 | 99.611% | 98,077 | 99.682% |
| 2024, all | 456 | 98,311 | 97,644 | 99.322% | 97,691 | 99.369% |
| All study rows | 926 | 196,701 | 195,651 | 99.466% | 195,768 | 99.526% |
| Labeled training | 62 | 13,086 | 13,038 | 99.633% | 13,043 | 99.671% |
| Labeled test | 125 | 26,408 | 26,213 | 99.262% | 26,231 | 99.330% |

These percentages pool event counts; they are not averages of player percentages.
All 926 rows have **zero missing values in every season-level feature column**,
including the seven model predictors. Individual-event missingness therefore
does not require player removal or zero-filling. Minimum measured EV and LA
counts per row are both 79. Measurement presence does not independently verify
sensor accuracy, estimated measurements or park-to-park comparability.

## Controlled selection and evaluation

The frozen parent cohort contains training 208 rows / **62 labels**, test 456 /
**125 labels**, and excluded overlap 262 / **52 labels**. Excluded rows and
unavailable labels participate in feature/coverage reporting, never fitting or
validation. All 62 labeled training rows represent distinct players.

Both Ridge configurations use the same original `mlb_woba` column and identical
deterministic `GroupKFold(shuffle=False)` splits grouped by MLBAM `player_id`.
The alpha grid is the existing **[0.1, 1, 10, 100, 1000]**. Each configuration
selects alpha independently by minimum mean fold MAE; exact ties choose the first
ascending alpha. RMSE is recorded but does not select alpha. There is no clipping,
target rescaling, sample weighting, feature selection or test-informed tuning.

Each fit uses median imputation, StandardScaler and Ridge with an unpenalized
intercept and SVD solver. Medians and scaling are learned within that fit's
training data. Entirely unmeasured fit columns would be dropped by the imputer,
not replaced with zeros. This differs from the legacy pipeline's empty-column
zero fallback; no columns are missing here, so it has no effect on benchmark
reproduction. The old pipeline is unchanged. Missing-measurement behavior and
training-only preprocessing are tested with synthetic cases.

There are two explicitly distinguished CV summaries:

1. **Final alpha-selection CV:** the original five-fold grouped search on all
   62 training labels. These scores reproduce the old benchmark for six counts,
   but are optimistic as estimates of the selected model's performance because
   alpha is selected on the same folds.
2. **Primary nested CV:** five shared outer validation folds, each with 12–13
   players; fitting subsets have 49–50 players. Within each outer fit subset,
   both configurations use identical five-fold inner splits to select alpha
   independently. Outer predictions are produced only after inner selection.
   Pooled out-of-fold metrics evaluate all 62 training players exactly once per
   configuration. The fold-assignment file records all outer and inner roles.

Both configurations select **alpha 100** when tuned on all 62 labels. In nested
CV, both independently select **alpha 1000 in each of the five outer fits**.
That difference between the smaller fit samples and the full training sample
illustrates tuning sensitivity with limited data.

| Alpha | Six-count selection CV MAE | Added-batted selection CV MAE |
|---:|---:|---:|
| 0.1 | .027687 | .030965 |
| 1 | .027347 | .030099 |
| 10 | .026839 | .027921 |
| 100 | .026816 | .026974 |
| 1000 | .027102 | .027144 |

## Results and uncertainty

Positive differences below mean **adding batted-ball predictors increased error**.

| Evaluation | Six-count MAE | Added-batted MAE | MAE change | Six-count RMSE | Added-batted RMSE | RMSE change |
|---|---:|---:|---:|---:|---:|---:|
| Final selection CV, mean folds | .026816 | .026974 | +.000159 | .033816 | .034501 | +.000685 |
| **Nested training OOF, pooled** | **.026970** | **.027013** | **+.000043** | **.034622** | **.034774** | **+.000152** |
| Exploratory frozen holdout | .035010 | .035310 | +.000300 | .046734 | .047064 | +.000330 |

The nested pooled MAE difference is about +0.16%; it is not a useful improvement.
Pooled RMSE is calculated over all OOF errors, not an average of fold RMSEs.
Mean paired outer-fold differences are +.000041 MAE and +.000139 RMSE; they
slightly differ from pooled differences because folds have unequal size and
RMSE is nonlinear.

| Outer fold (one-based) | Validation players | Six alpha | Added alpha | MAE change | RMSE change |
|---:|---:|---:|---:|---:|---:|
| 1 | 13 | 1000 | 1000 | −.000002 | +.000007 |
| 2 | 13 | 1000 | 1000 | +.000188 | +.000252 |
| 3 | 12 | 1000 | 1000 | −.000126 | +.000059 |
| 4 | 12 | 1000 | 1000 | +.000103 | +.000395 |
| 5 | 12 | 1000 | 1000 | +.000045 | −.000017 |

Added features improve MAE in **2/5 folds** and RMSE in **1/5**. The sample SD
of paired fold changes is .000118 MAE and .000178 RMSE. Folds share fitting
observations, so these are descriptive measures, not five independent trials.

A paired player bootstrap (4,000 samples, seed 4) of the **fixed nested OOF
predictions** gives conditional 95% percentile intervals:

- MAE change: **[−.000129, +.000227]**.
- RMSE change: **[−.000074, +.000378]**.

Both include zero. This bootstrap resamples players with both predictions kept
paired. It does not refit models, vary fold assignments or capture every source
of uncertainty. It is not a definitive significance test; neither a tiny point
difference nor these intervals establish equivalence. We have only 62 training
players, one training outcome year, thirteen correlated predictors in the larger
model and heavy regularization. Larger or prospectively held-out samples could
produce a different conclusion.

### Prediction spread

Observed training wOBA has population SD **.034590**. Nested OOF predictions
have SD **.001165** for six counts and **.001281** with batted-ball predictors;
ranges are .307304–.312056 and .306732–.312573. Both behave approximately like
predictions of the overall mean and have slightly negative nested R²
(−.0018 and −.0106). Added measurements barely widen that spread.

On the exploratory holdout, prediction SD increases from .003223 to .004971;
ranges widen from .303241–.318560 to .298179–.325828. This larger spread is
accompanied by slightly worse errors, not demonstrated improved discrimination.
See the generated `training_comparison.png` / `.svg` for paired fold errors and
nested OOF observed-versus-predicted plots.

### Exploratory holdout and benchmark reproduction

The held-out feature season is 2024 (2025 provisional MLB outcomes). Its 125
labeled observations and targets are identical between configurations. Predictions
are generated only after all training selection and final refits finish.
**The holdout is exploratory because the original test results have already
been inspected.** Its errors did not determine the feature block, alpha grid,
selection score, or recommendation based on training-only validation.

The six-count final alpha, CV MAE, test keys, targets, predictions, MAE and RMSE
reproduce both the existing fitting algorithm and the saved benchmark within
absolute 1e-12. The saved `data/processed/model_metrics.json` and `predictions.csv`
were read only. An explicit predictor allowlist leaves IDs, season, split,
coverage diagnostics and all outcome fields out of the model inputs.

## Reproduction, outputs and safeguards

With the existing locked dependencies installed, run from the repository root:

```bash
python scripts/ridge_batted_ablation.py
pytest
ruff check .
```

No network, additional dependencies or new source download is required. Default
output is **ignored `data/processed/ridge_batted_ablation_v1/`**, separate from
Azra's default `features_batted.csv` and all previous model/audit outputs:

| Artifact | Contents |
|---|---|
| `features_batted.csv` | Azra's full 926-row features |
| `study_with_batted.csv` | Validated one-to-one join preserving all study columns |
| `feature_missingness.csv`, `measurement_coverage.csv` | Per-column missingness and pooled event coverage, including labeled splits |
| `feature_spot_checks.csv` | Four fixed-key aggregation checks |
| `batted_source_anomalies.csv` | Six rows from three repeated in-play PAs; retained unchanged |
| `fold_assignments.csv` | Training players, outer/inner folds and fit/validation roles; shared by both models |
| `alpha_grid_scores.csv` | Every alpha's fold MAE/RMSE for final tuning and each inner search |
| `outer_fold_metrics.csv`, `paired_fold_differences.csv` | Nested fold scores, selected alphas and paired changes |
| `predictions.csv` | Nested OOF and exploratory holdout predictions, identical keys/targets for both configurations, input/code version metadata |
| `metrics.json` | Configuration, sample sizes, CV/holdout metrics, prediction spread, fitted medians/coefficients, conditional uncertainty and benchmark verification |
| `training_comparison.png`, `.svg` | Training-only comparison figure |
| `preserved_inputs.json` | Before/after hashes for protected existing files |

Provenance includes shared study/team/pitch hashes, feature generator and model
code hashes, Git revision/dirty state, library versions and bootstrap seed. Reruns
reproduce scientific results; Git provenance and plotting metadata may reflect
the current checkout/session. The runner checks protected tracked inputs and all
pre-existing processed files outside its output directory for unchanged hashes.
The first run verified **135 pre-existing files unchanged**, including the
committed wOBA audit, frozen dataset, labels/splits and earlier model outputs.
No existing file was edited, no new target/correction applied, no commit or push
made, and PR #13 was not modified.

Tests cover aggregation definitions, invalid/missing/duplicate feature keys and
values, repeated in-play source anomalies and measurement-summary invariance, exact row/label/split preservation, synthetic missingness without zero
substitution, fold-local preprocessing, repeated-player grouping, identical paired
prediction keys, exclusion of holdout/unlabeled/excluded rows from tuning,
holdout-label perturbation invariance, full-cohort generation and benchmark
reproduction. Only the new ablation's generated outputs are written.

Final validation: **153 pytest tests passed** and **Ruff passed**. A separate
end-of-task hash check confirmed all 135 original files remained unchanged;
all 16 generated files (including the plotting cache) are ignored. Git contains
only the four new ablation source/test/documentation files, with nothing staged.

## Recommendation

Keep the six-count Ridge as the simpler benchmark for now. Retain Azra's validated
feature table for future work, but do not claim the seven-stat block improves
prediction in this cohort. The controlled comparison shows no consistent gain
under training-only nested validation, and the exploratory holdout does not
supply supporting evidence either.

This finding is limited to this feature block, linear Ridge, alpha grid, small
player-separated training sample and **original provisional target**. It does not
rule out usefulness with more training seasons, approved standard-wOBA outcomes,
other validated measurements or Azra's separate models. Any later experiment
should be versioned and specified before evaluating a fresh holdout. Target
replacement still requires Anish's approval.

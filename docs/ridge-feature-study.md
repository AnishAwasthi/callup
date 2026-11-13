# Exploratory Ridge feature, sample-size and validation-stability study

**No new configuration consistently improves on the fold-fitted training-average
baseline.** Rates do not establish an advantage; individual batted-ball effects
change with validation assignment; small fitting samples are unstable. Increasing
fitting size from 10 toward 30–50 players greatly reduces error and variability
in these learning curves, but accuracy then sits near the mean baseline. These
results support obtaining more independent training seasons and improving target
measurement, rather than promoting another configuration from this cohort.

This is training-only exploration on the original provisional wOBA target. No
new holdout metric is calculated. The original six counts remain a historical
Ridge benchmark, not a model established as superior to the mean baseline.

## Inspection, scope and preservation

The working tree began at committed ablation `05a82ee` with four untracked
regularization-sensitivity files. Existing modeling modules, runners, diagnostics,
prior experiment reports/tests and the dataset contract/methodology were inspected.
Those four untracked files, all prior reports/results, the committed wOBA audit,
original labels and frozen split are preserved. This study adds only:

- `callup/ridge_feature_study.py`
- `scripts/ridge_feature_study.py`
- `tests/test_ridge_feature_study.py`
- This report.

The runner reuses Azra's existing feature functions through the validated batted
feature builder and exact one-to-one study join. All **926** keys retain every
original study column. The three known repeated in-play descriptions remain
unchanged and do not affect the seven measurements used here. Rates are derived
from feature-season AAA counts only. No future MLB field is allowed as a predictor.

Only **62 available training labels / 62 distinct players** are used. These have
2023 AAA features and 2024 provisional MLB outcomes. The full parent cohort still
contains training 208 rows, test 456 rows (125 labels), and excluded overlap 262
rows (52 labels). Excluded players, unavailable labels and the frozen future-season
test rows never fit, tune or validate the new models. Feature construction for all
926 rows is deterministic and does not learn anything from outcomes.

## Fixed design and evaluation rules

Choices below were specified before viewing these new results. The optional
compact rate subset search was omitted to limit selection on 62 players.

### A — Rates versus counts

| Name | Predictor count | Predictors |
|---|---:|---|
| `counts` | 6 | `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr` |
| `rates` | 5 | `aaa_pa`, `aaa_bb_rate=BB/PA`, `aaa_k_rate=K/PA`, `aaa_hr_rate=HR/PA`, `aaa_ba=H/AB` |
| `rates_batted` | 12 | Five rates/playing-time predictors plus the seven batted-ball measurements |

The seven measurements remain `ev_mean, ev_p90, ev_max, hard_hit_rate, la_mean,
la_median, la_std`. Count-derived walks retain the original source's convention,
including intentional walks. Division is explicit: a zero denominator produces
missing, never infinity or a fabricated zero. There are **no zero-denominator
or missing rate values in the actual 926 rows**. Synthetic tests exercise zero
PA/AB. Rates are not smoothed; PA remains an explicit playing-time measure.

### C — Controlled contributions, not exhaustive subset selection

Starting from the six counts, add each of the seven batted measurements separately,
then the EV group (EV mean/p90/max and hard-hit rate), the LA group (mean/median/SD),
and the entire seven-feature group. The entire counts+batted configuration has
13 predictors. Together with A this makes **13 fixed Ridge configurations**, plus
the mean baseline. We also compare full batted versus EV-only and LA-only groups,
and rates+batted versus rates. There is no exhaustive subset search, coefficient-
based pruning, or compact model chosen after inspecting validation outcomes.

These are conditional predictive contributions **with alpha retuned for each
configuration**. They are not causal feature importance or a test of isolated
coefficients. Correlated measurements can substitute for one another; retuning
also changes the overall amount of shrinkage.

### D — Repeated grouped splits

Evaluate every configuration on the original unshuffled five-fold GroupKFold
(labelled seed −1) and six additional shuffled GroupKFold assignments with seeds
**0, 1, 2, 3, 4, 5**. Each repetition evaluates the same 62 players exactly once
per configuration. Outer validation fold sizes are **13, 13, 12, 12, 12**; outer
fitting sizes are 49–50. Shared assignments include the inner folds, generated
with deterministic seed `10000 + 100*outer_seed + outer_fold` for shuffled runs;
the original split retains unshuffled inner folds. Every configuration within
an outer case sees exactly the same fit/validation players and target values.

Each configuration independently selects alpha from the **original grid
[.1, 1, 10, 100, 1000]**, using mean inner five-fold validation MAE. Ties choose
the first ascending alpha. We retain this grid for comparability and do not repeat
the wider-grid search. RMSE is reported but does not select alpha.

All fits use the existing Ridge/median-imputation/StandardScaler machinery with
SVD solver and an unpenalized intercept. Missing predictors are imputed with
fit-only medians; an entirely empty fit column is dropped, not zero-filled.
There is no target imputation. The new tuner caches alpha-independent preprocessing
within each inner fitting fold, then fits the same Ridge estimator for each alpha.
Equivalence with the original GridSearchCV implementation and saved predictions
is tested. This changes computational cost, not the statistical design.

The mean baseline is fitted separately on the **same fitting players**, including
learning subsets, and never uses a validation outcome to estimate its mean.
Reported repetition metrics pool all 62 OOF errors. Reported training errors
average the five fitting errors, not errors from a final fit to all 62.

### B — Learning curves with paired player subsets

Use the original five outer splits, keeping each validation fold fixed. Within
each outer fitting pool, draw **five deterministic random player permutations**
and use nested prefixes at 10, 20, 30 and 40 fitting players. All three A models
and the baseline use identical subsets. Seed is `20000 + 100*outer_fold + draw`.
The all-available point reuses the original-split fits at 49–50 players, once;
we do not pretend repeated identical full samples are independent draws.

| Fitting players | Outer validation players | Inner validation players | Inner fitting players | Subset draws per outer fold |
|---|---|---|---|---:|
| 10 | 12–13 | 2 | 8 | 5 |
| 20 | 12–13 | 4 | 16 | 5 |
| 30 | 12–13 | 6 | 24 | 5 |
| 40 | 12–13 | 8 | 32 | 5 |
| All: 49–50 | 12–13 | 9–10 | 39–40 | 1 |

Alpha is retuned **inside each subset**, without seeing the fixed outer validation
players. There are 100 smaller-subset outer cases plus five reused all-available
cases. Each size/draw pools validation predictions for the same 62 players across
five folds. Its variation across five draws measures sensitivity to which fitting
players were sampled, conditional on these outer folds. It is not uncertainty
about a genuinely new season. No point fits 62 players and validates on those same
players; the largest generalization-curve fitting size is 49–50.

## A results — Feature engineering

The original unshuffled nested comparison reproduces the old count and
counts+batted OOF predictions within absolute **1e-12**.

| Configuration | Original-split MAE | Original-split RMSE | MAE minus baseline | RMSE minus baseline |
|---|---:|---:|---:|---:|
| Training mean | .027083 | .034708 | .000000 | .000000 |
| Six counts | .026970 | .034622 | −.000112 | −.000086 |
| Rates | .027085 | .034721 | +.000003 | +.000013 |
| Rates + batted | .027128 | .034871 | +.000046 | +.000163 |

All three A configurations select alpha **1000 in each of the five original
outer fits**. Rates do not improve that assignment. Across the six shuffled
assignments, rates sometimes improve on counts but **never improve on the mean
baseline in either MAE or RMSE**. They are a plausible representation, not a
validated improvement.

| Configuration | Mean MAE across six seeds | SD across seeds | Mean RMSE | SD across seeds | MAE wins vs mean | RMSE wins vs mean |
|---|---:|---:|---:|---:|---:|---:|
| Training mean | .027597 | .000414 | .035321 | .000484 | — | — |
| Counts | .027936 | .000858 | .035737 | .000959 | 2/6 | 2/6 |
| Rates | .027767 | .000492 | .035470 | .000560 | 0/6 | 0/6 |
| Rates + batted | .027802 | .000375 | .035700 | .000532 | 1/6 | 0/6 |

Rates-minus-counts MAE averages −.000169, but its paired SD is .000458 and only
3/6 split assignments favor rates. Adding batted measurements to rates changes
mean MAE by +.000034 and mean RMSE by +.000230. Rates+batted wins MAE versus
rates in four seeds, but a larger deterioration in another seed outweighs these
small gains; it worsens RMSE in all six. Signs alone can conceal effect size.

## B results — Learning curves

Values are averages across five subset draws, except the all-available point
which has one draw. MAE/RMSE are pooled across each draw's 62 validation players.
The full tables also contain baseline-relative changes, fitting errors and SDs.

| Fitting players | Model | Fit MAE | Validation MAE | Validation MAE SD | Fit RMSE | Validation RMSE | Validation RMSE SD |
|---|---|---:|---:|---:|---:|---:|---:|
| 10 | Mean | .025036 | .028410 | .000632 | .031485 | .036390 | .001050 |
| 10 | Counts | .021689 | .031784 | .004412 | .027288 | .042930 | .009903 |
| 10 | Rates | .019912 | .033784 | .006468 | .025691 | .044513 | .008636 |
| 10 | Rates+batted | .019106 | .031888 | .005081 | .024272 | .042203 | .008210 |
| 20 | Mean | .026370 | .027451 | .000229 | .033483 | .034989 | .000385 |
| 20 | Counts | .024932 | .028875 | .001387 | .032031 | .036885 | .002099 |
| 20 | Rates | .025537 | .027995 | .000402 | .032608 | .035763 | .001096 |
| 20 | Rates+batted | .025214 | .028035 | .000589 | .032167 | .036091 | .001412 |
| 30 | Mean | .026077 | .027210 | .000165 | .032796 | .034971 | .000376 |
| 30 | Counts | .025399 | .027203 | .000302 | .032219 | .034964 | .000291 |
| 30 | Rates | .025618 | .027419 | .000553 | .032315 | .035216 | .000606 |
| 30 | Rates+batted | .025105 | .027593 | .000665 | .031756 | .035723 | .001054 |
| 40 | Mean | .026473 | .026994 | .000132 | .033502 | .034784 | .000139 |
| 40 | Counts | .025877 | .026901 | .000230 | .032938 | .034802 | .000252 |
| 40 | Rates | .026217 | .027017 | .000091 | .033181 | .034859 | .000224 |
| 40 | Rates+batted | .025715 | .027178 | .000465 | .032688 | .035303 | .000716 |
| 49–50 | Mean | .027168 | .027083 | Not estimated | .034533 | .034708 | Not estimated |
| 49–50 | Counts | .027005 | .026970 | Not estimated | .034405 | .034622 | Not estimated |
| 49–50 | Rates | .027074 | .027085 | Not estimated | .034433 | .034721 | Not estimated |
| 49–50 | Rates+batted | .026945 | .027128 | Not estimated | .034301 | .034871 | Not estimated |

Tiny samples have much lower fitting error but worse validation error, particularly
for the more flexible feature representations. At 10 fitting players, inner fits
have only eight players; selecting among alphas is unstable. By 30–50 players,
errors and draw variation are much smaller, and performance approaches the mean
baseline. For counts, validation MAE SD decreases from .004412 at 10 to .000230
at 40. The full-size point has **no estimated subset-draw SD**, not zero uncertainty.

These are strong descriptive signs that very small training samples are a problem.
They support seeking more data for stable estimation. They **do not show** that
adding data beyond the currently observed range will beat the mean baseline: the
curve is already fairly flat near 30–50, and counts at 40 slightly outperform the
49–50 point in MAE. No curve is extrapolated, and no numerical future performance
forecast is made. Retuning and correlated nested subset draws also limit causal
interpretation of sample-size differences.

## C results — Individual and grouped contributions

All changes below compare each addition to **the six counts**, paired across
six seeded nested-CV repetitions. Negative is better. Every added configuration
also has a separate matched mean-baseline comparison in `stability_summary.csv`.

| Added block | Mean MAE change vs counts | Paired SD | MAE wins vs counts | Mean RMSE change | RMSE wins vs counts | MAE / RMSE wins vs mean baseline |
|---|---:|---:|---:|---:|---:|---|
| EV mean | −.000013 | .000300 | 2/6 | −.000002 | 2/6 | 4/6, 3/6 |
| EV p90 | −.000148 | .000287 | 3/6 | −.000142 | 4/6 | 3/6, 2/6 |
| EV max | +.000121 | .000191 | 1/6 | +.000187 | 0/6 | 2/6, 1/6 |
| Hard-hit rate | +.000064 | .000134 | 1/6 | +.000071 | 1/6 | 3/6, 2/6 |
| LA mean | +.000039 | .000263 | 3/6 | +.000048 | 4/6 | 2/6, 3/6 |
| LA median | −.000139 | .000353 | 3/6 | +.000140 | 3/6 | 4/6, 2/6 |
| LA SD | +.000101 | .000184 | 1/6 | +.000046 | 1/6 | 2/6, 1/6 |
| EV group | −.000174 | .000294 | 3/6 | −.000120 | 3/6 | 3/6, 1/6 |
| LA group | −.000010 | .000637 | 2/6 | +.000067 | 1/6 | 2/6, 1/6 |
| All seven | −.000146 | .000358 | 3/6 | −.000060 | 3/6 | 1/6, 0/6 |

The EV group and EV p90 are the most defensible **hypotheses for later validation**,
not established improvements. The EV group's mean MAE (.027762) is the lowest
among these Ridge configurations but still worse than baseline (.027597). Its
baseline-relative MAE ranges from −.000120 to +.001024 across seeds. EV p90 is
similarly inconsistent. Adding the LA block to EV (full minus EV-only) worsens
mean MAE by .000028 and RMSE by .000060; neither group establishes reliable
incremental prediction. Individual additions can look beneficial on one criterion
and harmful on another.

LA mean is best on the original unshuffled assignment (.026906 MAE), but across
seeded splits its average MAE is .027975 versus .027597 for the baseline. This
is a concrete example of why we should not promote the winner of one split.

## D results — Validation instability

All 98 repetition/model records are saved: 7 assignments × 14 predictors/baseline
configurations, each with 62 OOF outcomes. This is **not 434 independent players**;
the same 62 are reused. Summary tables keep the original assignment separate
from the six random assignments rather than averaging them without explanation.

| Configuration | MAE minus mean: average | Paired SD across seeds | Minimum | Maximum | MAE rank range among 14 |
|---|---:|---:|---:|---:|---|
| Counts | +.000339 | .000668 | −.000158 | +.001627 | 2–11 |
| Rates | +.000170 | .000221 | +.000035 | +.000605 | 4–13 |
| Rates+batted | +.000204 | .000215 | −.000010 | +.000484 | 2–14 |
| Counts+EV | +.000164 | .000429 | −.000120 | +.001024 | 2–10 |
| Counts+EV p90 | +.000191 | .000497 | −.000136 | +.001173 | 1–11 |

The six seeded MAE winners are baseline, LA median, EV p90, EV p90, LA mean,
LA median. Rankings change substantially. The baseline has the best **mean MAE
and mean RMSE across seeds**, although not the best score in every seed and not
the best average rank. Rank summaries ignore how large a loss is: small frequent
wins can be outweighed by one much larger deterioration.

The six-count original-split advantage of .000112 MAE is smaller than its seeded
baseline-relative SD .000668. Its absolute MAE changes from .026970 on the original
assignment to .027142–.029143 across seeded assignments. This does not mean any
one seed is correct; fitting/tuning and validation assignments both vary.
Rates appear less split-sensitive but remain slightly worse than the mean.

Across the 30 seeded outer fits, counts select alpha 10 in 3 fits, 100 in 8 and
1000 in 19; rates select 100 in 4 and 1000 in 26; rates+batted select 100 in 6 and
1000 in 24. Tuning is sensitive, and strong shrinkage is still common. We do not
expand the grid or change selection to exploit these results.

Split variation measures sensitivity of this procedure on this fixed cohort.
It does **not** estimate true future-season uncertainty, temporal/population shift,
or label measurement uncertainty. Folds overlap in fitting players, repetitions
reuse every player, and these six seeds are not independent datasets. SDs and
ranges are descriptive; no p-values, significance claim, equivalence claim or
fresh-test performance estimate is made.

## Recommendations, ranked

1. **Obtain more independent training seasons with a prospectively specified
   evaluation.** Learning curves show small-subset instability; additional years
   also permit temporal validation, which repeated partitions of 62 players
   cannot provide. This is a research direction, not a forecast that more data
   will necessarily beat the mean. Do not reclaim frozen excluded-overlap rows
   or change the existing split to enlarge this experiment.
2. **Resolve target definition with Anish and separately version any approved
   standard-wOBA table.** The earlier audit documents measurement problems, and
   this study deliberately retains them. It does not test whether target correction
   improves prediction; that would require a new approved experiment.
3. **Make paired validation-stability reporting and the mean baseline standard
   checks.** Avoid selecting one favorable assignment. Define a new evaluation
   before using new data, and retain the historical six-count Ridge for continuity.
4. **Predeclare a small EV-focused follow-up on new data.** EV p90 and the EV group
   are more promising than EV max or broad feature-subset searching, but currently
   have no consistent advantage over baseline. Do not deploy the apparent best
   block or change this cohort's model based on the same repeated comparisons.
5. **Deprioritize further rate/subset/grid searches on these same players.** Rates
   do not establish an advantage, the optional compact search was omitted, and
   further adaptive choices would increase selection optimism. These results do
   not establish that rates or batted-ball information are generally useless.

No new configuration warrants replacing the original six-count Ridge benchmark.
That is a continuity recommendation under uncertainty, **not** a claim that counts
are intrinsically the best feature representation: several blocks have lower mean
errors than counts across seeds. The mean baseline is at least as important as
Ridge and is the strongest aggregate performer here.

## Reproduction, outputs and checks

Using the existing locked environment, run from the repository root:

```bash
python scripts/ridge_feature_study.py
pytest
ruff check .
```

No network or added dependency is required. Fresh clones regenerate batted
features from the shared archives. A saved prior ablation is an optional read-only
regression comparison; no old experiment entry point is executed. All output is
under ignored **`data/processed/ridge_feature_study_v1/`**:

| Artifact | Contents |
|---|---|
| `metrics.json` | Fixed design, A results, B/C/D summaries, rate coverage, provenance and preservation |
| `validation_fold_metrics.csv` | 490 cases/configurations with exact fit/validation counts, selected alphas, fit and validation errors |
| `validation_predictions.csv` | 6,076 paired OOF predictions across 7 splits × 14 configurations; no holdout |
| `repetition_metrics.csv`, `stability_summary.csv` | Pooled per-split scores, matched mean-baseline deltas, ranks, SDs and ranges |
| `feature_contributions.csv` | Controlled additions/removals compared with counts, rates and EV/LA groups |
| `learning_fold_metrics.csv`, `learning_predictions.csv` | 420 subset-case/configuration records and 5,208 OOF predictions |
| `learning_repetition_metrics.csv`, `learning_summary.csv` | Pooled learning scores by draw and mean/SD across draws |
| `fold_assignments.csv` | 27,090 outer/inner player-role records; one shared assignment per case, not separate folds per configuration |
| `subset_assignments.csv` | 2,500 player membership records for the smaller learning subsets |
| `inner_alpha_scores.csv` | 18,875 alpha/inner-fold validation scores across searches |
| `study_with_features.csv`, `features_batted.csv` | All 926 rows and feature inputs; originals preserved |
| `feature_spot_checks.csv`, `batted_source_anomalies.csv` | Inherited source validation and fixed-key aggregation checks |
| `learning_curves.png/.svg` | Fit/validation errors by size; bands show subset-draw SD, not confidence intervals |
| `validation_stability.png/.svg` | Paired primary-model scores across seeded assignments |
| `feature_contributions.png/.svg` | Batted additions versus counts; bars show split range, not confidence intervals |
| `preserved_inputs.json` | Before/after SHA-256 checks for pre-existing files |

Provenance identifies input/team/pitch/code hashes, Git revision and dirty state,
package versions and deterministic seeds. Scientific scores are reproducible;
plotting metadata and working-tree provenance can vary between runs. The runner
protects all tracked and untracked source files present at startup and all prior
processed results outside its new directory. An independent starting manifest
also preserves the four untracked sensitivity files byte for byte.

Tests cover exact safe-division formulas, zero denominators, unchanged original
columns, predictor allowlists, repeated-player grouping, reproducible seeded
splits, nested player subsets, equivalence of cached preprocessing to the original
Ridge, fit-only imputation, matched model/baseline players and labels, subset-fitted
means, exact sample sizes, JSON null handling and invariance to holdout/excluded/
unlabeled feature and outcome changes.

Limitations remain substantive: only 62 labeled training players, one training
year, the original provisional target, playing-time eligibility selection,
correlated and unevenly measured features, six chosen split seeds, five subset
draws, and many exploratory comparisons on repeatedly inspected observations.
Nested tuning prevents direct outer-label leakage, but it does not remove
researcher-level selection optimism from repeated study design. No subset was
chosen after inspecting results and no new holdout metric was calculated.

Final validation: **167 pytest tests passed** and **Ruff passed**. All **178**
files in the independent pre-study preservation manifest remain unchanged,
including the four prior untracked sensitivity files. All **25** generated
artifacts are ignored. Only the four new study source/test/report files were
added to the working tree; nothing is staged, committed or pushed, and PR #13
is unchanged.

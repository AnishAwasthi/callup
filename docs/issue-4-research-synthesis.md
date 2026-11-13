# Issue #4 — Research synthesis for Anish

**No additional configuration has demonstrated a reliable advantage over the
training-average baseline.** Stop searching this cohort. The next decisions are
target-definition approval, additional independent training seasons, and an agreed
new temporal evaluation. Keep the six-count Ridge as the historical reference,
not as a model established to outperform the mean.

## What is independent evidence?

The [full-cohort wOBA audit](woba-full-cohort-reconciliation.md) independently
matched **239/239 eligible player-seasons** to published FanGraphs records, with
zero ambiguous or unmatched records. Internal event components agree exactly for
**238**; Trey Sweeney's inherited two-strike strikeout explains the remaining
attribution discrepancy. His correction has not been applied. Original provisional
wOBA averages **+.012248** above published values. Standard seasonal reconstruction
reduces mean absolute disagreement from **.012265 to .000068**, with remaining
coefficient-precision and attribution qualifications documented in the audit.
The reconstruction itself is internal; the published references are independent.
This supports a target-definition revision, not a claim of improved prediction.

The later modeling studies reuse **62 labeled training players**, with 2023 AAA
features and provisional 2024 MLB outcomes. Nested folds, subset draws, correlations
and repeated splits are not independent replications. Outer fitting sets contain
49–50 players and validation sets 12–13; tuning and preprocessing stay inside
fitting folds. The original 125-player future-season holdout is distinct, but has
already been inspected. No additional holdout scores were calculated in these
three uncommitted studies. All targets remain provisional and unchanged.

## Numerical evidence

The [initial benchmark](modeling-ridge.md) on the 125-player holdout improved MAE
only from **.035107 to .035010** with Ridge; RMSE worsened from **.046677 to
.046734**. These historical test scores must not be compared directly with the
training-only scores below as evidence of improvement.

The following are pooled nested OOF scores on the **same 62 training players and
original grouped assignment**, using fold-fitted means as the matched baseline:

| Configuration | MAE | RMSE |
|---|---:|---:|
| Training mean | .027083 | .034708 |
| Six original counts | .026970 | .034622 |
| Six counts + seven batted measurements | .027013 | .034774 |
| Six counts, wider alpha search | .027113 | .034664 |
| Thirteen features, wider alpha search | .027075 | .034772 |
| Rates + PA (five predictors) | .027085 | .034721 |
| Rates + PA + seven batted measurements | .027128 | .034871 |

The [batted-ball comparison](ridge-batted-ablation.md) finds no consistent gain.
The [regularization study](ridge-regularization-sensitivity.md) tests 17 alphas
from .001 to 100,000. Lower penalties widen predictions and improve training fit
but generally worsen validation error; three of five outer fits per feature set
choose the expanded upper boundary. Wider predictions are not automatically
better predictions. Small tradeoffs between MAE and RMSE do not establish a
better selection procedure. Reproducing old scores verifies implementation
consistency, not new evidence.

The [feature and stability study](ridge-feature-study.md) repeats nested grouped
validation with six shuffled assignments, retaining matched players/folds across
configurations. Its averages exclude the original unshuffled assignment:

| Configuration | Mean MAE | Mean RMSE | MAE / RMSE wins against mean baseline |
|---|---:|---:|---|
| Training mean | .027597 | .035321 | — |
| Six counts | .027936 | .035737 | 2/6, 2/6 |
| Rates + PA | .027767 | .035470 | 0/6, 0/6 |
| Rates + PA + batted | .027802 | .035700 | 1/6, 0/6 |

Counts' original-split MAE advantage is only **.000112**, versus **.000668 SD**
in its baseline-relative difference across shuffled assignments. Its MAE rank
ranges from 2nd to 11th among fourteen configurations including baseline. The
baseline has the lowest mean MAE and RMSE across these assignments. Split SDs and
ranges are descriptive sensitivity measures, not confidence intervals for future
seasons or evidence of statistical significance.

Controlled individual/group additions offer hypotheses, not a winner. EV p90
and the EV group improve average MAE versus counts by **.000148 and .000174**,
but their paired split SDs are **.000287 and .000294**. Each beats baseline MAE
in only 3/6 assignments; the EV group beats baseline RMSE in only 1/6. Every
Ridge configuration has worse average MAE and RMSE than baseline across the six seeds.
Choosing the best-looking block now would add selection optimism.

## What explains the limitations?

- **Small fitting samples:** learning-curve counts MAE falls from **.031784 at
  10 players** to **.027203 at 30**, **.026901 at 40**, and **.026970 at 49–50**.
  MAE SD across five subset draws falls from **.004412 at 10** to **.000230 at
  40**. At ten players, training MAE is .021689 versus validation .031784.
  More data within this range improves stability, but curves then sit near the
  mean baseline. No numerical extrapolation or promised gain beyond the observed
  sizes is justified; the full-size point has only one subset draw.
- **Weak differentiation:** the [diagnostic study](ridge-limits-diagnostics.md)
  finds training outcome population SD **.034590**, versus saved Ridge prediction
  SD **.001165** and mean-baseline pooled SD **.000940**. The latter reflects
  different fitting-fold means, not within-fold player differentiation.
- **Redundant predictors:** PA–AB Pearson correlation is **.990**, EV mean–hard-hit
  rate **.941**, and LA mean–median **.899**. Standardized-design condition numbers
  are about **88** for counts and **106** combined. This complicates coefficient
  estimation, but does not by itself prove prediction must fail.
- **Influence without a single-player explanation:** largest absolute marginal
  Pearson/Spearman outcome correlations are **.162/.238** (n=62). Removing one
  player from a statistic can change EV-max Pearson from .111 to .211; other
  small associations retain their sign. These correlations do not prove an
  absence of multivariable, nonlinear or future-sample information. Ridge's five
  largest errors account for **22.7% of absolute error**, but **36/62 players**
  have errors above .020. Fourteen players account for half the absolute error;
  eight account for half the squared error. Errors are tail-sensitive but broad.

The diagnostic fits no models. Its one-player omissions recompute correlations
or score fixed saved predictions; they are not refitted leave-one-out validation.
Future MLB playing time is excluded from predictor/error-association analysis.
The studies cannot isolate causal explanations for failure, establish equivalence
to the mean, or independently confirm small gains after repeated cohort reuse.

## Minimal next stage requiring agreement

1. **Anish approves a separately versioned standard-seasonal-wOBA target**, with
   the explicit Sweeney attribution ledger and precision/reconciliation acceptance
   rules. Preserve original outcomes, split and results. Correct measurement is
   justified by the audit; improved predictive accuracy remains untested.
2. **Expand independent, completed historical training seasons.** Agree on a new
   data version and consistent feature/eligibility rules. Do not enlarge this
   experiment by reclaiming frozen excluded-overlap players or using incomplete
   cached outcomes. Additional years may improve estimation and permit temporal
   validation, but success is not guaranteed.
3. **Agree on a new untouched temporal evaluation before seeing its outcomes.**
   Specify baseline, six-count reference, any small predeclared EV hypothesis,
   tuning, metrics and player-overlap handling. Keep the inspected historical
   holdout as historical evidence; do not call another comparison on it confirmatory.

## Reproducibility and review scope

This synthesis reads existing reports/artifacts; no experiment was rerun to write
it. Original scripts/tests/reports remain separate and unchanged. The three study
reports link their existing runners, tests, seeds, input/code hashes and figures:

| Study | Existing runner | Ignored output under `data/processed/` |
|---|---|---|
| Regularization | `scripts/ridge_regularization_sensitivity.py` | `ridge_regularization_sensitivity_v1/metrics.json`, `alpha_summary.csv`, `nested_fold_metrics.csv` |
| Features/sample size/stability | `scripts/ridge_feature_study.py` | `ridge_feature_study_v1/metrics.json`, `repetition_metrics.csv`, `learning_summary.csv`, `feature_contributions.csv` |
| Signal/redundancy/residuals | `scripts/diagnose_ridge_limits.py` | `ridge_limits_diagnostics_v1/diagnostics.json`, `outcome_associations.csv`, `collinearity_blocks.csv`, `error_concentration.csv` |

The initial numbers come from `data/processed/model_metrics.json`; the committed
ablation uses `ridge_batted_ablation_v1/metrics.json`; audit coverage/statistics
use `woba_cohort_v1/summary.json` and curated tracked reference fixtures. All new
modeling uses the original provisional target. The diagnostic runner requires
saved feature-study artifacts and refuses to regenerate models if they are absent.
The other study runners refit models when deliberately invoked; they are not
necessary for reading this synthesis. Validate reviewed code with `pytest` and
`ruff check .`; leave generated tables, captures, predictions and figures ignored.

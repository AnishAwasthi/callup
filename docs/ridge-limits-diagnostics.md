# Final bounded Ridge limitations diagnostics

The new diagnostics support **broadly weak marginal differentiation plus substantial
predictor redundancy**, with some sensitivity to individual players. A few extreme
outcomes increase squared error, but they do not explain all the prediction error.
This does not establish why the model fails causally, prove that useful nonlinear
signal is absent, or select a better model.

## Scope and reproducibility

All statistics use only the **62 original labeled training players**: 2023 AAA
features and provisional 2024 MLB wOBA. The existing six-count Ridge and fold-fitted
mean predictions are read from the prior feature study's original unshuffled nested
OOF run (seed −1). The diagnostic does **not fit models, search alphas, make new
predictions, evaluate the holdout, or change the cohort**. Full shared-table loading
is solely for contract/key validation before selecting the 62 training rows.

Code, prior studies/results, tests, contract and Git status were inspected first.
The eight previously untracked sensitivity/feature-study files remain untouched.
At the start, an independent manifest protected **207** pre-existing files,
including all original datasets, prior artifacts and committed/uncommitted work.

Run with the existing locked dependencies:

```bash
python scripts/diagnose_ridge_limits.py
pytest
ruff check .
```

Required read-only inputs are the shared hitter table and existing ignored
`data/processed/ridge_feature_study_v1/features_batted.csv` and
`validation_predictions.csv`. If the saved artifacts are absent, restore them;
the runner fails explicitly instead of regenerating models. The integration test
skips when those optional prior artifacts are absent in a fresh checkout.

## A — Feature–outcome associations

All correlations below have **n=62 complete pairs**. Pearson describes linear
association; Spearman describes rank/monotonic association and uses average ranks
for ties. Missing pairs would be excluded with their actual n reported; constant
variables or fewer than three pairs produce an explicit unavailable result.
No p-values, causal interpretations or statistically confirmed discoveries are
reported. These are 26 exploratory summaries of previously studied players.

| AAA feature | Pearson | Spearman |
|---|---:|---:|
| PA | .112 | .114 |
| Hits | .160 | .127 |
| AB | .105 | .126 |
| BB | .109 | .073 |
| K | .030 | .068 |
| HR | .162 | .212 |
| EV mean | .056 | .104 |
| EV p90 | .124 | .208 |
| EV max | .111 | .238 |
| Hard-hit rate | −.002 | .035 |
| LA mean | −.114 | −.093 |
| LA median | −.090 | −.095 |
| LA SD | −.008 | −.017 |

The largest absolute Pearson association is only .162; the largest Spearman
association is .238. This is weak-to-modest marginal association in this sample,
not proof that multivariable, nonlinear or future-sample information is absent.
The highest correlation is not used to nominate or select a preferred predictor.

### One-player omission sensitivity

For each feature/method, recompute the correlation after omitting each player
from the **statistic**, giving 62 calculations with n=61 each. The stored cohort
is unchanged and no predictions are refitted. These ranges are not confidence
intervals or independent replications.

| Association | Full correlation | One-player-omission range | Observation |
|---|---:|---|---|
| HR, Pearson | .162 | .126 to .222 | Small positive association persists |
| EV max, Pearson | .111 | .048 to .211 | Largest single-player change is .100 |
| EV max, Spearman | .238 | .207 to .300 | Positive rank association persists |
| Hard-hit rate, Pearson | −.002 | −.072 to .086 | Sign flips in 25/62 omissions around an almost-zero estimate |
| LA mean, Pearson | −.114 | −.146 to −.059 | Small negative association persists |

Omitting Xavier Edwards changes EV-max Pearson from .111 to .211; his omission
also changes EV mean and EV p90 Pearson by about .090 and .088. Omitting
Christian Encarnacion-Strand changes HR Pearson by about .060. These players
influence some estimates, but no single-player omission creates a strong Pearson
association: the maximum across all omission calculations is .222. Some small
associations are stable in sign; it would be inaccurate to call every relationship
unstable. Near-zero estimates are especially easy to reverse.

### Predictor redundancy and multicollinearity

All block diagnostics use the same 62 complete training rows. Matrix SVD is
applied to centered, population-standardized predictors; VIF is the diagonal
inverse correlation matrix. **No auxiliary regression models are fitted.**

| Block | Features / numerical rank | Standardized-design condition number |
|---|---|---:|
| Six counts | 6 / 6 | 87.89 |
| Seven batted measurements | 7 / 7 | 8.27 |
| Combined | 13 / 13 | 105.81 |

Examples of predictor–predictor Pearson correlations are PA versus AB **.990**,
EV mean versus hard-hit rate **.941**, hits versus AB **.930**, and LA mean versus
median **.899**. In the count block, VIF is approximately **1,018 for PA**, **728
for AB**, and **41 for BB**. Combined-block PA and AB VIFs are about 1,343 and
970. Full tables include all pairs, both correlation methods, VIFs and singular
values. The matrices have full numerical rank, but contain substantial redundant
information, especially among related playing-time counts.

This helps explain why individual coefficients can be unstable and why additional
columns may add little new information. Ridge can handle redundant predictors;
redundancy alone is not proof of poor prediction. The prior rates experiment did
not establish that removing shared count denominators fixes performance.

## B — Outcome distribution and saved residuals

Provisional training wOBA has mean **.310097**, sample SD **.034872** and population
SD **.034590**. Quantiles are:

| Minimum | 5th | 25th | Median | 75th | 95th | Maximum |
|---:|---:|---:|---:|---:|---:|---:|
| .213312 | .248447 | .288739 | .309307 | .335512 | .363850 | .376000 |

Residual means observed outcome minus saved prediction. Original keys, outcomes
and fold assignments are checked before analysis; the saved mean predictions are
verified against their fitting-fold means. No future MLB playing-time variable
is passed into predictor or error-association analysis. Such variables are not
needed for this diagnostic and are omitted entirely.

| Saved OOF configuration | n | MAE | RMSE | Prediction population SD | Median absolute error |
|---|---:|---:|---:|---:|---:|
| Six-count Ridge | 62 | .026970 | .034622 | .001165 | .022258 |
| Fold-fitted mean | 62 | .027083 | .034708 | .000940 | .022620 |

These reproduce earlier errors, not new validation evidence. Outcomes vary much
more than predictions. The mean baseline's pooled spread reflects different
fitting-fold means, not player-specific prediction within a fold.

### Error concentration and influential players

| Largest-error players | Ridge absolute-error share | Ridge squared-error share |
|---:|---:|---:|
| 1 | 5.8% | 12.8% |
| 3 | 15.2% | 29.2% |
| 5 | 22.7% | 40.0% |
| 10 | 39.5% | 61.3% |
| 20 | 62.9% | 82.3% |

The mean baseline has almost identical concentration. **14 players account for
half of total absolute error; eight account for half of squared error.** Ridge
absolute errors exceed .010 for 44 players, .020 for 36, and .050 for ten. Errors
are tail-sensitive, especially squared errors, but not confined to one or two
players.

The five largest Ridge errors are Alex Jackson (.097520), Christian
Encarnacion-Strand (.082747), Dominic Fletcher (.073159), Xavier Edwards (.064642)
and Noelvi Marte (.061711). They include both lower- and higher-than-predicted
outcomes. Names/IDs and every residual are retained for inspection, not exclusion.

For fixed-prediction sensitivity, omit one player's scored error at a time without
refitting anything. Omitting Alex Jackson's error reduces Ridge MAE from .026970
to **.025814** and RMSE from .034622 to **.032595**. The remaining predictions still
come from the original fits, which may have included the omitted player in other
folds. This is **not LOOCV** and does not estimate a refitted model's influence.

Across all single-player scoring omissions, Ridge-minus-mean MAE remains between
**−.000139 and −.000087**; RMSE difference stays between **−.000114 and −.000056**.
The original split's tiny Ridge advantage is therefore not created by just one
scored observation. This does not overcome its previously demonstrated split
instability or show a statistically reliable gain. Omitting one outcome changes
the descriptive training mean by at most .001587; the remaining mean ranges
.309016–.311683.

### Error versus pre-outcome information

For Ridge, absolute error versus AAA PA has Pearson **−.022** and Spearman
**+.012**, both with n=62. The baseline gives almost the same values. Training-PA
tertiles contain 21, 20 and 21 players:

| AAA PA range | n | Ridge MAE | Ridge RMSE |
|---|---:|---:|---:|
| 158–263 | 21 | .027088 | .036517 |
| 269–367 | 20 | .028286 | .035330 |
| 375–537 | 21 | .025600 | .031885 |

The highest-PA group has somewhat lower errors, but there is no clear monotonic
MAE pattern or strong continuous relationship. Across the other twelve predictors,
absolute-error associations are also small: Ridge's largest absolute Pearson is
about .157 and largest absolute Spearman about .159. These explorations do not
identify a convincing pre-outcome subgroup that explains the bulk of error.
Relationships involving errors are descriptive and conditional on the saved
predictions and selected cohort, not causal effects of playing time or contact.

## C — What this adds, and what remains a hypothesis

**Supported observations:** marginal feature–outcome associations are generally
small; several near-zero/EV estimates are sensitive to individual players;
count predictors and some batted summaries are redundant; both saved predictors
barely differentiate outcomes; large errors increase RMSE but substantial error
is spread across many players. Single-player scoring omissions do not reverse
the original split's tiny model difference.

**Hypotheses, not established explanations:** redundant features may make
coefficients harder to estimate; small samples and target noise may obscure real
signal; additional years may improve estimation; nonlinear structure or other
information may matter. This diagnostic does not isolate causal contributions to
model failure, assess how refitting without influential players would change
predictions, or establish that any feature is useless.

Current data can support transparent residual review, auditing suspicious source
records, and documenting redundant measurements. It cannot create independent
validation, reliably establish a new feature's usefulness, or justify deleting
players. Keep the cohort unchanged. Additional historical training seasons and
prospectively specified temporal evaluation are needed for stronger predictive
claims. Standard-wOBA target replacement still requires Anish's approval and a
separate version; no corrected targets were used here.

All evidence here reuses the same 62 previously analyzed players. It adds an
explanation of marginal signal, redundancy and error concentration to earlier
performance experiments, not independent confirmation, new model rankings or
statistical significance.

## Files and safeguards

New source/test files are `callup/ridge_diagnostics.py`,
`scripts/diagnose_ridge_limits.py`, `tests/test_ridge_diagnostics.py`, plus this
report. Outputs are ignored under **`data/processed/ridge_limits_diagnostics_v1/`**:

- `diagnostics.json`: distribution, association and collinearity summaries,
  saved error metrics, definitions, input/code hashes and preservation metadata.
- `outcome_associations.csv`, `lopo_associations.csv`: full and all 61-player
  omission correlations, sample sizes and largest changes.
- `predictor_pairs.csv`, `pearson_matrix.csv`, `spearman_matrix.csv`,
  `collinearity_blocks.csv`, `collinearity_vif.csv`, `singular_values.csv`:
  redundancy diagnostics with explicit numerical-rank status.
- `residuals.csv`, `residual_summary.csv`, `ranked_errors.csv`,
  `error_concentration.csv`: all saved errors and their concentration.
- `lopo_fixed_prediction_metrics.csv`, `lopo_metric_differences.csv`,
  `lopo_outcome_mean.csv`: omission sensitivity without model refits.
- `error_feature_associations.csv`, `aaa_pa_error_bins.csv`: pre-outcome-only
  descriptive error relationships.
- `outcome_associations.png/.svg`, `predictor_correlations.png/.svg`,
  `outcomes_and_errors.png/.svg`: exploratory visualizations; omission ranges
  are not confidence intervals.
- `preserved_inputs.json`: hashes protecting all pre-existing files.

Tests cover ties, missing/constant correlations, exact player omissions,
collinearity matrices and rank deficiency, prediction key/label/fold consistency,
fold-fitted mean verification, residual/concentration arithmetic, fixed-prediction
omissions, pre-outcome allowlists and invariance to future MLB PA. A real-input
test blocks Ridge/GridSearchCV fitting while running the diagnostics.

Final validation: **174 pytest tests passed** and **Ruff passed**. All **207**
pre-existing file hashes remain unchanged; all **26** generated diagnostic
artifacts are ignored. The diagnostic fitted zero models and ran zero searches.
Nothing was staged, committed or pushed, and PR #13 remains unchanged.

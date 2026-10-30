# PRELIMINARY — Callup modeling results for discussion

We have a reproducible first modeling result: a training-average benchmark and
a leakage-safe Ridge comparison on a frozen, player-disjoint future-season test
set. Ridge has not demonstrated a meaningful predictive improvement. These
models predict the project's **provisional served-event wOBA labels**, whose
definition differs from published FanGraphs wOBA; they do not establish accurate
prediction of official FanGraphs outcomes.

## Question, population, and approach

Can a hitter's Triple-A season help predict next-season MLB batting performance?
The study pool requires at least 150 AAA PA. Modeling additionally requires an
available outcome and at least 75 next-season MLB PA.

| Frozen partition | Feature → outcome year | All player-seasons | Available labels |
|---|---|---:|---:|
| Train | 2023 → 2024 | 208 | 62 |
| Test | 2024 → 2025 | 456 | 125 |
| Excluded overlap | 2023 → 2024 | 262 | 52 |

Rows equal distinct players within each partition. Full-cohort overlap is
checked before label filtering; excluded rows never train the models. Findings
apply to hitters with usable MLB outcomes, not all AAA hitters.

The baseline predicts the unweighted training mean, **0.31009660**, for everyone.
Ridge uses the six approved counts: AAA PA, hits, at-bats, walks, strikeouts,
and home runs. Median imputation and standardization are inside the Pipeline
and are refitted within each training fold. Valid starter counts are complete,
so imputation is currently a no-op. IDs and future MLB fields are not predictors.

Deterministic five-fold GroupKFold, grouped by player ID, selects alpha by mean
validation MAE from the predefined grid `[0.1, 1, 10, 100, 1000]`. Selected
**alpha = 100**, with validation MAE **0.02681562**. The final Pipeline is refitted
on all 62 training labels. No test data are used for tuning or preprocessing.

## PRELIMINARY numerical results

Both models evaluate exactly the same 125 labeled test player-seasons.

| Model | MAE ↓ | RMSE ↓ | R² ↑ |
|---|---:|---:|---:|
| Training average | 0.03510651 | 0.04667678 | -0.07754577 |
| Ridge | 0.03501012 | 0.04673390 | -0.08018468 |

Ridge reduces MAE by only **0.00009638 wOBA (about 0.27%)**, while RMSE and R²
worsen slightly. Negative R² means more squared error than a constant equal to
the test-target mean, an evaluation reference that was not used for fitting.
We have not established statistical significance or a reliable improvement.

The plots show strong shrinkage toward the training mean. Ridge predictions
span **0.30324–0.31856**, with standard deviation **0.00324**, compared with
observed test standard deviation **0.04515**. It does not capture the observed
spread well. Small training size, limited count features, temporal/population
shift, and provisional outcomes constrain interpretation; these diagnostics
do not justify changing tuning based on this already-inspected test set.

Ridge standardized coefficients (wOBA per one training standard deviation):

| Predictor | Coefficient |
|---|---:|
| aaa_pa | +0.000463 |
| aaa_hits | +0.001482 |
| aaa_ab | +0.000346 |
| aaa_bb | +0.000743 |
| aaa_k | -0.000672 |
| aaa_hr | +0.001744 |

The fitted intercept is 0.31009660. These are conditional associations in a
regularized model. The counts are correlated and share playing-time information,
so individual coefficients are difficult to interpret causally or as isolated
feature importance. No coefficient uncertainty estimates are claimed.

## PRELIMINARY outcome validation and questions for Anish

The independent five-player FanGraphs pilot found prepared-minus-reference gaps:

| Player / MLB outcome year | Gap |
|---|---:|
| Nathan Lukes / 2024 | +0.012636 |
| Joey Ortiz / 2024 | +0.011336 |
| Bligh Madris / 2024 | +0.009000 |
| Junior Caminero / 2025 | +0.015965 |
| James Wood / 2025 | +0.011307 |

All exceed reference rounding tolerance. Internal investigation identified
nonstandard credits for errors, fielder's choices, bunts, intentional walks,
and interference, plus seven missing denominators on observed ordinary outs.
Using standard conventions and seasonal coefficients internally brings four
within 0.0005 of the published values; Caminero retains a roughly -0.000590
residual. Internal reconstructions are not independent references or approved
replacement targets. See [validation methodology and sources](outcome-validation.md).

Discuss with Anish: Which precise wOBA definition should be the target? How
should missing denominators and unusual events be handled? What further
reconciliation is required before expansion or target revision? What new
features and future evaluation design should follow outcome review? No target,
label, split, feature, or model-selection changes have been made. Selection into
MLB playing time, small-sample uncertainty, and lack of independent target
verification remain open limitations.

## Reproduce and present

With the locked dependencies installed, run from the project root:

```bash
python scripts/model_diagnostics.py
```

This calls the existing committed fitters without changing their settings.
Coefficient extraction repeats the unchanged training-only fit and asserts that
its predictions match the comparison model. It replaces ignored predictions/
metrics and writes coefficient, residual, extreme-error, and metric-comparison
CSVs under `data/processed/`. Metrics retain input checksum, Git state, settings,
and counts. `--input PATH` supports synthetic setup checks; those are not the
full-table result above. No models are tuned using these diagnostics.

All figures are explicitly PRELIMINARY; PNG is convenient for slides and SVG
for scaling. They live under ignored `data/processed/figures/` and must be
regenerated after cloning:

- [Observed versus predicted, both models](../data/processed/figures/observed_vs_predicted.png): identical axes and y=x reference; all 125 observations per model, with overlap possible.
- [Ridge residuals](../data/processed/figures/ridge_residuals.png): observed minus predicted; negative means overprediction. The three largest errors in each direction are labeled by MLBAM ID.
- [Standardized coefficients](../data/processed/figures/ridge_coefficients.png): conditional associations with the correlation caveat.
- [Metric comparison slide](../data/processed/figures/model_comparison.png).

The largest overpredictions are IDs **680577, 683770, 678489**; the largest
underpredictions are **694388, 669065, 701350**. Exact predictions, residuals,
and display names are in `data/processed/ridge_residual_extremes.csv`.

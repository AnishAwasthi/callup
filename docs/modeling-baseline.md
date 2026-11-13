# Preliminary training-average baseline

Run from the project root with the project's installed dependencies:

```bash
python scripts/train_baseline.py
```

The default input is `data/shared/processed/hitter_seasons.csv`. An optional
`--input PATH` supports setup checks with synthetic tables. Never mix real and
synthetic rows. A small fixture run is a setup check, not full-table evaluation;
the output counts and data checksum identify the actual input used.

The script writes `data/processed/model_metrics.json` and
`data/processed/predictions.csv`, replacing prior baseline outputs at these
paths. These files are ignored by Git. No new dependencies are required.

`callup.modeling.training_average_baseline` validates the full cohort before
filtering labels, including player disjointness across training and test.
It requires the frozen 2023 training/excluded and 2024 test seasons and checks
that excluded-overlap players occur in the full test cohort. Only available,
eligible training labels contribute to the unweighted arithmetic mean. Each
available test label receives this constant prediction. Unavailable outcomes
are never imputed, and excluded-overlap rows never contribute to fitting or
evaluation. No predictor columns, scaling, imputation, tuning or randomness
are used.

`regression_metrics` calculates test MAE as mean absolute error, RMSE as the
square root of mean squared error, and R² as one minus squared prediction error
divided by squared deviations from the test-target mean. The test mean is used
only for evaluation. R² is JSON null with an explanatory reason for fewer than
two targets or constant targets. Empty labeled training/test sets and nonfinite
available outcomes are errors. Metrics record full and labeled row/player
counts, missing/unavailable outcomes, excluded rows, settings, input SHA-256,
Git revision and working-tree dirty status. With uncommitted changes, the Git
revision alone does not identify the implementation; retain the reviewed code
alongside the outputs.

## Full shared-table result

Run on October 29, 2026, using input SHA-256
`5715a003e98e5c42c3eafab7bc32a36085da3fa5080f57c1a3db9a7a6c34cc36`.

| Partition | All rows / players | Available labels | Unavailable labels |
|---|---:|---:|---:|
| Train | 208 | 62 | 146 |
| Test | 456 | 125 | 331 |
| Excluded overlap | 262 | 52 | 210 |

All 926 rows were checked before label filtering. All 262 excluded-overlap
rows remain excluded. The fitted training mean is **0.3100966015380032**.

| Test metric | Value |
|---|---:|
| MAE | 0.03510650943598129 |
| RMSE | 0.0466767786090525 |
| R² | -0.07754577053190914 |

Negative R² means this prediction has more squared error than a constant equal
to the test mean; the test mean was not used to fit the baseline.

## Outcome validation status and limits

**These results are preliminary: independent outcome validation remains
pending.** No independent season-level reference comparisons have been
performed in this baseline change. Issue #4 still requires initial 3–5 player
comparisons, broader eligible-row reconciliation where references exist, and
Anish's review of unresolved differences before results are treated as reliable.
The supplied provisional wOBA labels and frozen split are unchanged.

Evaluation describes only hitters with usable next-season MLB outcomes, not
every Triple-A hitter. It does not correct selection into MLB playing time.
Ridge regression and its training-only preprocessing are deferred.

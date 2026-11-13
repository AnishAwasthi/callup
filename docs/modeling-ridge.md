# Preliminary baseline and Ridge comparison

Install the locked dependencies, then run from the project root:

```bash
python -m pip install -r requirements-lock.txt
python scripts/train_models.py
```

The script defaults to `data/shared/processed/hitter_seasons.csv`. `--input PATH`
supports synthetic setup checks. Those checks are not full-table evaluation;
input checksums, data kind, and partition counts identify the input actually used.
Real and synthetic rows cannot be combined.

## Model selection fixed before test evaluation

Ridge uses only `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr`, in that order.
An explicit allowlist rejects IDs, outcome columns, split indicators, provenance,
and other unapproved predictors. Player ID is used only for validation, grouping,
and output identification.

The alpha grid is **[0.1, 1, 10, 100, 1000]**. Choose the alpha with the lowest
**mean validation MAE** across deterministic **five-fold GroupKFold**, grouping
by `player_id`, with `shuffle=False`. Folds have equal weight in the selection
score. Exact ties choose the first alpha in the ascending grid. These choices
are specified before evaluating the frozen test set; test scores do not revise
the grid, scoring rule, or features. Smaller setup fixtures use
`min(5, number of training players)` folds and require at least two players.

GridSearchCV fits the entire following Pipeline independently inside each fold:

1. `SimpleImputer(strategy="median", keep_empty_features=True)` learns feature
   medians from the fold's training rows. An entirely missing feature in a fold
   is retained and filled with zero.
2. `StandardScaler` learns feature means and standard deviations from those
   imputed training rows. Constant features retain scale 1.
3. `Ridge(fit_intercept=True, solver="svd")` learns coefficients with an L2
   penalty. The intercept is unpenalized. No sample weights, target scaling,
   prediction clipping, or random operations are used; the random seed is null.

After alpha selection, GridSearchCV refits the Pipeline on all available
training labels. Only then is the test feature matrix transformed and predicted.
The shared validator still rejects missing/noninteger starter AAA counts, so
imputation is a no-op for valid current cohort inputs. Synthetic feature-matrix
tests exercise imputation without changing the cohort contract.

Full-cohort overlap checks occur before filtering to available labels. The
2023 training rows, 2024 test rows, and excluded-overlap rows retain their frozen
assignments. Available labels must be eligible and finite; missing outcomes are
never imputed. Excluded-overlap and unavailable-label rows influence neither
preprocessing nor alpha selection. Both models use the exact same test rows.

## Outputs and reproducibility

The comparison command replaces ignored `data/processed/model_metrics.json`
and `data/processed/predictions.csv`. JSON has a `models` object with
`training_average` and `ridge` entries. Each records metrics, predictors,
partition/label/missing/drop counts, input checksum, Git revision, dirty status,
and settings. Ridge also records candidate validation MAEs, selected alpha,
fitted preprocessing statistics, and scikit-learn version at the top level.
CSV contains both models, one row per evaluated player-season per model, with
the contract's identifiers, true/predicted values, and version fields.

`scripts/train_baseline.py` remains independently runnable and retains its
baseline-only output schema. Running it replaces the same two output files
with baseline-only results; rerun `train_models.py` to restore the comparison.
Keep the reviewed source with outputs generated from a dirty working tree,
because the recorded Git revision alone cannot reproduce uncommitted changes.

## Limits and outcome validation

**All results are preliminary: independent season-level MLB wOBA validation is
pending.** The supplied labels and split are unchanged. Issue #4 still requires
initial 3–5 player reference comparisons, broader reconciliation where possible,
and Anish's review of unresolved discrepancies before treating results as reliable.

Only 62 labeled players are available for model fitting and alpha selection.
Cross-validation estimates may be unstable, and testing covers a later season
and a different player population. Results apply to usable MLB outcomes, not all
Triple-A hitters. This implementation does not address promotion selection bias
or establish causal relationships. The six count predictors are preliminary.

## Full shared-table result: October 29, 2026

Input SHA-256:
`5715a003e98e5c42c3eafab7bc32a36085da3fa5080f57c1a3db9a7a6c34cc36`.
Both models fit 62 labeled training players and evaluate the same 125 labeled
test players. Full partition sizes are 208 training, 456 test, and 262 excluded
overlap. No excluded rows enter fitting, tuning, or evaluation.

Selected alpha: **100**. Training-only mean cross-validation MAE:

| Alpha | Mean validation MAE |
|---|---:|
| 0.1 | 0.0276865763 |
| 1 | 0.0273470036 |
| 10 | 0.0268388933 |
| 100 | 0.0268156217 |
| 1000 | 0.0271022036 |

| Model | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|
| Training average | 0.0351065094 | 0.0466767786 | -0.0775457705 |
| Ridge | 0.0350101245 | 0.0467338994 | -0.0801846800 |

Ridge's MAE is slightly lower, while RMSE and R² are slightly worse. This does
not demonstrate a reliable improvement. Both negative R² values indicate more
squared error than the evaluation-only test-mean reference. The alpha grid and
selection rule were not changed after seeing these results.

Verification: 94 tests passed, Ruff passed, and `pip check` reported no broken
requirements. The standalone baseline command reproduced its previous results.
The comparison command was run afterward so the final ignored outputs contain
both models (250 prediction rows). Independent outcome validation remains pending.

# Exploratory Ridge regularization sensitivity — provisional outcome, v1

The evidence points toward **limited reproducible predictive signal in these
features and this small cohort**, rather than an obvious penalty-setting error.
Lower penalties produce larger coefficients, more varied predictions and better
training fit, but worse validation error. Widening the alpha search does not
meaningfully improve nested validation compared with the committed old-grid
experiment or a fold-fitted training-average predictor.

This is a new training-only investigation, not a replacement for the initial
Ridge benchmark or [committed batted-ball ablation](ridge-batted-ablation.md).
No target correction or production model change is made. In particular,
standard seasonal wOBA and the Sweeney attribution correction remain proposals.

## Inputs, preservation and implementation

Work began with a clean `issue-4-ridge-model` working tree at
`05a82eeeb6c50f72af4983a9f1b197dfaad38a63`. The existing pipeline,
`callup/modeling.py`, ablation module/runner, their tests and reports were read
before implementation. They remain unchanged. New implementation files are:

- `callup/ridge_sensitivity.py`: alpha paths, diagnostics and nested comparisons.
- `scripts/ridge_regularization_sensitivity.py`: reproducible offline runner,
  source/preservation checks, saved-result comparisons and plots.
- `tests/test_ridge_sensitivity.py`: grouping, preprocessing, invariance,
  penalty behavior and regression tests.
- This report.

The runner calls the existing validated Azra-feature builder and the existing
one-to-one feature join, without executing either previous experiment's writing
entry point. It regenerates a separate 926-row feature table under its own output
directory; original study columns and keys are unchanged. Source checks and the
three documented repeated in-play anomalies are inherited from the ablation.
They remain uncorrected and do not alter the seven model measurements.

Both feature configurations are fixed in advance:

| Configuration | Predictors |
|---|---|
| Six counts | `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr` |
| Thirteen features | Those six plus `ev_mean, ev_p90, ev_max, hard_hit_rate, la_mean, la_median, la_std` |

The target is the **original provisional `mlb_woba`**. Training uses the same
62 labeled players (2023 AAA features, 2024 MLB outcomes); all 926 cohort rows
retain their frozen splits and flags. The 125 labeled test players, excluded
overlap rows and unavailable outcomes do not enter tuning, fitting or reported
new evaluation. No new test predictions or test scores are calculated.

## Design fixed before results

The wider grid has **17 values**, spaced every half decade from .001 to 100,000:

`.001, .003162, .01, .031623, .1, .316228, 1, 3.162278, 10, 31.622777, 100,
316.227766, 1000, 3162.277660, 10000, 31622.776602, 100000`.

The implementation uses exact floating-point powers of ten, not the rounded
spellings above. It includes all original candidates `.1, 1, 10, 100, 1000`.
Both feature configurations use identical deterministic `GroupKFold` partitions
by `player_id`, with `shuffle=False`. The saved outer and inner assignment table
reproduces the previous ablation exactly.

There are five outer validation folds with **13, 13, 12, 12, 12 players**;
outer fitting subsets have 49, 49, 50, 50, 50 players. Each fitting subset has
five inner folds (9–10 validation players, 39–40 fitting players). Alpha is
chosen independently for each feature configuration and each outer fit by
lowest **mean inner-fold MAE**. Exact ties choose the first ascending alpha.
RMSE is recorded but is not used to select alpha.

Every fit starts a fresh existing Ridge pipeline: fit-only median imputation,
StandardScaler, unpenalized intercept and SVD solver. As in the ablation, entirely
unmeasured fit columns would be dropped rather than zero-filled; none is missing
in the real feature table. No sample weights, target scaling, clipping, new
features or interactions are used. The objective is ordinary squared-error
Ridge with L2 penalty; its tuning criterion remains MAE for comparability.

Three complementary outputs must be kept distinct:

1. **Fixed-alpha paths:** each alpha is evaluated on the shared five outer folds
   without selection, recording fit/validation MAE and RMSE, standardized
   coefficient L1/L2/max magnitude and prediction SD/variance. These diagnose
   the penalty effect. Choosing the best point on these curves reuses those
   validation labels and is not independent evidence of improved generalization.
2. **Nested evaluation:** each outer fit selects alpha using only its inner
   folds. The wider-grid procedure and original-grid procedure are evaluated
   on exactly the same outer players. Original-grid selection reuses only the
   corresponding inner scores, never scores from other outer fitting subsets.
3. **Training-average baseline:** each outer fitting subset supplies its own
   mean outcome, predicted for that subset's outer validation players. Using
   the overall 62-player mean here would leak validation outcomes and is not done.

Full-training fits along the grid are saved only as coefficient/spread/fit-error
diagnostics. The final all-training CV choice is recorded, but is neither used
to report a new test result nor adopted as a replacement model.

## Alpha paths: training fit, validation error and shrinkage

The following are **mean fold errors** from fixed-alpha paths, not nested
selection performance. Coefficient norms exclude the intercept and refer to
standardized inputs; coefficients on correlated features are not causal effects.
Prediction SD is averaged **within validation folds**.

| Features | Alpha | Fit MAE | Validation MAE | Fit RMSE | Validation RMSE | Coefficient L2 | Validation prediction SD |
|---|---:|---:|---:|---:|---:|---:|---:|
| Six | .001 | .025603 | .028771 | .033148 | .036057 | .103806 | .008826 |
| Six | 31.623 | .026245 | .026710 | .033747 | .033851 | .004714 | .004273 |
| Six | 100 | .026557 | .026816 | .034019 | .033816 | .002392 | .003029 |
| Six | 1000 | .027005 | .027102 | .034405 | .033973 | .000445 | .000772 |
| Six | 100000 | .027166 | .027210 | .034532 | .034072 | .000005 | .000009 |
| Thirteen | .001 | .024285 | .032195 | .030961 | .039312 | .204779 | .017239 |
| Thirteen | 100 | .025984 | .026974 | .033342 | .034501 | .003736 | .004522 |
| Thirteen | 1000 | .026874 | .027144 | .034268 | .034113 | .000638 | .001013 |
| Thirteen | 100000 | .027165 | .027210 | .034530 | .034074 | .000007 | .000012 |

Reducing alpha from 100 to .001 widens predictions, but increases validation
MAE by about .001955 for six features and .005221 for thirteen. For thirteen
features at .001, the fit-versus-validation MAE gap is about .007911, versus
.000991 at alpha 100. This is evidence consistent with fitting noise at weak
regularization, especially with the larger feature block.

At the opposite extreme, alpha 100,000 nearly eliminates coefficient magnitudes
and within-fold prediction variance. Predictions approach the fitting mean.
This is mechanical underfitting of player differences, but a lower-variance mean
can still be competitive when fitted differences do not generalize. The nearly
flat high-alpha validation curve gives no evidence that more varied predictions
would necessarily be more accurate. Higher penalties monotonically increase
training squared error, not necessarily training MAE; the two objectives differ.
Some folds have lower validation than training error because their player/outcome
mixes differ, so an individual negative error gap is not proof against overfitting.

## Where do selected alphas land?

| Fit population / selection | Six features | Thirteen features |
|---|---:|---:|
| All 62 training players, old-grid mean CV MAE | 100 | 100 |
| All 62 training players, wide-grid mean CV MAE | **31.623** | **100** |
| Outer fit 1, inner-CV selection | **100000** | **100000** |
| Outer fit 2 | 1000 | 1000 |
| Outer fit 3 | **100000** | **100000** |
| Outer fit 4 | **100000** | 3162.278 |
| Outer fit 5 | 316.228 | **100000** |

The all-training choices are **interior** to the expanded grid. Six-feature
selection CV MAE changes from .026816 at 100 to .026710 at 31.623, an apparent
.000106 gain on reused selection folds. Nested evaluation does not confirm an
improvement from the expanded search.

The selected alpha **still hits the upper boundary in 3/5 outer fits for each
configuration**; no fit chooses the lower boundary. The other two choices are
interior. The old grid chose its upper boundary, 1000, in all ten outer fits.
Thus widening the grid resolves neither tuning instability nor the lack of
strong predictive separation. At 100,000 the model is already almost a constant;
a still larger alpha could marginally reduce an inner score but would not
recover meaningful prediction spread.

If RMSE were used diagnostically to choose a fixed-alpha point on the all-training
curve, six features favor 100 (interior), while thirteen favor 100,000 (upper
boundary). These are **not** additional RMSE-tuned nested experiments. We keep
the predeclared MAE selection rule.

## Nested results against the mean baseline and saved Ridge

Each pooled result below has one out-of-fold prediction for every one of the
same 62 training players. Pooled RMSE is calculated across all errors and differs
from the mean of fold RMSEs.

| Procedure | MAE | RMSE | R² | Pooled prediction SD |
|---|---:|---:|---:|---:|
| Fold-fitted training mean | .027083 | .034708 | −.006812 | .000940 |
| Six features, original-grid tuning | .026970 | .034622 | −.001832 | .001165 |
| Six features, wide-grid tuning | .027113 | .034664 | −.004266 | .001359 |
| Thirteen features, original-grid tuning | .027013 | .034774 | −.010647 | .001281 |
| Thirteen features, wide-grid tuning | .027075 | .034772 | −.010525 | .001055 |

Widening the search changes six-feature MAE by **+.000142** and RMSE by
**+.000042**. For thirteen features, changes are **+.000062 MAE** and
**−.000002 RMSE**. None is a meaningful improvement. Against the mean baseline,
the wider six-feature model is .000030 worse in MAE and .000044 better in RMSE;
the wider thirteen-feature model is .000007 better in MAE and .000064 worse in
RMSE. This is essentially mean-baseline performance, with tradeoffs between
criteria rather than a convincing improvement.

The observed training-outcome SD is **.034590**. Pooled OOF prediction SD also
includes differences between the five fitted intercepts: even the constant
within-fold mean baseline has pooled SD .000940. Do not interpret that baseline
spread as player-specific predictive information. Likewise, the six-feature
wide-grid pooled spread can be larger than its old-grid spread even though three
wide-grid fits are nearly constant, because the other selected penalties and
fold means differ. The path plots show within-fold spread separately.

The original-grid nested predictions and metrics reproduce the saved ablation
within absolute **1e-12**. This validates comparability, not a new performance
claim. Initial saved model metrics and ablation holdout metrics are read only and
retained in `metrics.json` under historical context. Their test MAE/RMSE/R² concern
125 different observations and must not be compared directly to the new training
OOF scores as evidence of improvement. No holdout is re-evaluated.

## Fold-level variation

Values are **wide-grid minus original-grid** errors; negative favors the wider
search. Both configurations use the same outer fold numbers.

| Outer fold | Validation players | Six MAE change | Six RMSE change | Thirteen MAE change | Thirteen RMSE change |
|---|---:|---:|---:|---:|---:|
| 1 | 13 | +.000212 | +.000107 | +.000214 | +.000100 |
| 2 | 13 | .000000 | .000000 | .000000 | .000000 |
| 3 | 12 | +.000176 | +.000228 | +.000301 | +.000170 |
| 4 | 12 | +.000125 | +.000006 | +.000012 | −.000255 |
| 5 | 12 | +.000205 | −.000054 | −.000226 | +.000093 |

Six-feature MAE improves in **0/5**, worsens in four and ties in one; RMSE
improves in one, worsens in three and ties in one. Thirteen-feature MAE and RMSE
each improve in one, worsen in three and tie in one. Mean paired fold changes
are +.000144 MAE / +.000057 RMSE for six features, and +.000060 / +.000022 for
thirteen. These differ from pooled changes because of unequal fold sizes and
RMSE's nonlinearity.

Fold composition has a much larger effect than search range: wide-grid outer
MAEs range approximately .0214–.0353. Across folds, MAE SD is .006510 for six
features and .006390 for thirteen; RMSE SD is .008372 and .008405. The paired
MAE-change SD is .000087 for six and .000206 for thirteen. These are descriptive
statistics, not confidence intervals or independent replications. The paired
CSV also includes each wide-grid model's fold differences from the mean baseline.

## Interpretation and limitations

There is **no demonstrated excessive-regularization problem that can be fixed
simply by lowering alpha**. Lowering the penalty does widen predictions, as
expected, but weak-penalty validation error gets worse while training fit gets
better. That pattern supports a variance/overfitting explanation for why CV
prefers heavy shrinkage. Conversely, extremely heavy shrinkage suppresses all
player differences and approaches the mean; that alone does not prove useful
signal is absent in the underlying sport.

The stronger conclusion supported here is limited: these fixed linear feature
sets do not reliably distinguish next-season provisional outcomes in this
62-player training sample. Single-year training, correlated counts and batting
summaries, provisional target measurement problems, eligibility selection and
small folds could all limit the detectable signal. A different model, more
training seasons or a separately approved target could change the result.

This is explicitly **exploratory repeated use of the same training cohort**.
Although each nested fit respects its outer boundary, choosing a wider grid was
motivated by earlier results on these same players; this is not fresh confirmatory
evidence. No repeated shuffled/grouped partitions, training-sample bootstrap or
new temporal validation were added. Outer fits overlap; the spread across folds
and shaded path bands should not be treated as independent-sample uncertainty.
With thirteen correlated predictors and only 39–40 players in an inner fitting
subset, alpha estimates can be unstable. The optimum is grid- and criterion-
dependent, and a boundary choice is not proof of a well-determined optimum.

Retain the original benchmark and the previous experiment unchanged. Do not
replace the model merely to obtain wider predictions, and do not adopt 31.623
from the reused all-training curve as a proven improvement. More independent
training seasons and validation under an approved target are more informative
next steps than expanding the grid further to make predictions approach the mean.

## Reproduction and artifacts

With the existing locked dependencies installed, run from the repository root:

```bash
python scripts/ridge_regularization_sensitivity.py
pytest
ruff check .
```

No network or additional dependencies are required. Fresh-checkout runs regenerate
features from shared source inputs. Saved prior experiments are optional read-only
comparators; when present, original-grid nested predictions and fold assignments
are checked against them. Outputs go only to ignored
**`data/processed/ridge_regularization_sensitivity_v1/`**:

| File | Contents |
|---|---|
| `metrics.json` | Design, nested metrics, selected alphas/boundaries, fold variation, historical comparisons and provenance |
| `alpha_fold_metrics.csv` | Every inner/outer alpha/fold fit's training/validation error, coefficient norms and prediction variance |
| `alpha_summary.csv` | Mean/SD fixed-alpha fold diagnostics plus pooled validation metrics |
| `coefficients.csv` | Individual standardized coefficients for every inner and fixed-alpha outer fit |
| `fixed_alpha_predictions.csv` | Outer validation predictions across the full alpha path; training players only |
| `nested_predictions.csv`, `nested_fold_metrics.csv` | Wide-grid, original-grid and mean-baseline comparisons |
| `paired_fold_differences.csv` | Wide-grid paired changes against old-grid tuning and baseline |
| `fold_assignments.csv` | Shared outer and inner fit/validation player IDs and feature seasons |
| `full_training_path.csv` | Resubstitution error, coefficient norm and spread on fits of all 62 training players; not generalization estimates |
| `features_batted.csv`, `feature_spot_checks.csv`, `batted_source_anomalies.csv` | Separate regenerated feature inputs and inherited review diagnostics |
| `regularization_paths.png`, `.svg` | Fit/validation errors, coefficient shrinkage and within-fold prediction spread |
| `nested_comparison.png`, `.svg` | Paired outer-fold scores for baseline and both configurations/grids |
| `preserved_inputs.json` | SHA-256 preservation manifest for pre-existing files |

Provenance records source/team/study hashes, code hashes, Git revision/dirty state
and library versions. Scientific results are deterministic; image/session metadata
may differ on rerun. All prior processed outputs outside this new experiment are
protected by before/after hashes along with tracked inputs. Initial execution
verified **155 pre-existing files unchanged**, including datasets, original labels,
splits, saved model results and the committed wOBA audit and ablation. Nothing
was staged, committed or pushed; PR #13 was not modified.

Tests cover grid validity and original values, criterion/tie handling, coefficient
shrinkage versus training squared error, fold-local imputation, player overlap
rejection, invariance to changed test/excluded/unlabeled data, fold-fitted mean
correctness, identical paired outer players and reproduction of saved old-grid
nested results. Every generated prediction concerns training feature season 2023.

Final validation: **160 pytest tests passed**, **Ruff passed**, all **155**
pre-existing file hashes remained unchanged, and all **19** generated artifacts
(including the plotting cache) are ignored. Git contains only the four new
sensitivity implementation/test/report files, with nothing staged.

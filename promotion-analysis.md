# Next-season MLB participation

Issue: [#5](https://github.com/AnishAwasthi/callup/issues/5)

Of 926 Triple-A player-seasons, 443 (47.84%) have next-season MLB batting appearances, and 239 (25.81%) meet the 75-PA threshold and have a usable **preliminary** wOBA label. The 926 rows represent 664 distinct people. This analysis includes nonparticipants and all split categories, including `excluded_overlap`.

## Reproduce

From the repository root, with Python 3.13:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/promotion_analysis.py
python scripts/performance_analysis.py
ruff check .
pytest
python scripts/offline_example.py
```

On Windows activate with `.venv\Scripts\Activate.ps1`. Matplotlib is the added plotting dependency, pinned with its dependencies in the lockfile. The script uses a noninteractive plotting backend and no network requests. If the default font-cache directory is unwritable, set `MPLCONFIGDIR` to a writable temporary directory.

Inputs are `data/shared/processed/hitter_seasons.csv` and `reports/cohort_preparation.json`. The script validates the shared table contract, requires real data, checks all six preparation totals and both seasons, and verifies the input SHA-256 against the shared manifest before writing results. Optional `--input`, `--report`, and `--output` arguments allow alternate locations; the input must still match the frozen snapshot.

The snapshot is **shared-csv-v2**, based on callup-csv-v1 with no source refresh. The input SHA-256 is `5715a003e98e5c42c3eafab7bc32a36085da3fa5080f57c1a3db9a7a6c34cc36`; the starting repository commit is `a8f676a6dee27dffbf84316c962af65d222061aa`. Each run records the current Git commit, dirty status, script/input/report hashes, package versions and Python version in `analysis_metadata.json`. The script hash identifies uncommitted script changes as well.

## Sample and definitions

Each row is a unique `(player_id, season)` for a hitter with at least 150 official Triple-A PA in 2023 or 2024. Outcomes refer to 2024 or 2025 respectively. Names are display metadata, not keys. There are 262 players represented in both feature years; pooled unique-player counts must be recomputed, not added across seasons or outcome groups.

- `reached_mlb`: next-season MLB batting PA > 0, including returning MLB players.
- `outcome_eligible`: next-season MLB batting PA >= 75.
- `label_available`: eligible with reconstructible observed preliminary wOBA. This is distinct from eligibility even though their counts coincide in this snapshot.
- Exclusive `outcome_status` groups: `not_observed` (0 PA), `thin` (1–74 PA), and `eligible` (75+ PA).

All reported participation, eligibility and label rates use **player-season rows in the indicated group** as the denominator, not unique people. Conditional summaries for each flag's true and false groups are included. Empty groups have zero counts and blank rates. Missing outcomes and measurements remain blank; observed zero counts remain zero.

## Findings

| AAA season → MLB season | Rows | No MLB PA | 1–74 MLB PA | Any MLB PA | 75+ MLB PA | Usable provisional labels |
|---|---:|---:|---:|---:|---:|---:|
| 2023 → 2024 | 470 | 257 | 99 | 213 (45.32%) | 114 (24.26%) | 114 (24.26%) |
| 2024 → 2025 | 456 | 226 | 105 | 230 (50.44%) | 125 (27.41%) | 125 (27.41%) |
| All player-seasons | 926 | 483 | 204 | 443 (47.84%) | 239 (25.81%) | 239 (25.81%) |

Any MLB PA includes both thin and eligible rows; it must not be added to them. These results reproduce the current preparation report. Older cache summaries use the presence of an MLB statistics row instead of positive batting PA: three zero-PA rows explain the old 207 thin / 480 no-row totals versus the current 204 / 483.

The eligible group has a higher median Triple-A batting average and HR rate and a lower median K rate than nonparticipants in both seasons. BB rate and Triple-A playing time do not increase uniformly across participation categories. Pooled medians provide the following descriptive summary; the plots also separate seasons:

| Triple-A statistic | No MLB PA | 1–74 MLB PA | 75+ MLB PA |
|---|---:|---:|---:|
| PA | 299 | 341.5 | 318 |
| Batting average | .251 | .267 | .279 |
| BB / PA | 11.06% | 12.12% | 11.55% |
| K / PA | 22.73% | 22.40% | 20.87% |
| HR / PA | 2.75% | 3.03% | 3.46% |

Rates are calculated per player-season before summarizing, with H/AB for batting average and official AAA PA as the denominator for BB, K and HR rates. Walks include intentional walks. A zero denominator produces a blank rate. Means and quartiles accompany medians in the output; these are unweighted player-season summaries, not pooled event rates or adjusted estimates.

The six starter AAA count fields and AAA date bounds have no missing values in this snapshot. However, complete fields do not imply complete or accurate pitch coverage: the preparation report documents 464 AAA observed-versus-official PA discrepancies and 104 MLB discrepancies among participants. The 687 rows without labels (74.19%) retain blank wOBA. MLB date bounds are missing for all 483 nonparticipants, as expected. Missingness tables cover every non-key input field and the derived rates, with separate season/status/flag groups. Exit velocity and launch angle are not columns in this starter table; this report does not claim to audit their pitch-level missingness.

## Outputs and plots

All generated outputs go to ignored `data/processed/promotion/` and must stay out of Git:

- `participation_summary.csv`: `season`, `group_by`, `group`, `outcome_status`, `n_rows`, `n_players`, `n_reached`, `n_eligible`, `n_label_available`, `participation_rate`, `eligibility_rate`, `label_rate`.
- `missing_values.csv`: `season`, `group_by`, `group`, `field`, `n_missing`, `n_total`, `missing_rate`.
- `aaa_comparisons.csv`: group keys, `field`, `n_total`, `n_observed`, `n_missing`, `mean`, `median`, `q25`, `q75`.
- `analysis_metadata.json`: source/version identifiers, environment, validated totals and denominator definition.
- `participation_counts.png`: nested counts by season, explicitly labeled as nonadditive.
- `aaa_playing_time.png`: AAA PA distributions in exclusive outcome groups, by season. Boxes show the 25th–75th percentiles, the line is the median, and whiskers extend to observations within 1.5 IQR; points beyond are outliers.
- `aaa_hitting_rates.png`: median AAA batting average, BB, K and HR rates by outcome group and season.
- `missingness.png`: missingness in starter AAA counts/date bounds and MLB outcome/date fields by season and exclusive outcome group.

A blank `season` in summary tables denotes all seasons, not a missing source year. Rates are fractions from 0 to 1. `group_by=all` is the cohort summary. Status categories partition rows, while the three flag comparisons and all-row summaries overlap; never add counts across different `group_by` values. `n_players` counts distinct IDs within each specific group, so a person can be counted in different outcome groups across years.

## Spot checks and validation

Five source-row checks span both years and all exclusive outcome groups. These check transformations against the frozen input, not against an independent baseball data source:

| Player ID / season | Name | AAA H / AB | Computed average | Next MLB PA | Status / label |
|---|---|---|---:|---:|---|
| 501659 / 2023 | Abraham Almonte | 27 / 134 | .201493 | 0 | not_observed / blank |
| 542364 / 2023 | Rafael Ortega | 64 / 281 | .227758 | 17 | thin / blank |
| 572138 / 2023 | Jon Singleton | 86 / 298 | .288591 | 405 | eligible / available |
| 493329 / 2024 | Yuli Gurriel | 85 / 291 | .292096 | 40 | thin / blank |
| 578428 / 2024 | Jose Iglesias | 45 / 165 | .272727 | 343 | eligible / available |

Synthetic tests cover repeated people across years, eligible rows without available labels, empty groups, zero denominators versus observed zero rates, missing-value serialization, and rejection of preparation-total mismatches. No synthetic rows enter the final analysis.

## Limitations

Participation means observed next-season batting appearances, not first-ever promotion or a permanent career outcome. Returning MLB veterans are included. The descriptive population is all eligible AAA hitter-seasons, not specifically MLB-naive prospects. Full-season AAA playing time can reflect movement between levels and is not a direct measure of talent.

The outcome values are provisional observed wOBA reconstructed from served Savant values, not xwOBA or independently verified official wOBA. Eligibility and label availability must remain separate concepts. Missing outcomes cannot be inferred to equal poor performance. No source refresh, outcome correction, selection correction or causal claim is included. Group differences can reflect age, prior MLB experience, roster needs, health, scouting and other unmeasured factors. Repeated players also mean rows are not statistically independent. These summaries provide context for later model evaluation; they do not establish why a player appeared in MLB.

## Extension: which Triple-A statistics relate to next-season MLB performance?

**Walk rate has the strongest pooled association among the ten available starter statistics, but the relationship is weak. The training-selected single-stat model does not outperform the mean baseline on the separate test season.** This exploratory supplement addresses performance conditional on having a label; it does not predict participation or replace the team's main modeling assignment.

### Scope and measures

Use all **239 labeled player-seasons from 207 distinct players** for the descriptive associations: 114 rows from the 2023 AAA season and 125 from 2024. The target is the existing next-season `mlb_woba`. OPS, xOPS and xwOBA are not prepared labels in the shared table, and the shared pitch export does not include expected-wOBA event values. No new outcome has been inferred or substituted. xwOBA uses contact-quality information and differs from observed wOBA ([MLB definition](https://www.mlb.com/glossary/statcast/expected-woba)).

The ten prespecified AAA candidates are PA, H, AB, BB, K and HR counts, plus H/AB, BB/PA, K/PA and HR/PA. Rates use the definitions above. This is a comparison of the starter statistics, not every possible baseball measure: exit velocity, hard-hit rate, contact rate, park adjustments and other teammates' feature outputs are not yet incorporated. There are no missing candidate features among these 239 rows. Outcomes are never imputed.

### Relationships across the labeled sample

Pearson correlation measures a linear relationship; Spearman correlation compares ranks. We report both overall and separately by feature season. The ranking uses absolute pooled Pearson correlation, preserving the sign in the table. A positive value means higher AAA statistics tend to accompany higher next-season MLB wOBA within this selected sample.

| AAA statistic | Pearson r | 95% player-bootstrap interval | Spearman rho |
|---|---:|---:|---:|
| Walk rate | .147 | [.034, .264] | .126 |
| Home-run rate | .077 | [-.055, .209] | .101 |
| Walks | .070 | [-.032, .184] | .079 |
| Home runs | .058 | [-.076, .196] | .107 |
| Strikeouts | -.051 | [-.185, .076] | -.004 |
| At-bats | -.043 | [-.158, .078] | .004 |
| Batting average | .041 | [-.094, .173] | .033 |
| Hits | -.032 | [-.152, .089] | .015 |
| Strikeout rate | -.029 | [-.157, .097] | -.035 |
| Plate appearances | -.028 | [-.144, .093] | .015 |

For walk rate, r is .063 in the 2023 cohort and .205 in 2024. Its pooled r squared is about 2.2%, an in-sample one-variable linear association, **not** a validated prediction score. Its uncertainty interval excludes zero before any multiple-comparison adjustment, but these are exploratory comparisons of ten correlated statistics. The intervals are not simultaneous, and choosing the largest observed correlation creates selection optimism; do not present this as a confirmed discovery.

The 95% percentile intervals use 1,000 bootstrap draws of distinct player IDs, carrying all of a sampled player's season rows together. This accounts for repeated players while retaining equal weighting of player-season rows in the point estimates. Per-season intervals use the same procedure within the season. Correlations use only complete feature/outcome pairs and report paired rows, distinct people, missing pairs and valid bootstrap draws. A constant variable or fewer than three pairs yields a blank correlation. No p-value-based selection is performed.

### Prediction on a separate season

The fixed project split is preserved before label filtering:

- Training: 62 labeled 2023 rows, all distinct players.
- Test: 125 labeled 2024 rows, all distinct players, with no training-player overlap.
- Excluded from prediction fitting and scoring: 52 labeled 2023 rows whose players appear anywhere in the 2024 cohort. They remain in the descriptive 239-row analysis.

Each candidate gets a separate linear regression with an intercept. Five player-grouped training folds produce out-of-fold predictions; candidates are ranked by the RMSE across all 62 out-of-fold predictions, with feature-name ordering for exact ties. Median imputation and standardization are fitted inside a scikit-learn Pipeline using each training fold only. No future MLB fields, labels, IDs, split indicators or coverage diagnostics enter the predictors. The mean baseline uses the training-fold mean during validation, then the full training mean for testing. Models are unweighted by MLB PA, and predictions are not clipped.

The script selects and fits the model before computing the pooled descriptive correlations. The test outcomes and pooled association ranking never choose the predictor. **Total AAA hits** wins training validation narrowly: RMSE .03444 versus .03471 for the mean baseline. Home runs are nearly tied at .03446; this is not a stable separation. Walk-rate model CV RMSE is .03504, worse than the baseline. The selected hits model and baseline are then evaluated once on the 125 test rows:

| Model | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|
| Training mean wOBA | .03511 | .04668 | -.078 |
| Training-selected AAA hits model | .03550 | .04756 | -.119 |

RMSE is in wOBA units, and lower is better. The hits model's error is slightly higher. The paired test-player bootstrap interval for its RMSE minus baseline RMSE is **[-.00011, .00189]**, with point estimate +.00088. This interval is conditional on the fitted model and does not include training or model-selection uncertainty. Negative test R² means neither fitted prediction beats the test set's own mean as a retrospective reference; that test mean was not used to train either model.

The practical conclusion is **weak descriptive association and no demonstrated predictive improvement for the training-selected single-stat model**. This does not show that every other statistic or a richer model cannot predict performance. The sample is small and selected for sufficient MLB playing time, outcomes remain provisional, raw counts mix opportunity with performance, and the population changes across seasons. Results do not generalize automatically to the 687 rows without outcomes or to future prospects. Because this report also inspects all-cohort associations, subsequent feature changes would require fresh validation; the current test set must not become a tuning set.

### Reproduce and review the extension

Run `python scripts/performance_analysis.py` after installing the updated `requirements-lock.txt`. New direct dependencies are scikit-learn and SciPy; their versions and transitive dependencies are pinned. The default bootstrap count is 1,000 and seed is 20261029; `--bootstrap`, `--seed` and `--output` are supported. The same frozen input hash and preparation totals are verified.

Generated files are under ignored `data/processed/promotion/performance/`:

- `correlations.csv`: all ten features, pooled and by season, Pearson/Spearman estimates and intervals, sample counts and absolute Pearson ranks. Blank season means pooled.
- `training_cv.csv` and `training_cv_predictions.csv`: all candidate scores, baseline scores, and fold-level out-of-fold predictions. These are selection scores, not unbiased estimates after selection.
- `test_predictions.csv`: predictions for the training-selected model and baseline only, with player/season keys, outcomes, split and data/code version identifiers.
- `model_metrics.json`: train/test/exclusion counts, feature list, missingness, selection/preprocessing settings, test metrics, paired uncertainty interval, versions and hashes.
- `woba_correlations.png`: pooled association ranking with bootstrap intervals.
- `woba_training_comparison.png`: training-only candidate comparison.

Tests verify that changing test outcomes or excluded rows does not affect model selection or test predictions, reject outcome/identity predictors, reject full-cohort train/test overlap even on unlabeled rows, preserve player groups within validation folds, handle missing/constant correlation inputs, and refuse missing training outcomes. All 71 repository tests pass locally, along with lint and the original offline example. Both analysis scripts are included in the GitHub checks workflow; hosted checks have not run yet.

## Follow-up: do other MLB outcomes correlate more strongly?

Yes for particular aspects of hitting; no improvement appears for OPS as a broad batting summary. The comparison below retains exactly the same 239 player-seasons and ten starter AAA predictors. Each row shows the largest absolute pooled Pearson correlation among those ten predictors; this is exploratory screening, not a test-set prediction result.

| Next-season MLB outcome | Most related AAA statistic | Pearson r |
|---|---|---:|
| wOBA (existing preliminary outcome) | Walk rate | .147 |
| OPS | Home-run rate | .133 |
| On-base percentage | Walk rate | .270 |
| Slugging percentage | Home-run rate | .249 |
| Batting average | Strikeout rate | -.162 |
| Isolated power (SLG minus AVG) | Home-run rate | .423 |
| Strikeout rate | Strikeout rate | .686 |
| Walk rate | Walk rate | .510 |
| Home-run rate | Home-run rate | .432 |

OPS combines OBP and SLG ([MLB](https://www.mlb.com/glossary/standard-stats/on-base-plus-slugging)). The alternatives therefore suggest that specific skills translate more consistently than the broad outcomes checked here. Strikeout rate is the strongest relationship, but measures strikeout tendency rather than overall offensive value; a higher rate is not better performance. OBP and SLG summarize reaching base and hit production respectively, while ISO isolates extra-base production. None includes defense or baserunning. A larger correlation alone is not a reason to replace the project's agreed wOBA outcome.

These supplemental labels were **newly reconstructed from observed terminal events** in the frozen MLB 2024/2025 pitch files; they were not existing prepared labels. They remain separate from the central cohort and are provisional, not independently verified official statistics. Source hashes, one terminal event per `(game_pk, at_bat_number)`, and event years are checked. All 239 terminal-event totals match the starter table, and reconstructed wOBA matches its existing values within floating-point tolerance. Unknown event types or duplicate terminal keys stop the script.

Counts use one batter appearance per terminal event, including double-play events. `truncated_pa` is excluded from completed PA and AB. Walks include intentional walks. AB consists of hits and explicitly classified batter-at-bat outcomes, including errors and fielder's choices; walks, HBP, sacrifice flies/bunts and catcher interference are excluded. Catcher interference counts toward completed PA. Formulas are H/AB for AVG; total bases/AB for SLG ([MLB](https://www.mlb.com/glossary/standard-stats/slugging-percentage)); (H+BB+HBP)/(AB+BB+HBP+SF) for OBP ([MLB](https://www.mlb.com/glossary/standard-stats/on-base-percentage)); OBP+SLG for OPS; SLG-AVG for ISO. K, BB and HR rates divide by observed completed PA. Zero denominators remain blank.

After excluding truncated records, observed completed PA matches official cached PA in 238 of these 239 rows. Trey Sweeney's 2024 AAA / 2025 MLB row has 327 observed completed PA versus 326 official PA. It is retained and flagged; the discrepancy is not silently corrected. Agreement in counts does not establish independent accuracy of the event classifications or official batting rates.

The patterns are present in both seasons: AAA BB rate versus MLB OBP has r=.181/.333 in the 2023/2024 feature cohorts; AAA HR rate versus MLB ISO has r=.366/.485; AAA K rate versus MLB K rate has r=.696/.680. The full output also reports Spearman correlations. Screening nine outcomes against ten features increases selection optimism; no multiple-comparison-adjusted claims or predictive validation are made here. Correlations reflect a selected sample with repeated players, and changing outcomes after inspecting results would require new validation.

Run `python scripts/compare_outcomes.py`. Generated outputs under ignored `data/processed/promotion/alternative_outcomes/` include the complete correlation table, strongest associations, reconstructed numerator/denominator counts and outcomes, provenance/coverage metadata, and `outcome_correlations.png`. Unit tests check AB/PA/OBP denominators, truncated events, double-play treatment, zero denominators and rejection of unknown/duplicate events. The full suite now has **74 passing tests**; the third script is also included in GitHub checks.

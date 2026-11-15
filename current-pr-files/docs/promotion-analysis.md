# Next-season MLB participation

Issue: [#5](https://github.com/AnishAwasthi/callup/issues/5)

Of 926 Triple-A player-seasons, 443 (47.84%) have next-season MLB batting appearances, and 239 (25.81%) meet the 75-PA threshold and have a usable **preliminary** wOBA label. The 926 rows represent 664 distinct people. This analysis includes nonparticipants and all split categories, including `excluded_overlap`.

## Reproduce

Install Git and Python 3.13. Start with a clone of the repository and check out **this PR's branch**, since the scripts may not yet be on `main`. Replace `PR_NUMBER` below with the number in this pull request's URL (not the issue number). This checkout method also works for a PR submitted from a fork.

```sh
git clone https://github.com/AnishAwasthi/callup.git
cd callup
git fetch origin pull/PR_NUMBER/head:review-issue-5
git switch review-issue-5
```

On macOS/Linux, run from the repository root:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-promotion.txt
python scripts/promotion_analysis.py
python -m ruff check .
python -m pytest
python scripts/offline_example.py
```

On Windows PowerShell, after the same Git checkout:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-promotion.txt
.venv\Scripts\python.exe scripts/promotion_analysis.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts/offline_example.py
```

No separate data download, API key, notebook state or network access is required for the analysis. Git retrieves the frozen inputs; the package installation needs network access. `requirements-promotion.txt` includes the existing locked environment plus pinned Matplotlib dependencies. The script uses a noninteractive plotting backend. If the default font-cache directory is unwritable, set `MPLCONFIGDIR` to a writable temporary directory.

Successful execution writes three CSV tables, four PNG plots and `analysis_metadata.json` under `data/processed/promotion/`, then prints the checked counts. Expect 926 rows, 664 distinct players, 443 participants, 239 eligible rows and 239 preliminary labels. Re-running the same command replaces these generated files. They are ignored by Git and must not be uploaded. Source-count inconsistencies or a mismatched input hash cause an error rather than silently changing the sample.

The scope of this PR is the descriptive participation analysis. Correlation analyses and performance models are reserved for a follow-up PR.

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

## Fresh-environment verification

Verified on November 12, 2026 using a separate checkout and a newly created Python 3.13 environment installed solely from `requirements-promotion.txt`. Dependency checks, lint, all 66 tests and the offline example passed. The three generated CSV tables and four PNG plots matched the previous verified outputs byte for byte. GitHub-hosted checks will run after upload; they have not been claimed as passing here.

## Limitations

Participation means observed next-season batting appearances, not first-ever promotion or a permanent career outcome. Returning MLB veterans are included. The descriptive population is all eligible AAA hitter-seasons, not specifically MLB-naive prospects. Full-season AAA playing time can reflect movement between levels and is not a direct measure of talent.

The outcome values are provisional observed wOBA reconstructed from served Savant values, not xwOBA or independently verified official wOBA. Eligibility and label availability must remain separate concepts. Missing outcomes cannot be inferred to equal poor performance. No source refresh, outcome correction, selection correction or causal claim is included. Group differences can reflect age, prior MLB experience, roster needs, health, scouting and other unmeasured factors. Repeated players also mean rows are not statistically independent. These summaries provide context for later model evaluation; they do not establish why a player appeared in MLB.

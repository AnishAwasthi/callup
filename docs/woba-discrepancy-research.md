# PRELIMINARY — Are Callup's wOBA differences meaningful?

**Yes, the differences are practically meaningful in this selected sample.**
They largely reflect a target-definition mismatch plus incomplete served
denominator fields, rather than missing season totals. Callup reproduces its
frozen served-event ratio, but that ratio is neither standard FanGraphs wOBA
nor FanGraphs' Basic wOBA approximation. If the intended target is standard
seasonal wOBA, these findings warrant proposing a versioned revision to Anish.
They do not authorize replacing labels or rerunning models now.

Checked November 5, 2026, America/Los_Angeles (November 6 UTC). This audit reads
existing labels, split, and model metrics; it does not fit models or overwrite
any existing outcomes, predictions, metrics, or five-player validation outputs.

## What is actually calculated?

`scripts/prepare_analysis.py`, lines 78–104, numerically parses the served fields
and selects rows where `events` is nonmissing. For each player/outcome season:

`prepared = sum(terminal.woba_value) / sum(terminal.woba_denom.fillna(0))`.

The code does not construct seasonal weights. Pandas skips missing numerator
values; denominators missing on an observed event become zero. An available
label requires cached official MLB PA ≥75, a positive denominator, and no
missing numerator on a positive-denominator row. It does not reject missing
denominators, numerator contributions on zero-denominator rows, or absent
events. A completely absent event contributes nothing. `observed_pa` counts
every nonmissing event, including `truncated_pa`; date bounds use all player
pitch rows. The preparation loop selects year-named shards; upstream archive
reports document regular-season checks, rather than a separate game-type
filter inside this calculation. Original global duplicate-key checks are
documented; this audit also rejects duplicate keys for selected players.

In the ten audited rows, served weights include BB/HBP .7, 1B .9, 2B 1.25,
3B 1.6, HR 2.0, errors/selected fielder's choices .9, IBB .4, and catcher
interference .7. Bunts have .2 or .9 with zero denominator; one strikeout has
.7. Other outs generally have zero numerator. Ordinary contributing events
generally have denominator 1, but 15 such fields are missing in this sample
(including 12 outs, a walk, a single, and a home run). This is an empirical
inventory of served fields, not a universal event-weight specification.

## Standard versus Basic wOBA

Standard FanGraphs numerator is
`wBB*(BB-IBB) + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR`;
denominator is `AB + BB - IBB + SF + HBP`. Errors and fielder's choices count
as at-bats with no numerator credit; SH, IBB, and interference are excluded.
[FanGraphs definition](https://library.fangraphs.com/offense/woba/).

| Formula | BB coefficient | HBP | 1B | 2B | 3B | HR | Denominator |
|---|---:|---:|---:|---:|---:|---:|---|
| Standard 2024 | .689 | .720 | .882 | 1.254 | 1.590 | 2.050 | AB+BB−IBB+SF+HBP |
| Standard 2025 | .691 | .722 | .882 | 1.252 | 1.584 | 2.037 | AB+BB−IBB+SF+HBP |
| Basic (2015 publication) | .700 | .700 | .900 | 1.250 | 1.600 | 2.000 | PA |

Seasonal weights come from [FanGraphs Guts](https://www.fangraphs.com/tools/guts?type=cn).
They are displayed to three decimals; no additional wOBAScale multiplication
belongs in the wOBA ratio.

Jeff Zimmerman's [Basic wOBA Equation, May 14, 2015](https://blogs.fangraphs.com/instagraphs/basic-woba-equation/)
uses `.7*(BB+HBP)+.9*1B+1.25*2B+1.6*3B+2*HR`, divided by PA. We implement it
literally: BB includes IBB, and total PA includes SH/interference. FanGraphs
describes Basic as an approximation, not its official player-page statistic.
Callup shares the six coefficients but adds other served credits and uses a
different denominator. Calling the current target simply Basic wOBA would
therefore also be inaccurate.

## Independent references and selection

The original five published wOBA records and their October retrieval metadata
remain unchanged in `validation/references/fangraphs_woba_pilot.json`.
`validation/references/fangraphs_woba_audit.json` adds five independent records,
ten independently transcribed Standard-table component rows, formula versions,
URLs, precision, and the November retrieval session metadata. Sources were
web-tool rendered/cached pages; origin freshness is unknown. The capture is
curated facts, not raw HTML. Player identity uses the documented manual
MLBAM/Savant-to-FanGraphs match, season, team, and PA.

The extension deliberately selects Schneider and Palacios as training PA-gap
cases, both years of Meadows for a repeated-player comparison, and Lukes 2025
to extend his earlier trace. There are 10 player-seasons / 8 players: six 2024
outcomes, four 2025 outcomes; three train, four test, three excluded-overlap.
These are nonrandom diagnostic selections, including repeated people. There
is no population-level statistical-significance claim or p-value.

All independent values below are full MLB regular-season observed wOBA, not
xwOBA, projections, postseason, or a local reconstruction. Each player has one
MLB team in the relevant season; qualification filters were not applied.

## PRELIMINARY comparison

Basic and standard diagnostic columns use internal archived event counts;
**only the published column is an independently published wOBA reference**.

| Player / MLB season | Split | Prepared | Basic diagnostic | Seasonal diagnostic | Published | Prepared − published |
|---|---|---:|---:|---:|---:|---:|
| Nathan Lukes / 2024 | excluded | .363636 | .347253 | .351101 | .351 | +.012636 |
| Joey Ortiz / 2024 | train | .330336 | .318885 | .318720 | .319 | +.011336 |
| Bligh Madris / 2024 | excluded | .310000 | .300667 | .301270 | .301 | +.009000 |
| Junior Caminero / 2025 | test | .372965 | .357121 | .356410 | .357 | +.015965 |
| James Wood / 2025 | test | .364307 | .358055 | .352693 | .353 | +.011307 |
| Davis Schneider / 2024 | train | .279757 | .278524 | .277478 | .277 | +.002757 |
| Richie Palacios / 2024 | train | .313419 | .307278 | .302840 | .303 | +.010419 |
| Parker Meadows / 2024 | excluded | .330743 | .321812 | .321148 | .321 | +.009743 |
| Parker Meadows / 2025 | test | .283962 | .279343 | .276606 | .277 | +.006962 |
| Nathan Lukes / 2025 | test | .332512 | .315868 | .316858 | .317 | +.015512 |

New source pages: [Schneider](https://www.fangraphs.com/players/davis-schneider/23565/stats/batting),
[Palacios](https://www.fangraphs.com/players/richie-palacios/24589/stats/batting),
[Meadows](https://www.fangraphs.com/players/parker-meadows/23800/stats/batting),
[Lukes](https://www.fangraphs.com/players/nathan-lukes/18123/stats/batting).
Original source links are preserved in the pilot fixture and
[pilot note](outcome-validation.md).

The original five component totals are reproduced as:

| Player | Prepared N / D | Seasonal diagnostic N / D | Missing out denominators |
|---|---:|---:|---:|
| Lukes 2024 | 32 / 88 | 31.248 / 89 | 1 |
| Ortiz 2024 | 167.15 / 506 | 161.910 / 508 | 2 |
| Madris 2024 | 23.25 / 75 | 22.294 / 74 | 0 |
| Caminero 2025 | 242.80 / 651 | 232.379 / 652 | 1 |
| Wood 2025 | 247 / 678 | 240.184 / 681 | 3 |

For an additive explanation, first remove nonstandard numerator credits while
holding the served denominator fixed, then correct the denominator, then change
the six fixed coefficients to seasonal ones. Attribution depends on this order.
The following columns sum to prepared minus published:

| Player | Numerator credits | Denominator | Coefficients | Residual |
|---|---:|---:|---:|---:|
| Lukes 2024 | +.004545 | +.004035 | +.003955 | +.000101 |
| Ortiz 2024 | +.008300 | +.001268 | +.002047 | −.000280 |
| Madris 2024 | +.009333 | −.004063 | +.003459 | +.000270 |
| Caminero 2025 | +.015822 | +.000548 | +.000186 | −.000590 |
| Wood 2025 | +.008702 | +.001567 | +.001345 | −.000307 |

Confirmed numerator differences in these five: Lukes bunts +.4; Ortiz errors
+.9, fielder's choices +2.7, bunts +.6; Madris interference +.7; Caminero errors
+7.2, fielder's choices +2.7, IBB +.4; Wood errors +2.7, IBB +3.2. Interference
also adds one served denominator for Madris; removing it raises the intermediate
ratio, explaining his negative denominator contribution. Missing out denominators
depress the served denominator for the other four.

## What is confirmed, and what remains unresolved?

All ten served numerator/denominator sums reproduce frozen labels. Archived
AB, PA excluding truncated rows, BB, IBB, hits by type, HBP, SF, and SH match
the independently transcribed season counts exactly. Original Ortiz/Wood PA
excesses are zero-contribution truncated events. There is no aggregate evidence
of missing season components here, although offsetting game-level errors cannot
be ruled out. Individual anomalies retain game/date/PA/pitch keys.

The extension confirms a missing walk/strikeout denominator for Schneider
(2024-05-23, game 746474, PA 35/17); missing single/HR denominators for Lukes
(2025-08-18 game 776694 PA 10; 2025-09-16 game 776305 PA 34); and a strikeout
with .7 served numerator for Meadows (2025-09-13 game 776347 PA 85). These are
observations of fields, not independently verified diagnoses of scorer/feed causes.

Nine seasonal diagnostics are within ±.0005 of published wOBA. Caminero's
−.000590 residual is outside reference rounding alone but within a conditional
bound allowing ±.0005 on each displayed coefficient (about .000155 additional
uncertainty for him). Higher-precision coefficients could explain it; that is
a hypothesis, not confirmation. Later scoring corrections or differing source
definitions remain possible. Full game-level reconciliation is outstanding.

## Practical magnitude and recommendation

| Selection | n | Mean signed gap | Mean absolute gap |
|---|---:|---:|---:|
| Original pilot | 5 | +.012049 | .012049 |
| Extension | 5 | +.009078 | .009078 |
| All selected | 10 | +.010564 | .010564 |
| 2024 outcomes | 6 | +.009315 | .009315 |
| 2025 outcomes | 4 | +.012436 | .012436 |

All ten gaps are positive; median absolute gap is .010863, range .002757–.015965.
This is systematic within the selected sample, not proof of population-wide
bias or a statistically significant season difference. Seasonal diagnostics'
mean absolute residual is .000287; Basic diagnostics' is .001946.

For scale, the mean label gap is about 30% of baseline MAE (.035107), 23% of
baseline RMSE (.046677), and 110 times Ridge's tiny MAE advantage (.00009638).
These compare different samples/quantities and are not an error decomposition
of model scores. A common target shift can affect training and test together;
we cannot subtract this mean gap from MAE or predict which model would win on
revised labels. Models still evaluate the frozen provisional ratio.

Ask Anish to approve an explicit target definition and a separately versioned
reconciliation plan. If standard season wOBA is intended, prefer independent
season totals or tested seasonal reconstruction over raw served-field division.
Resolve missing denominators and unusual numerator fields, obtain precision
needed for residual cases, then validate more widely before approving changes.
If an approximation is intended instead, document its exact conventions and
name; the current ratio should not be described as either published FanGraphs
standard or literal Basic wOBA. Keep existing results preliminary and preserve
them for comparison; no label revision has been made.

## Reproduce without fetching sources or fitting models

With the existing locked dependencies installed, from the repository root:

```bash
python scripts/audit_woba.py
pytest tests/test_woba_audit.py
ruff check .
```

New inputs are the tracked audit reference JSON plus the unchanged pilot
fixture and shared dataset. Source fact records and formula coefficients are
frozen to their recorded capture sessions, not refreshed on rerun. Generated
files go only to ignored `data/processed/woba_audit/`: `comparisons.csv`,
`events.csv` (per-player event counts/N/D/missing fields), `anomalies.csv`
(investigation keys and expected diagnostic fields), `served_weights.csv`
(observed field combinations), and `audit.json` (summaries, formula versions,
source/input/code hashes, Git state, pandas version). Existing model metrics
are read only if present; they are never regenerated. Exact source records
remain distinct from all internal diagnostic columns. Unknown event categories
fail rather than receive invented weights. Review these artifacts before
expanding further or proposing any target change.

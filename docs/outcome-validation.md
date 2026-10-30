# Independent MLB wOBA validation: five-player pilot

Checked October 29, 2026, America/Los_Angeles (October 30 UTC). **All model
results and outcome labels remain preliminary.** This pilot compares exactly
five available labels; it does not validate the other 234 labels or approve
any outcome replacement. Labels, eligibility rules, split, and model outputs
are unchanged. Unresolved interpretations require Anish's review.

## Sources, matching, and scope

Independent reference values below were manually transcribed from FanGraphs'
player Dashboard MLB regular-season rows, using its explicitly labeled `wOBA`
column, not `xwOBA`, projections, minor leagues, spring training, or postseason.
Each selected player has one MLB team in that outcome season, so the team's
season row covers the player's full MLB season. No qualified-hitter restriction
was applied. The 75-PA threshold is our frozen cohort rule, not a wOBA denominator.

Names were checked on MLBAM-ID-bearing Baseball Savant player pages and matched
to FanGraphs names; season/team and published MLB PA were checked as supporting
evidence. This is a manual five-person mapping, not an automated ID crosswalk.
AAA feature seasons and Y+1 outcome years were checked against the unique
prepared keys and contract. The sample includes one training row, two test rows,
and two excluded-overlap rows. Excluded rows are valid for outcome verification
but remain excluded from model fitting/evaluation.

All reference values have **three decimal places**, with an assumed rounding
interval of ±0.0005. Retrieval metadata records `2026-10-30T01:48:11+00:00`
(October 29 locally), representing this browsing session. The web tool served
rendered/cached pages; this is not a claim of fresh origin-server downloads or
that we know when FanGraphs last revised these historical values. One direct
Wood URL attempt returned 403; its alternate stats URL subsequently resolved to
the batting page and exposed the required season row.

| Player | MLBAM / FanGraphs ID | AAA → MLB season | Split | Prepared | FanGraphs | Prepared − reference | Status |
|---|---|---|---|---:|---:|---:|---|
| Nathan Lukes | 664770 / 18123 | 2023 → 2024 | excluded_overlap | 0.363636364 | 0.351 | +0.012636364 | unresolved_definition_difference |
| Joey Ortiz | 687401 / 25493 | 2023 → 2024 | train | 0.330335968 | 0.319 | +0.011335968 | unresolved_definition_difference |
| Bligh Madris | 676632 / 20054 | 2023 → 2024 | excluded_overlap | 0.310000000 | 0.301 | +0.009000000 | unresolved_definition_difference |
| Junior Caminero | 691406 / 28163 | 2024 → 2025 | test | 0.372964670 | 0.357 | +0.015964670 | unresolved_definition_difference |
| James Wood | 695578 / 29518 | 2024 → 2025 | test | 0.364306785 | 0.353 | +0.011306785 | unresolved_definition_difference |

Reference and MLBAM identity pages, respectively:

- Nathan Lukes: [FanGraphs](https://www.fangraphs.com/players/nathan-lukes/18123/stats/batting), [Savant](https://baseballsavant.mlb.com/savant-player/nathan-lukes-664770).
- Joey Ortiz: [FanGraphs](https://www.fangraphs.com/players/joey-ortiz/25493/stats/batting), [Savant](https://baseballsavant.mlb.com/savant-player/joey-ortiz-687401).
- Bligh Madris: [FanGraphs](https://www.fangraphs.com/players/bligh-madris/20054/stats/batting), [Savant](https://baseballsavant.mlb.com/savant-player/bligh-madris-676632).
- Junior Caminero: [FanGraphs](https://www.fangraphs.com/players/junior-caminero/28163/stats/batting), [Savant](https://baseballsavant.mlb.com/savant-player/junior-caminero-691406).
- James Wood: [FanGraphs](https://www.fangraphs.com/players/james-wood/29518/stats/batting), [Savant](https://baseballsavant.mlb.com/savant-player/james-wood-695578).

## Findings and interpretation

Published FanGraphs PA equals frozen official PA for all five: Lukes 91, Ortiz
511, Madris 75, Caminero 653, Wood 689. Archive terminal-event counts are 91,
514, 75, 653, and 691 respectively. Ortiz has three `truncated_pa` events and
Wood two, each with zero numerator and denominator. Those events numerically
explain their excess terminal counts without changing the wOBA ratio. This does
not independently prove complete event coverage; game-level checking remains.

The archived numerator/denominator sums reproduce each prepared outcome's
stored components. These are **internal diagnostic calculations only**, never
independent reference values. Additional observed event conventions:

- Lukes: two sacrifice bunts contribute 0.4 numerator, zero denominator.
- Ortiz: one error contributes 0.9 numerator; three sacrifice bunts contribute
  0.6 numerator with zero denominator.
- Madris: one catcher-interference event contributes 0.7 numerator and one
  denominator. He is exactly at the 75 official-PA eligibility floor.
- Caminero: eight errors contribute 7.2 numerator; one intentional walk adds
  0.4 numerator with missing denominator, treated as zero by preparation.
- Wood: three errors contribute 2.7 numerator; eight intentional walks add
  3.2 numerator with missing denominators.

Preparation sums all nonmissing terminal `woba_value`s, even for events with
zero/missing denominators. Archived weights include BB/HBP 0.7, single 0.9,
double 1.25, triple 1.6, HR 2.0 in both years. In contrast, FanGraphs uses
year-specific weights and denominator `AB + BB - IBB + SF + HBP`; its numerator
uses unintentional walks, HBP, and hits, not a generic sum of these served event
values. [Definition](https://library.fangraphs.com/offense/woba/),
[seasonal weights](https://www.fangraphs.com/tools/guts?type=cn).

All original differences exceed rounding tolerance. A subsequent read-only
investigation found positive numerator credits on fielder's choices (Ortiz and
Caminero) and missing denominators on seven ordinary outs (Lukes 1, Ortiz 2,
Caminero 1, Wood 3). Applying standard event conventions and published seasonal
weights to archived counts gave diagnostic values 0.351101, 0.318720, 0.301270,
0.356410, and 0.352693, respectively. Four are within 0.0005 of the independent
reference; Caminero retains a -0.000590 residual, potentially affected by
coefficient/reference rounding. These internal calculations are not independent
references or approved replacement labels. They are not generated by the pilot
comparison script; reproducing that separate decomposition remains future work.

The comparison retains `unresolved_definition_difference` for the original
prepared labels. Standard target definition, event handling, and remaining
residuals still require scientific review with Anish. Later source corrections
and event coverage remain possible concerns; equal PA counts alone do not
settle them. No target-definition or outcome changes have been approved.

## Artifacts and reproduction

The small tracked fixture is
`validation/references/fangraphs_woba_pilot.json`. It is a byte-for-byte copy of
the original ignored reference JSON, including the five values, source/identity
URLs and IDs, seasons, precision, retrieval metadata, evidence, and notes. No
source values were refreshed. Its SHA-256 is
`53ea0bf329607fadef5e422a710dadb89f29520d65d8021a10988c9ecd2e5d30`.
It is a curated transcription, not a raw HTML snapshot or an automated crosswalk.

Generated artifacts remain ignored:

- `data/processed/outcome_validation_comparison.csv`: five comparisons,
  prepared components/date bounds, reference values/PA, signed and absolute
  differences, rounding tolerance, statuses, archived event summaries, input/
  archive/reference checksums, Git revision, dirty flag, and preliminary flag.

From a fresh clone containing this change and the existing tracked shared
dataset, install the locked dependencies and run from the project root:

```bash
python -m pip install -r requirements-lock.txt
python scripts/validate_outcomes.py
pytest tests/test_outcome_validation.py
ruff check .
```

No ignored reference input, extra dataset download, API account, or network
access is required to run validation after dependency installation. The default
reference path is resolved from the repository root. An explicit alternative
remains supported (relative paths are resolved from the working directory):

```bash
python scripts/validate_outcomes.py --references validation/references/fangraphs_woba_pilot.json
```

The script is offline: it joins the fixed five keys to the validated shared
table, checks availability and names, compares the independent transcription,
and recomputes archived components only as diagnostics. It writes only the
comparison CSV. It never trains models or rewrites predictions, metrics, or
source labels. The loader requires exactly the five unique pilot keys and the
recorded provenance fields, including a timezone-bearing retrieval timestamp.
Its checksum identifies exactly which transcription was used. Preserve the
original retrieval metadata; rerunning the script does not retrieve sources.
Scientific columns reproduce unchanged with the same frozen inputs; Git
revision/dirty status intentionally reflect the checkout used for each run.

The comparison helper leaves unavailable or mismatched references unresolved
with blank numeric reference/difference fields. Missing references must never
be replaced by a reconstruction from our archived pitches. Tests use synthetic
values and cover rounding, signed differences, identity/year/scope/source
rejection, unavailable values, invalid numeric values, and PA discrepancies.
Additional tests pin the original fixture checksum, check reference loading
and provenance requirements, and run the default/override CLI in an isolated
checkout layout without an ignored reference JSON to verify reproducibility.

Next steps require review before expansion: inspect independent component
totals and event-level explanations, reconcile seasonal weights, and discuss
unresolved differences with Anish. No conclusions about the other labels or
changes to the frozen target/split are authorized by this pilot.

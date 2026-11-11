# Full eligible-cohort wOBA reconciliation — diagnostic v1

All **239 eligible player-seasons** can be independently and unambiguously matched
to FanGraphs MLB regular-season batting records. FanGraphs independently published
wOBA and all eleven component totals were captured for every one. Internal event
counts agree exactly for **238/239**; the remaining discrepancy is an inherited
two-strike strikeout attributed to the terminal batter rather than the officially
charged batter. Standard seasonal reconstruction reduces mean absolute disagreement
from **.012265 to .000068**, without replacing any original outcomes.

This extends [the preliminary ten-season audit](woba-discrepancy-research.md).
That report, its scripts/tests and both earlier reference fixtures are preserved
byte for byte. The full-cohort findings below supersede its coverage limitation,
not its original retrieval evidence. Work began on `issue-4-ridge-model` at
`7697e3f3e2c3cd56c1bf4f2bb89b4ec3eb74e330`; the five preliminary audit files
were untracked. No commit, push, PR #13 change, model retraining, split change,
or target replacement was performed.

## Cohort and frozen contract

The input is `data/shared/processed/hitter_seasons.csv`, validated with
`callup.contract.load`, filtered only by `label_available=True`. The result is
239 player-seasons / **207 distinct MLBAM IDs**. There are 32 players represented
in both outcome years. A player-season remains the unit of each summary; repeated
players are not independent observations for inferential purposes.

| AAA feature season | MLB outcome season | Train | Excluded overlap | Test | Total |
|---|---|---:|---:|---:|---:|
| 2023 | 2024 | 62 | 52 | 0 | 114 |
| 2024 | 2025 | 0 | 0 | 125 | 125 |
| All | All | 62 | 52 | 125 | 239 |

The [contract](data-contract.md), [methodology](methodology.md), preparation code,
[prior validation](outcome-validation.md), tests and fixtures were read before
implementation. The 926-row parent cohort requires ≥150 AAA PA; the outcome floor
is ≥75 official next-season MLB PA. Eligibility and reconstructible label
availability are distinct concepts even though all 239 eligible rows have labels
in this snapshot. The frozen split is defined on the full parent cohort before
filtering: all 2024 feature rows are test; 2023 players appearing anywhere in that
pool are excluded from training. No row is reassigned or dropped by this audit.

Preparation uses terminal-event served numerator sums divided by nonmissing served
denominator sums, with missing denominators effectively zero. It does not implement
standard seasonal wOBA. All 239 original numerator sums, denominator sums,
terminal-row counts and ratios reproduce within absolute 1e-9.

## Independent coverage and provenance

| Outcome season | Eligible | Matched | Ambiguous | Unmatched after attempt | Not yet verified | Published wOBA + full components |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 114 | 114 | 0 | 0 | 0 | 114 |
| 2025 | 125 | 125 | 0 | 0 | 0 | 125 |
| All | 239 | 239 | 0 | 0 | 0 | 239 |

The public [2024 leaderboard](https://www.fangraphs.com/leaders/major-league?pos=all&stats=bat&lg=all&qual=0&type=8&season=2024&season1=2024&ind=0&pageitems=2000&pagenum=1)
and [2025 leaderboard](https://www.fangraphs.com/leaders/major-league?pos=all&stats=bat&lg=all&qual=0&type=8&season=2025&season1=2025&ind=0&pageitems=2000&pagenum=1)
embed a JSON leaderboard payload in `__NEXT_DATA__`. These captures contain 1,454
and 1,470 rows respectively, equal to the embedded `totalCount`. We used zero
qualification threshold, all positions/leagues/teams, one season, no postseason
or monthly split, MLB level and `ind=0`. Each eligible MLBAM ID occurs exactly
once in its corresponding season capture. The parser checks scope, season and
capture completeness before matching.

Identity is an exact join of FanGraphs' own **`xMLBAMID` plus `Season`**, with its
`playerid` retained. Names are display evidence only; all 239 also agree exactly
with the frozen display names. Cross-year MLBAM→FanGraphs mapping is consistent
and one-to-one. Duplicate candidates would be ambiguous, never silently chosen.
This avoids both name collisions and conflating two years for a repeated player.
There are **21 multi-team seasons** (5 in 2024, 16 in 2025), represented by one
all-team row (`TeamName="- - -"`, team ID 0). We do not add team rows or average
team wOBA. Matching identity is distinct from validating numerical agreement:
Sweeney is a verified match despite his internal count discrepancy.

Retrieval occurred November 11, 2026, 07:49–07:55 UTC (November 10 local), via
`curl` HTTPS. `2026-11-11T07:55:46+00:00` records registration of those captures;
it is not an invented exact per-request completion time. Embedded `dataUpdatedAt`
is saved separately; origin revision time and historical scoring revision history
are unknown. An initial guessed API route returned 404; the public pages provided
complete coverage, so no API failure was classified as an unmatched player.

`validation/references/fangraphs_woba_cohort_v1.json` contains only curated cohort
reference facts and retrieval/query metadata: original source numeric wOBA tokens,
their decimal precision, display precision (three places), both identifiers,
season, source name/team, source/player URLs, and integer AB, PA, 1B, 2B, 3B, HR,
BB, IBB, HBP, SF, SH. Raw HTML remains ignored under `data/processed/` and SHA-256
identifies each capture. These values were read from FanGraphs, not calculated
from Callup events. The original ten manual references remain unchanged; the new
capture supplies greater precision. Differences from an old rounded display alone
do not establish that historical records changed.

## Internal reconstruction and numerical comparisons

The independent source counts are **never inputs to internal reconstruction**.
`callup.woba_audit.reconstruct` classifies existing archived terminal events:

`N = wBB*(BB-IBB) + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR`

`D = AB + BB - IBB + SF + HBP`; `standard_woba = N/D`.

Errors and fielder's choices are AB with zero numerator; ordinary outs and
strikeout double plays are AB. Sacrifice flies (including double plays) enter D;
sacrifice bunts, IBB, catcher interference and truncated PAs do not. Completed
archive PA is terminal rows minus truncated PAs, retaining interference and SH
for the separate PA coverage comparison. Unknown events fail closed rather than
being silently treated as outs. Duplicate pitch keys, missing pitch keys,
multiple terminal events for a game/PA, and incorrect event-date years also fail.
The shared extracts omit `game_type`: regular-season scope relies on the prior
[full archive audit](../reports/archive-summary.md), not a new game-type check.

The [FanGraphs definition](https://library.fangraphs.com/offense/woba/) and
[Guts coefficients](https://www.fangraphs.com/tools/guts?type=cn) give:

| Outcome year | uBB | HBP | 1B | 2B | 3B | HR |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | .689 | .720 | .882 | 1.254 | 1.590 | 2.050 |
| 2025 | .691 | .722 | .882 | 1.252 | 1.584 | 2.037 |

The existing captured coefficients were checked again against Guts in this session.
No extra multiplication by wOBAScale is applied. The coefficient values are
published to three decimals; the independent embedded player wOBA has greater
numeric precision. That numeric precision does not imply unlimited measurement
accuracy. We preserve the actual source tokens rather than padding three-place
values with fictitious digits.

All following differences are **Callup quantity minus independent published
FanGraphs wOBA**, unweighted across player-seasons, in fractional wOBA units.

| Comparison | n | Mean signed | Mean absolute | Median signed | Median absolute | Maximum absolute |
|---|---:|---:|---:|---:|---:|---:|
| Original, all | 239 | +.012248 | .012265 | +.011976 | .011976 | .043710 |
| Original, 2024 | 114 | +.011972 | .012000 | +.011952 | .011952 | .043710 |
| Original, 2025 | 125 | +.012501 | .012506 | +.012242 | .012242 | .035145 |
| Standard reconstruction, all | 239 | −.000048 | .000068 | −.000077 | .000077 | .000850 |
| Standard reconstruction, 2024 | 114 | +.000020 | .000021 | +.000022 | .000022 | .000045 |
| Standard reconstruction, 2025 | 125 | −.000110 | .000110 | −.000105 | .000105 | .000850 |

For an entirely internal comparison (not independent validation), original minus
standard reconstruction over all 239 has mean signed +.012296, mean absolute
.012312, median signed/absolute .012244 and maximum absolute .043689.
The generated JSON includes all these statistics by split as well as year.
Original-minus-published mean signed differences by split are train +.012469,
excluded overlap +.011379 and test +.012501.

**238 rows have exact agreement for all eleven independent component totals.**
Their reconstruction-minus-published mean signed gap is −.000045, mean absolute
.000065 and maximum absolute .000163. Each residual is compatible with the bound
from ±.0005 on each of the six displayed coefficients, weighted by its actual
contributing-event count and divided by D, plus the source-token rounding bound.
The status is `compatible_with_coefficient_precision`, not an assertion of exact
high-precision wOBA equality. Obtaining independently published higher-precision
coefficients would test this explanation; estimating them from player records
would not independently verify them. No residual exceeds this bound among the
238 count-matched rows. All 2025 residuals are negative, consistent with a seasonal
coefficient approximation rather than random event errors, but this is an
interpretation, not proven origin-server arithmetic.

The original labels are higher in 236 rows and lower in 3. Absolute original gaps
exceed .005 in 204/239 and .010 in 151/239. Largest is Ali Sánchez 2024:
original .227778 versus published .184068, gap +.043710. Jonah Bride 2025 has
+.035145. These are full-cohort descriptive findings, not extrapolations from
the ten-player selection and not a population p-value.

## Event anomalies and the remaining attribution issue

| Archived event issue, eligible cohort only | 2024 | 2025 | Total |
|---|---:|---:|---:|
| Missing required standard denominator fields | 77 | 91 | 168 |
| Of those, missing AB-out denominators | 61 | 75 | 136 |
| Truncated PAs | 62 | 44 | 106 |
| Completed archive PA differs from official PA | 0 | 1 | 1 player-season |

Missing required denominators affect 98 player-seasons. The remaining 32 missing
fields are 21 singles, 2 HR and 9 walks. None of the terminal rows has a missing
numerator value. Numerator fields nevertheless contain nonstandard credits:
392 errors contribute 352.8; 124 fielder's choices contribute 110.7 (one carries
zero); 95 IBB contribute 38 with missing denominators; 244 SH contribute 62.1;
29 interference events contribute 20.3 and 29 served denominators. Twenty
strikeouts carry .7 each; two sacrifice flies carry .9 each. Some bunts carry
.9 rather than .2. These are observed source-field conventions/anomalies; their
upstream feed/scoring causes have not all been established. They should not be
summed as standard wOBA numerator credits. Detailed event/value/denominator
frequencies and game/date/PA/pitch-keyed anomaly rows are generated for inspection.

The mean original-minus-standard difference decomposes additively as +.009845
from removing nonstandard numerator credits, +.000562 from denominator correction,
and +.001889 from seasonal coefficients. This attribution holds the served
denominator fixed for the first step, then changes D, then weights; attribution
is order-dependent. It explains the arithmetic, not a causal source history.

**Trey Sweeney, 2025 (test)** has internal AB=297 and PA=327 versus independent
AB=296 and PA=326; every other captured component agrees. The excess event is
2025-09-12, game 776366, archived PA 11, pitch 5: a strikeout with served N=0,
D=1. Archived pitches 1–2 identify Javier Báez (595879), pitches 3–5 Sweeney
(700242). MLB's independently retrieved
[game log](https://statsapi.mlb.com/api/v1/people/700242/stats?stats=gameLog&group=hitting&season=2025&sportIds=1)
gives Sweeney 3 AB/PA that day, while the archive gives 4. The
[official play-by-play](https://statsapi.mlb.com/api/v1.1/game/776366/feed/live)
at zero-based atBatIndex 10 records Sweeney replacing Báez at 0–2, and officially
credits the strikeout to Báez. This establishes an attribution problem with using
the terminal batter alone, rather than evidence of an extra played PA.

The raw MLB responses are ignored and their hashes, URLs and curated supporting
facts are in `validation/references/woba_sweeney_attribution_v1.json`. This is
supporting MLB evidence, separate from the FanGraphs references. No correction
has been applied. Sweeney remains `unresolved_component_difference` in diagnostic
v1: original .256000, internal standard 79.676/327=.243657, published .244508;
standard residual −.000850 exceeds his coefficient bound (~.000128). Removing
the incorrectly attributed zero-credit AB would give 79.676/326≈.244405, within
the coefficient bound, but that is a proposed explicit event-attribution revision,
not the v1 output. Any implementation should preserve a correction ledger and
check both affected players/cohort membership, not silently delete a pitch.

For all other rows, completed PA agrees with official PA; the 106 truncated rows
have zero served N/D and explain terminal-count inflation. Exact component totals
cannot rule out offsetting individual-game errors. Exhaustive independent
game-by-game reconciliation of every player was not performed. Event-level
source causes and high-precision seasonal coefficients remain follow-up work.

## Reproduction and review artifacts

Install the existing locked dependencies, then run from the repository root:

```bash
python scripts/audit_woba_cohort.py
pytest
ruff check .
```

The default run is offline, reading frozen shared pitches and the curated reference
fixture. It writes only ignored `data/processed/woba_cohort_v1/`:

- `reconciliation.csv`: all 239 keys, original labels, internal counts and ratios,
  independent values/counts/IDs/URLs/precision, signed differences, separate match
  and reconciliation statuses, SHA-256 provenance and `adopted_as_target=False`.
- `events.csv`, `served_weights.csv`, `anomalies.csv`: cohort-level event accounting,
  served-field inventories and event-keyed exceptions.
- `summary.json`: overall/year/split coverage and discrepancy summaries, formulas,
  input/code checksums, Git revision/dirty flag, pandas version and reference metadata.

Raw captures can be refreshed explicitly, never as a side effect of the offline
audit. Use the exact URLs above with curl `--fail --silent --show-error --max-time 60`
and save as `data/processed/woba_cohort_v1/sources/fangraphs_2024.html` and
`fangraphs_2025.html`. Then import to a **new reviewed reference version**:

```bash
python scripts/audit_woba_cohort.py \
  --capture data/processed/woba_cohort_v1/sources \
  --retrieved-at ACTUAL_TIME_WITH_UTC_OFFSET \
  > data/processed/woba_cohort_v1/proposed_references.json
```

Do not overwrite a prior fixture with a new retrieval. Check complete scope/counts,
ID stability, source revisions and reference differences before promoting selected
reference facts into Git. Raw pages and full generated tables stay ignored.

Tests cover source-token precision, completeness/scope rejection, name collisions,
ambiguous duplicate matches, missing matches, conflicting crosswalk IDs, reference
uniqueness, missing independent references, signed/absolute statistics, full-cohort
component reconciliation, the Sweeney exception, reproducible reruns and unchanged
shared/model input bytes. Existing ten-season tests still run unchanged.

## Recommendation for Anish — proposed, awaiting review

Adopt **standard seasonal FanGraphs wOBA as the intended target definition** after
review. The full cohort demonstrates a systematic and practically meaningful
measurement mismatch in the original target. About twelve wOBA points on average,
with forty-four at the maximum, is substantial compared with the existing Ridge
MAE of .035010; it is also much larger than its .000096 MAE improvement over the
training-average baseline. Those saved model metrics concern the original target:
this magnitude comparison does not tell us how either model will perform on a
revised target. No model-performance improvement has been measured or promised.

Create a separately versioned outcome table only after approval, preserving the
original shared table and split forever. Proposed output:
`data/processed/outcomes/standard_woba_v1.csv`, unique on `(player_id, season)`,
with `outcome_version`, `player_id` (MLBAM), `season` (feature year), `outcome_year`,
`split`, `original_provisional_woba`, `reconstructed_standard_woba`, nullable
`independently_published_woba`, `fangraphs_player_id`, original eligibility flags,
internal and reference component counts, standard N/D, formula/coefficient version,
`match_status`, `reconciliation_status`, `correction_ledger_version`, source URLs,
retrieval timestamps, published precision, and input/reference/code hashes.
Keep every eligible row; an unresolved candidate value should carry its status,
with any approved target column null until acceptance. If extended to the full
926-row pool, preserve unavailable labels as null, never zero.

Use Callup event counts for reconstruction, with reviewed official-attribution
corrections in an explicit ledger; retain published values in a separate column.
Do not mix external replacement counts into internal reconstructions. Resolve
Sweeney through the documented substitution rule and test it before accepting
his candidate. Define a documented coefficient-precision tolerance, distinguish
component agreement from exact rate agreement, and optionally retain a rounded
three-decimal comparison for display only. Get higher-precision coefficients if
exact reproduction of the published numeric payload is required.

A later approved model comparison would use a new data/target version, the same
frozen split and new output paths. It is outside this investigation. **No target
replacement has been implemented; the artifacts here are diagnostics for review.**

Validation completed for this change: **138 pytest tests passed**, and
`ruff check .` passed. A before/after SHA-256 comparison of 38 pre-existing
shared inputs and analysis artifacts found no changed bytes, including all five
initially untracked preliminary-audit files. The preservation manifest is ignored
at `data/processed/woba_cohort_v1/preserved_inputs.json`. Git status contains only
untracked research additions; no tracked file changed.

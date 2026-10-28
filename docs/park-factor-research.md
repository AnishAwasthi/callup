# How Triple-A ballparks affect hitting

Issue #3. Prototype code: [`callup/parks.py`](../callup/parks.py) and [`scripts/park_prototype.py`](../scripts/park_prototype.py). Tests on invented data: [`tests/test_parks.py`](../tests/test_parks.py).

## Recommendation

- **Scale: a neutral park is 1.0.** A factor of 1.08 means hitters produce about 8% more of the statistic there than in a typical park in the same league. Factors multiply rates directly. Multiply by 100 to display them on the FanGraphs/Baseball-Reference scale.[^1]
- **Starting method: `home_away_shrunk`.** It uses a home-versus-road wOBA ratio for each team's park, corrected because a team never visits its own park on the road, normalized to 1.0 within each league, pooled with the previous season when the venue is unchanged, and then pulled toward 1.0 by an amount based on its uncertainty (empirical Bayes). It is transparent, uses only data available by January 1 of the following year, and agrees well with a model that adjusts for which players were involved.
- **Assign games by venue, not by the `home_team` label.** Use the MLB Stats API schedule (`game_pk` → `venue.id`). Ten games were played in the visiting team's park, and two suspended games were finished in a different park.
- **Statistic: wOBA** The AAA version of the study's target (next-season MLB wOBA; see docs/methodology.md). To confirm with Anish.
- **Treat every factor as provisional.** Two seasons of data, no games between the two leagues, and an unagreed statistic all mean these numbers are not final.

## Data and venue mapping

All AAA pitch rows are used, including hitters outside the study cohort. A PA is a row with a nonmissing `events` value and `woba_denom == 1`. The 2,023 PAs with a missing denominator (2023–2024 combined) are dropped rather than scored as zero, along with the 1,574 PAs with a zero denominator (sacrifice bunts and truncated PAs).

**Venue source.** The MLB Stats API endpoint `schedule?sportId=11&season=Y&gameType=R` lists each game's `venue.id`.[^2] Postponed and cancelled entries are dropped; `Final` and `Completed Early` entries are kept. Responses are cached in the ignored `data/cache/` folder. The cache is a 2026 snapshot of past schedules, so later corrections could differ from what was known at the time.

| Check | 2023 | 2024 |
|---|---|---|
| Pitch-file games found in schedule | 2,224 / 2,224 | 2,232 / 2,232 |
| Team-seasons whose main park matches `teams.csv` `default_venue_id` | 30 / 30 | 30 / 30 |
| Games played in the visitor's park (counted at the actual venue) | 3 | 7 |
| Suspended games finished at a different venue (**excluded**) | 0 | 2 |
| Games between the International League and Pacific Coast League | 0 | 0 |

Notes:

- The `teams.csv` default venues hold up for 2023–2024, but they describe each team's season, not each game. The per-game schedule is the documented mapping. `park_id` in the output is the Stats API `venue.id`.
- **Join on IDs, not abbreviations or names.** `COL` means Columbus (Triple-A) and also Columbia (Single-A). Only Columbus appears in the AAA files, but abbreviation joins across levels are unsafe. Venue names also change while IDs stay the same: the API now calls Innovative Field (Rochester) "ESL Ballpark", and Coolray Field (Gwinnett) "Gwinnett Field".
- **The two split games** (752285, SYR–WOR; 752681, NOR–CLT) were finished at the visitor's park. Their pitch rows all carry the original date, so it is impossible to tell which PAs happened where. They are left out.
- **Watch for venue changes.** No AAA team changed parks between 2023 and 2024. Pooling seasons only combines seasons with the same `park_id`. Before extending to 2025, check Sacramento: Sutter Health Park was shared with the MLB Athletics.[^3]
- The API's `elevation` field is mostly empty for these venues, so elevation is not used as an input.

## Methods compared

All three methods use 2023–2024 AAA data. Season Y uses only seasons Y−1 and Y, so 2023 factors use 2023 alone, and 2024 factors use 2023–2024. No 2025 data is used.

| Method | What it does | Pros | Cons |
|---|---|---|---|
| `home_away_ratio` | (wOBA in all PAs at the park, both teams batting) ÷ (wOBA in the team's road games), one season. Corrected as `p = r·N/(N−1+r)` with N = parks in the league, then home-PA-weighted league mean set to 1.0[^4] | Classic and simple. Team quality largely cancels because the team bats and pitches in both samples | Noisy. Compares only within a league |
| `home_away_shrunk` (**recommended**) | Same ratio, pooled over Y−1 and Y when the venue is the same, then shrunk on the log scale: `w = τ²/(τ²+se²)`, with τ² = observed variance across parks − mean sampling variance[^5] | Pooling and shrinkage cut noise. Shrinkage is driven by each park's own uncertainty | Still compares only within a league. Standard errors assume independent PAs |
| `player_adjusted` | Ridge model for each PA: mean + batter-season + pitcher-season + venue effects (penalty = 200 PAs on player effects), fitted by backfitting. Normalized to all-AAA mean 1.0[^6] | Adjusts for uneven schedules and opponent quality. Links the two leagues through players who appeared in both | Less transparent. The league-to-league link depends on a modest number of moving players and mixes in league-wide offense levels |

The approach Statcast uses for MLB, comparing the same batters' results at a park with their results elsewhere over several years, is a close relative of `player_adjusted`.[^7]

## Prototype results (wOBA)

Run `python scripts/park_prototype.py` (about 25 seconds after the first schedule download). Full tables are in `data/processed/park_method_comparison.csv`.

| | 2023 | 2024 |
|---|---|---|
| Median PAs per park, single season (home / road) | 5,778 / 5,800 | 5,655 / 5,699 |
| Median PAs pooled for `home_away_shrunk` (home / road) | same (no 2022 data) | 11,429 / 11,510 |
| SD of log single-season ratio across parks | 0.055 | 0.062 |
| Mean standard error of log factor: single season / pooled | 0.027 / 0.027 | 0.028 / 0.019 |

Sampling noise accounts for roughly a quarter of the spread between parks in a single season, so shrinkage keeps about 75–85% of each park's distance from 1.0.

**Most hitter-friendly and pitcher-friendly parks (`home_away_shrunk`, 2024):** Albuquerque 1.083, Reno 1.082, St. Paul 1.072, El Paso 1.061 … Rochester 0.964, Oklahoma City 0.957, Round Rock 0.953, Sugar Land 0.907, Sacramento 0.902. Ranges: single-season ratio 0.87–1.11; shrunk 0.90–1.09; player-adjusted 0.91–1.13.

**Agreement between methods.** The single-season ratio and the player-adjusted factor (rescaled within league) correlate at **0.92**, so team and opponent quality do not appear to distort the simple ratio much.

**League level.** The player-adjusted factors average 1.02 in the PCL and 0.99 in the IL in both seasons. Home/away factors cannot show this, because each league is normalized to its own average. Salt Lake (roughly 4,200 ft[^8]) shows the consequence: it rates 0.99 against other PCL parks but about 1.0 across all of AAA.

## Distortions to watch

- **Small samples.** One season gives about 5,700 home PAs per park and a standard error of about 3% on the factor. Single-season ratios correlate only **0.62** from 2023 to 2024. Using random subsets of games, a 25% sample moves factors by a median of 0.037 (max 0.15), and a 50% sample by 0.021 (max 0.07). Home-run factors are much noisier: single-season 0.54–1.48, and the 25% sample moves them by a median of 0.15. Use pooled and shrunk factors, and leave thin samples blank.
- **Team and opponent quality.** These mostly cancel in the home/away ratio because the team plays in both samples. They do not cancel when the home team's roster changes a lot during the season. The player-adjusted check handles this.
- **League differences.** There were no games between the two leagues in either season, so home/away factors are relative to the park's own league. The PCL has several high-altitude, dry-air parks, so a PCL park at 1.00 is not equivalent to an IL park at 1.00. Use `player_adjusted` (or a league adjustment) before comparing hitters across leagues.
- **Altitude and climate.** Albuquerque, Reno, Salt Lake, El Paso and Las Vegas are at high elevation; thinner air increases fly-ball distance.[^8] Altitude explains part of the PCL's higher league level and is the leading reason for its top factors.
- **Handedness.** Fence distances and wind affect left- and right-handed hitters differently.[^9] Not yet estimated. Splitting by `stand` would halve each sample, so it would need to be pooled and shrunk too.
- **Uneven schedules.** Teams do not visit every park equally. The own-park correction assumes they do. The player model helps with this.
- **Venue changes and renovations.** Pool seasons only for the same `park_id`. Fence or surface changes within the same venue ID would need a separate check.
- **Rule experiments.** AAA has tested rules such as the automated ball-strike system during these seasons.[^10] When those applied unevenly by date or league, they could look like park effects.
- **Home-field advantage and travel** affect both samples about equally and are not modeled.

## Output: `data/processed/park_prototype.csv`

One row per `(season, home_team)`. There are 60 rows (30 parks × seasons 2023 and 2024), following the [data contract](data-contract.md#park-prototype-output):

| Column | Meaning |
|---|---|
| `season`, `home_team` | Integer year and AAA team abbreviation (unique key) |
| `park_id` | Stats API `venue.id`, verified per game from the schedule |
| `factor` | `home_away_shrunk` wOBA factor. Blank when either side has fewer than `--min-pa` PAs (default 2,000) |
| `reference_scale` | `1.0`: a neutral park within the league |
| `n_home_pa`, `n_away_pa` | PAs with `woba_denom = 1` at the park and in the team's road games, summed over the seasons used (2023: one season; 2024: two) |
| `method`, `provisional` | `home_away_shrunk_woba`; always `True` for now |

The script also writes `park_method_comparison.csv` (all three methods, the raw ratio, the standard error and the seasons used) and `park_venue_audit.csv` (venue checks for each team-season). All files stay in ignored `data/processed/`.

**For Persons 1, 2 and 4:** do not join park factors to hitter rows on `home_team`; that duplicates rows or misses road games. Instead, assign each of a hitter's PAs the factor for the park where it happened, average those factors weighted by PA, and divide the hitter's rate statistic by that average. This is the hitter's actual park exposure; the usual shortcut is `(1 + factor)/2`, which assumes exactly half of PAs at home.[^1] Use only the same season's factors so that 2024 features use 2023–2024 data and nothing from 2025. The data contract leaves the join format open, so agree on it before anyone builds it.

## Checks performed

- Home/away direction: invented data with one inflated park gives that park a factor above 1 and the others below 1. A relocated game counts at the park where it was played. The own-park correction recovers the true 1.2 ratio between parks, where raw ratios would show 1.32.
- Plausibility: high-altitude PCL parks rank at the top in all three methods, and the methods agree (correlation 0.92).
- Extremes: no wOBA factor falls outside 0.87–1.13. Shrinkage pulls the extremes in: Sugar Land 2023 moves from 0.87 to 0.90.
- Blanks: no real factor is blank at a minimum of 2,000 PAs. The tests confirm that thin samples are left blank instead of being set to 1.0.

## Next steps

1. Confirm the statistic (wOBA versus components such as HR, 2B/3B and K/BB) with Anish.
2. Decide whether to report within-league or all-AAA factors before hitters are compared across leagues.
3. Add handedness-specific factors, pooled and shrunk.
4. Use game-level bootstrap standard errors, since PAs within a game are not independent.
5. Add the hitter exposure helper once the join format is agreed.

## Sources to verify and fill in

Each blank is a placeholder. The suggestions are unverified starting points and have not been checked.

[^1]: ______ (suggested: FanGraphs Library, "Park Factors"; Baseball-Reference, "Park Adjustments" page; both for the 100 scale and half-home adjustment)
[^2]: ______ (suggested: MLB Stats API `schedule` and `venues` endpoints, statsapi.mlb.com, and MLB Advanced Media terms of use)
[^3]: ______ (suggested: news coverage of the Athletics playing at Sutter Health Park beginning in 2025)
[^4]: ______ (suggested: Thorn & Palmer, *The Hidden Game of Baseball* (1984), and *Total Baseball*, for the home/road ratio and the own-park correction)
[^5]: ______ (suggested: Efron & Morris (1975), "Data Analysis Using Stein's Estimator and Its Generalizations," *JASA*; Tango, Lichtman & Dolphin, *The Book* (2007), on regression to the mean)
[^6]: ______ (suggested: Acharya et al. (2008), "Improving Major League Baseball Park Factor Estimates," *Journal of Quantitative Analysis in Sports*)
[^7]: ______ (suggested: Baseball Savant Statcast Park Factors leaderboard and its methodology notes)
[^8]: ______ (suggested: Alan Nathan's baseball physics work on altitude and fly-ball distance; ballpark elevation from a venue reference)
[^9]: ______ (suggested: FanGraphs or Statcast handedness-split park factors)
[^10]: ______ (suggested: MLB announcements on Triple-A automated ball-strike system testing in 2023–2024)

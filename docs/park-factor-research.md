# How Triple-A ballparks affect hitting

Issue #3. Prototype code: [`callup/parks.py`](../callup/parks.py) and [`scripts/park_prototype.py`](../scripts/park_prototype.py). Tests on invented data: [`tests/test_parks.py`](../tests/test_parks.py). A LaTeX version of this document is in [`park-factor-research.tex`](park-factor-research.tex).

## Recommendation

- **Scale: a neutral park is $f = 1.0$.** For example, $f = 1.08$ means hitters produce about 8% more of the statistic there than in a typical park in the same league. Factors multiply rates directly. Multiply by 100 to display them on the FanGraphs/Baseball-Reference scale.[^1]
- **Starting method: `home_away_shrunk`.** It uses a home-versus-road wOBA ratio for each team's park, corrected because a team never visits its own park on the road, normalized to 1.0 within each league, pooled with the previous season when the venue is unchanged, and then pulled toward 1.0 by an amount based on its uncertainty (empirical Bayes). It is transparent, uses only data available by January 1 of the following year, and agrees well with a model that adjusts for which players were involved.
- **Assign games by venue, not by the `home_team` label.** Use the MLB Stats API schedule (`game_pk` → `venue.id`). These usually agree, but can differ: ten games were played in the visiting team's park, and two suspended games were finished in a different park.
- **Statistic: wOBA**, the AAA version of the study's target (next-season MLB wOBA; see [methodology](methodology.md)). To confirm with Anish.
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

**Venue versus label.** Assigning games by the `home_team` label instead of by venue moves 576 of 344,431 PAs (0.17%) to a different park. The median factor changes by 0.0001 and the largest by 0.009 (Memphis 2024), about a third of one standard error. The effect is small for 2023–2024, but venue assignment is the correct definition and costs one cached request per season.

## Methods

Equations are numbered. Each one that the code computes is followed by a **Code** line naming the function in [`callup/parks.py`](../callup/parks.py) and linking to the lines that implement it. [Appendix A](#appendix-a-implementation-map) collects these links, with the test that checks each one.

### Notation

| Symbol | Meaning | Code |
|---|---|---|
| $i$ | A plate appearance (PA) | one row of the `pa` frame |
| $y_i$ | Its value: `woba_value` for wOBA, or 1 if a home run and 0 otherwise for `hr_rate` | `value` |
| $v(i)$ | The venue where PA $i$ was played (from the schedule) | `venue_id` |
| $t$, $k_t$ | A team, and the venue of most of its nominal home games | `home_team`, `park_id` |
| $\ell(t)$, $N$ | The team's league, and the number of parks in it ($N = 15$) | `league`, `n_parks` |
| $X$ | A season. Season $X$ uses only seasons $X-1$ and $X$, so every factor is available by January 1 of $X+1$ | `season` |
| $n_H$, $n_R$ | PAs in the home and road samples | `n_home_pa`, `n_away_pa` |
| $f_t$, $\tilde{f}_t$ | Normalized factor, and the shrunk factor reported in the output | `factor` |
| $\mathrm{se}_t$ | Standard error of $\log f_t$ | `se_log` |

*Code:* PA values and venues come from [`plate_appearances`](../callup/parks.py#L50-L68) (value at [line 61](../callup/parks.py#L61)), venues from [`schedule_venues`](../callup/parks.py#L31-L47), and $k_t$ from [`home_parks`](../callup/parks.py#L71-L86), which takes the most common venue at [lines 74–76](../callup/parks.py#L74-L76).

For each team-season, the **home sample** $H_t$ is every PA at the team's park, by both teams. The **road sample** $R_t$ is every PA in the team's games at other venues:

$$
H_t = \lbrace i : v(i) = k_t \rbrace, \qquad
R_t = \lbrace i : t \text{ plays in the game of } i,\ v(i) \neq k_t \rbrace
\tag{1}
$$

*Code:* [`home_away_sums`](../callup/parks.py#L94-L97): `at_park` is $H_t$; `in_game & ~at_park` is $R_t$.

Each sample has a size $n$, a mean $\bar{y}$ and a per-PA variance $s^2$:

$$
\bar{y}_{H} = \frac{1}{n_{H}} \sum_{i \in H_t} y_i, \qquad
\bar{y}_{R} = \frac{1}{n_{R}} \sum_{i \in R_t} y_i
\tag{2}
$$

*Code:* the sums are built in [`home_away_sums`](../callup/parks.py#L98-L99) (`home_sum`, `away_sum`), and the means are taken in [`ratio_factors`](../callup/parks.py#L107-L108) (`home_rate`, `away_rate`).

### Method 1: single-season home/road ratio (`home_away_ratio`)

**Raw ratio.**[^4]

$$
r_t = \frac{\bar{y}_{H}}{\bar{y}_{R}}
\tag{3}
$$

*Code:* [`ratio_factors`, line 109](../callup/parks.py#L109): `raw = home_rate / away_rate`, saved as `raw_factor`.

**Own-park correction.** A team's road games are spread over the other $N - 1$ parks, never its own. Suppose the true factors $\pi_k$ average 1 across the league and the schedule is balanced. Then the road sample's expected level is the average of the other parks:

$$
\mathbb{E}[\bar{y}_R] \propto \frac{N - \pi_t}{N - 1}
\qquad\Longrightarrow\qquad
r_t = \frac{\pi_t\,(N - 1)}{N - \pi_t}
\tag{4}
$$

Solving (4) for $\pi_t$ gives the corrected factor:

$$
p_t = \frac{r_t\,N}{N - 1 + r_t}
\tag{5}
$$

*Code:* [`ratio_factors`, lines 111–112](../callup/parks.py#L111-L112): `corrected = raw * n_parks / (n_parks - 1 + raw)`. Equation (4) is the derivation only; nothing computes it.

On invented data with true factors 1.2 and 1.0, the raw ratios differ by a factor of 1.32, and the corrected factors recover 1.2.

**Normalization.** Each league is rescaled so its home-PA-weighted average is 1:

$$
f_t = \frac{p_t}{\bar{p}_{\ell}}, \qquad
\bar{p}_{\ell} = \frac{\sum_{u \in \ell} n_{H_u}\, p_u}{\sum_{u \in \ell} n_{H_u}}
\tag{6}
$$

*Code:* [`ratio_factors`, lines 116–118](../callup/parks.py#L116-L118): `league_mean` is $\bar{p}_\ell$, grouped by season and league. Parks with a blank factor are left out of the average.

**Why team quality mostly cancels.** Team $t$ bats and pitches in roughly equal shares of $H_t$ and $R_t$. Under a multiplicative model in which a PA's expected value is the league level × park effect × batter effect × pitcher effect, team $t$'s own player effects appear in both the numerator and denominator of $r_t$ and divide out. Opponents differ between the two samples, which a balanced schedule evens out only approximately.

**Standard error.** By the delta method, treating PAs as independent:

$$
\mathrm{se}_t^2 \approx \text{Var}(\log r_t) \approx \frac{s_{H}^2}{n_{H}\,\bar{y}_{H}^2} + \frac{s_{R}^2}{n_{R}\,\bar{y}_{R}^2}
\tag{7}
$$

*Code:* [`ratio_factors`, lines 120–122](../callup/parks.py#L120-L122): `se_log`, with $s^2$ computed from `home_sq` and `away_sq` (dividing by $n$).

This is used as the standard error of $\log f_t$ without adjustment. Exactly, the correction in (5) scales log-scale errors by $\partial \log p / \partial \log r = (N-1)/(N-1+r) \approx 0.93$ near $r = 1$, and normalization changes them very little. So $\mathrm{se}_t$ for $\log f_t$ is overstated by about 7%, which slightly increases shrinkage in Method 2.

For wOBA, $s \approx 0.52$ and $\bar{y} \approx 0.36$ per PA, so with equal samples of size $n$:

$$
\mathrm{se} \approx \frac{\sqrt{2}\,s}{\bar{y}\,\sqrt{n}} \approx \frac{2}{\sqrt{n}}
\tag{8}
$$

That is 0.027 for a typical season's 5,700 PAs per side and 0.046 at the minimum. Equation (8) is a rule of thumb; nothing computes it.

**Minimum sample.** $f_t$ is left blank, not set to 1, unless $\min(n_{H}, n_{R}) \ge n_{\min} = 2000$.

*Code:* [`ratio_factors`, line 113](../callup/parks.py#L113) (`enough`). It also requires both means to be positive, which matters only for `hr_rate` in tiny samples.

### Method 2: pooled and shrunk (`home_away_shrunk`, recommended)

**Pooling.** For season $X$, the samples from seasons $X-1$ and $X$ are combined when the team's park is unchanged, and (3)–(7) are recomputed from the pooled sums:

$$
H_t^{\text{pool}} = H_t^{(X-1)} \cup H_t^{(X)} \quad \text{if } k_t^{(X-1)} = k_t^{(X)}
\tag{9}
$$

and likewise for $R_t$. 2023 has no earlier season, so its pooled factor equals the single-season one.

*Code:* [`pooled_sums`](../callup/parks.py#L126-L137), where the same-park condition is [line 130](../callup/parks.py#L130). [`prototype`, line 191](../callup/parks.py#L191) passes the pooled sums back through `ratio_factors`.

**Shrinkage.**[^5] Each park's observed log factor is modeled as its true value plus sampling noise:

$$
\log f_t = \theta_t + \varepsilon_t, \qquad
\theta_t \sim (0,\ \tau^2), \qquad
\varepsilon_t \sim \mathcal{N}(0,\ \mathrm{se}_t^2)
\tag{10}
$$

The true log factors $\theta_t$ center on 0 because normalization makes the league average 1. The best linear estimate of $\theta_t$ shrinks the observed value toward 0:

$$
\hat{\theta}_t = w_t \log f_t, \qquad
w_t = \frac{\tau^2}{\tau^2 + \mathrm{se}_t^2}
\tag{11}
$$

The between-park variance $\tau^2$ is estimated by the method of moments, once per season across both leagues. The observed variance is the true spread plus the average noise:

$$
\hat{\tau}^2 = \max\left(0,\ \widehat{\text{Var}}(\log f) - \overline{\mathrm{se}^2}\right)
\tag{12}
$$

*Code:* [`shrink`, line 147](../callup/parks.py#L147): `true_var`, using the sample variance (dividing by $n-1$) and grouped by season only.

The reported factor is therefore

$$
\tilde{f}_t = \exp\left(w_t \log f_t\right) = f_t^{\,w_t}
\tag{13}
$$

*Code:* [`shrink`, line 148](../callup/parks.py#L148): `np.exp(values * true_var / (true_var + se2))` computes (11) and (13) together. [`prototype`, line 192](../callup/parks.py#L192) applies it to the pooled factors.

Parks with smaller samples get smaller $w_t$, and so are pulled further toward 1. In 2024 the output uses the pooled factors, where the smaller $\mathrm{se}$ gives larger weights than a single season would:

| | 2023 | 2024 |
|---|---|---|
| $\hat{\tau}$: single season / used in output (pooled) | 0.048 / 0.048 | 0.056 / 0.049 |
| Mean $\mathrm{se}$: single season / pooled | 0.027 / 0.027 | 0.028 / 0.019 |
| Typical $w$: single season / used in output (pooled) | 0.76 / 0.76 | 0.80 / 0.87 |

Sugar Land 2023 shows the effect: $f = 0.866$ becomes $\tilde{f} = 0.866^{0.76} \approx 0.896$.

**Why empirical Bayes.**
- With 30 parks, shrinking toward the common mean lowers expected squared error compared with raw estimates. This is the James–Stein result, which applies once there are three or more groups.[^5]
- The amount of shrinkage comes from the data ($\hat{\tau}^2$) and from each park's own sample size ($\mathrm{se}_t$), rather than from a fixed percentage borrowed from MLB.
- With 30 parks, full hierarchical Bayes would give nearly identical point estimates.

**Test on later data.** Each 2023 estimate was used to predict the 2024 single-season ratios, which come from completely separate games:

| 2023 estimate | RMSE against 2024 |
|---|---|
| Every park $f = 1$ | 0.061 |
| Raw single-season $f$ | 0.050 |
| Shrunk $\tilde{f}$ | **0.048** |

**The shrinkage is probably slightly too weak.** If true factors were constant, the year-to-year regression slope of $\log f$ would equal the single-season reliability $w$. The observed slope is 0.70, against $w = 0.76$. PAs within a game share weather, umpires and lineups, so $\mathrm{se}_t$ is somewhat underestimated (partly offset by the 7% overstatement noted under (7)). A game-level bootstrap would fix this and shrink a little more.

### Method 3: player-adjusted model (`player_adjusted`, a check)

A ridge regression fit to every PA in seasons $X-1$ and $X$, with batter-season, pitcher-season and venue effects:[^6]

$$
y_i = \mu + b_{\text{bat}(i)} + c_{\text{pit}(i)} + u_{v(i)} + e_i
\tag{14}
$$

$$
\min_{b,\,c,\,u}\ \sum_i e_i^2 + \lambda \left( \sum_j b_j^2 + \sum_m c_m^2 \right), \qquad \lambda = 200
\tag{15}
$$

$\mu$ is fixed at the overall mean. Venue effects are not penalized.

*Code:* [`player_adjusted`, lines 159–172](../callup/parks.py#L159-L172). Each pass updates one set of effects as residual sum ÷ $(n + \lambda)$ at [line 171](../callup/parks.py#L171), which minimizes (15) one block at a time. The two-season window is set at [`prototype`, line 194](../callup/parks.py#L194).

The factor for venue $k$ is normalized so the PA-weighted average across **all of Triple-A** is 1:

$$
f_k \propto \frac{\mu + u_k}{\mu}
\tag{16}
$$

*Code:* [`player_adjusted`, lines 174–175](../callup/parks.py#L174-L175). Factors are blank below 2,000 venue PAs ([`prototype`, line 196](../callup/parks.py#L196)).

The approach Statcast uses for MLB, comparing the same batters at a park with their results elsewhere, is a close relative.[^7]

This method adjusts for uneven schedules and opponents, and it is the only one that puts both leagues on one scale. It is less transparent:
- No single set of rows determines a factor; each depends on about 900 batter and 1,200 pitcher effects fitted together.
- The results depend on $\lambda$. Setting $\lambda = 0$ changes 2023 factors by up to 0.074; values from 200 to 1,000 change them by at most 0.014. The fit fully converges in 30 iterations.
- The comparison between leagues rests on about 40 batters and 60 pitchers per season who appeared in both leagues, involved in 12% of PAs.
- The code gives no standard error for these factors.

Use it as a check and for the league scale, not as the main factor.

## Prototype results (wOBA)

Run `python scripts/park_prototype.py` (about 25 seconds after the first schedule download). Full tables are in `data/processed/park_method_comparison.csv`.

| | 2023 | 2024 |
|---|---|---|
| Median PAs per park, single season (home / road) | 5,778 / 5,800 | 5,655 / 5,699 |
| Median PAs pooled for `home_away_shrunk` (home / road) | same (no 2022 data) | 11,429 / 11,510 |
| SD of single-season $\log f$ across parks | 0.055 | 0.062 |

Sampling noise accounts for roughly a quarter of the spread between parks in a single season ($\overline{\mathrm{se}^2} / \widehat{\text{Var}}(\log f) \approx 0.2$–$0.25$).

**Most hitter-friendly and pitcher-friendly parks ($\tilde{f}$, 2024):** Albuquerque 1.083, Reno 1.082, St. Paul 1.072, El Paso 1.061 … Rochester 0.964, Oklahoma City 0.957, Round Rock 0.953, Sugar Land 0.907, Sacramento 0.902.

| Method | 2023–2024 range |
|---|---|
| Single-season ratio $f$ | 0.87–1.11 |
| Shrunk $\tilde{f}$ | 0.90–1.09 |
| Player-adjusted | 0.91–1.13 |

**Agreement between methods.** The single-season ratio and the player-adjusted factor (rescaled within league) correlate at $\rho = 0.92$, so team and opponent quality do not appear to distort the simple ratio much.

**League level.** The player-adjusted factors average 1.02 in the PCL and 0.99 in the IL in both seasons. Home/away factors cannot show this, because each league is normalized to its own average. Salt Lake (roughly 4,200 ft[^8]) shows the consequence: it rates 0.99 against other PCL parks but about 1.0 across all of AAA.

## Distortions to watch

- **Small samples.** One season gives about 5,700 home PAs per park, so $\mathrm{se} \approx 0.027$. Single-season ratios correlate only $\rho = 0.62$ from 2023 to 2024. Using random subsets of games, a 25% sample moves factors by a median of 0.037 (max 0.15), and a 50% sample by 0.021 (max 0.07). Home-run factors are much noisier: single-season 0.54–1.48, and the 25% sample moves them by a median of 0.15. Use pooled and shrunk factors, and leave thin samples blank.
- **Team and opponent quality.** These mostly cancel in the home/away ratio because the team plays in both samples. They do not cancel when the home team's roster changes a lot during the season. The player-adjusted check handles this.
- **League differences.** There were no games between the two leagues in either season, so home/away factors are relative to the park's own league. The PCL has several high-altitude, dry-air parks, so a PCL park at 1.00 is not equivalent to an IL park at 1.00. Use `player_adjusted` (or a league adjustment) before comparing hitters across leagues.
- **Altitude and climate.** Albuquerque, Reno, Salt Lake, El Paso and Las Vegas are at high elevation; thinner air increases fly-ball distance.[^8] Altitude explains part of the PCL's higher league level and is the leading reason for its top factors.
- **Handedness.** Fence distances and wind affect left- and right-handed hitters differently.[^9] Not yet estimated. Splitting by `stand` would halve each sample and raise $\mathrm{se}$ by about $\sqrt{2}$, so it would need to be pooled and shrunk too.
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
| `factor` | $\tilde{f}_t$ from (13), the `home_away_shrunk` wOBA factor. Blank when either side has fewer than `--min-pa` PAs (default 2,000) |
| `reference_scale` | `1.0`: a neutral park within the league |
| `n_home_pa`, `n_away_pa` | $n_{H}$ and $n_{R}$, summed over the seasons used (2023: one season; 2024: two) |
| `method`, `provisional` | `home_away_shrunk_woba`; always `True` for now |

The script also writes `park_method_comparison.csv` (all three methods, the raw ratio, the standard error and the seasons used) and `park_venue_audit.csv` (venue checks for each team-season). All files stay in ignored `data/processed/`.

**For Persons 1, 2 and 4:** do not join park factors to hitter rows on `home_team`; that duplicates rows or misses road games. Instead, use each hitter's actual park exposure. For hitter $j$ with PAs $P_j$:

$$
\bar{f}_j = \frac{1}{\lvert P_j \rvert} \sum_{i \in P_j} \tilde{f}_{v(i)}, \qquad
\text{adjusted rate}_j = \frac{\text{observed rate}_j}{\bar{f}_j}
\tag{17}
$$

*Code:* **not yet implemented**; see Next steps.

The usual shortcut, $(1 + \tilde{f})/2$, assumes exactly half of a hitter's PAs are at home.[^1] Use only the same season's factors so that 2024 features use 2023–2024 data and nothing from 2025. The data contract leaves the join format open, so agree on it before anyone builds it.

## Checks performed

- **Home/away direction:** invented data with one inflated park gives that park a factor above 1 and the others below 1. A relocated game counts at the park where it was played. The own-park correction recovers the true 1.2 ratio between parks, where raw ratios would show 1.32.
- **Plausibility:** high-altitude PCL parks rank at the top in all three methods, and the methods agree ($\rho = 0.92$).
- **Extremes:** no wOBA factor falls outside 0.87–1.13. Shrinkage pulls the extremes in: Sugar Land 2023 moves from 0.87 to 0.90.
- **Blanks:** no real factor is blank at $n_{\min} = 2000$. The tests confirm that thin samples are left blank instead of being set to 1.0.

## Next steps

1. Confirm the statistic (wOBA versus components such as HR, 2B/3B and K/BB) with Anish.
2. Decide whether to report within-league or all-AAA factors before hitters are compared across leagues.
3. Add handedness-specific factors, pooled and shrunk.
4. Use game-level bootstrap standard errors, since PAs within a game are not independent.
5. Add the hitter exposure helper, Equation (17), once the join format is agreed.

## Appendix A: implementation map

Line links point to the version of [`callup/parks.py`](../callup/parks.py) in this PR. Recheck them if the code changes. Tests are in [`tests/test_parks.py`](../tests/test_parks.py) and use invented data. The code's docstrings write the season as $Y$ rather than $X$.

| Eq. | Quantity | Function | Lines | Tested by |
|---|---|---|---|---|
| — | PA value $y_i$; venue $v(i)$ | `plate_appearances`, `schedule_venues` | [61](../callup/parks.py#L61), [31–47](../callup/parks.py#L31-L47) | `test_plate_appearances_drop_missing_denominators_and_split_games`, `test_schedule_keeps_played_games_and_blanks_split_venues` |
| — | Team's park $k_t$ | `home_parks` | [74–76](../callup/parks.py#L74-L76) | `test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park` |
| (1) | Home and road samples | `home_away_sums` | [94–97](../callup/parks.py#L94-L97) | `test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park` |
| (2) | Sample means | `home_away_sums`, `ratio_factors` | [98–99](../callup/parks.py#L98-L99), [107–108](../callup/parks.py#L107-L108) | (via (3)) |
| (3) | Raw ratio $r_t$ | `ratio_factors` | [109](../callup/parks.py#L109) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (4) | Own-park derivation | — | — | — |
| (5) | Corrected $p_t$ | `ratio_factors` | [111–112](../callup/parks.py#L111-L112) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (6) | Normalized $f_t$ | `ratio_factors` | [116–118](../callup/parks.py#L116-L118) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (7) | Standard error $\mathrm{se}_t$ | `ratio_factors` | [120–122](../callup/parks.py#L120-L122) | not directly tested |
| (8) | Rule of thumb | — | — | — |
| — | Minimum sample | `ratio_factors` | [113](../callup/parks.py#L113) | `test_small_samples_stay_blank_not_neutral` |
| (9) | Pooling | `pooled_sums` | [126–137](../callup/parks.py#L126-L137) | `test_pooling_uses_same_park_and_never_later_seasons` |
| (10) | Shrinkage model | — | — | — |
| (11), (13) | Weight $w_t$ and shrunk $\tilde{f}_t$ | `shrink` | [148](../callup/parks.py#L148) | `test_shrinkage_moves_toward_one_and_noise_only_gives_one` |
| (12) | Between-park variance $\hat{\tau}^2$ | `shrink` | [147](../callup/parks.py#L147) | `test_shrinkage_moves_toward_one_and_noise_only_gives_one` |
| (14), (15) | Ridge model | `player_adjusted` | [159–172](../callup/parks.py#L159-L172) | `test_player_model_separates_strong_team_from_neutral_parks` |
| (16) | Venue factor $f_k$ | `player_adjusted` | [174–175](../callup/parks.py#L174-L175) | `test_player_model_separates_strong_team_from_neutral_parks` |
| (17) | Hitter exposure $\bar{f}_j$ | not yet implemented | — | — |

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

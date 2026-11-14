# How Triple-A ballparks affect hitting

Issue #3. Prototype code: [`callup/parks.py`](../callup/parks.py), [`scripts/park_prototype.py`](../scripts/park_prototype.py) and [`scripts/park_pooling_check.py`](../scripts/park_pooling_check.py). Tests on invented data: [`tests/test_parks.py`](../tests/test_parks.py).

## Summary

- **Proposed: `home_away_shrunk` factors for wOBA** (see [Conclusion](#conclusion)).
  - The method is a home-versus-road ratio for each team's park, corrected for the team never visiting its own park on the road, normalized to 1.0 within each league, pooled with the previous season, and pulled toward 1.0 by empirical Bayes.
  - wOBA had the least noise and the lowest out-of-sample error of the four statistics tested, and it is the study's outcome statistic.
- **Other statistics evaluated:** HR rate, doubles + triples rate and singles rate are compared under [Comparing the candidate statistics](#comparing-the-candidate-statistics). All are noisier than wOBA, and singles show little park effect.
- **Scale: a neutral park is $`f = 1.0`$.** For example, $`f = 1.08`$ means hitters produce about 8% more of the statistic there than in a typical park in the same league. Multiply by 100 for the FanGraphs/Baseball-Reference scale.[^1]
- **Games are assigned by venue, not by the `home_team` label**, using the MLB Stats API schedule (`game_pk` → `venue.id`).
- **Every factor is provisional**, and the proposal needs Anish's confirmation. Other choices are listed under [Judgment calls](#judgment-calls).

## Data and venue mapping

All AAA pitch rows are used, including hitters outside the study cohort. A PA is a row with a nonmissing `events` value and `woba_denom == 1`. The 2,023 PAs with a missing denominator (2023–2024 combined) are dropped rather than scored as zero, along with the 1,574 PAs with a zero denominator (sacrifice bunts and truncated PAs).

**Venue source.** The MLB Stats API endpoint `schedule?sportId=11&season=Y&gameType=R` lists each game's `venue.id`.[^2] Only `Final` and `Completed Early` entries are kept. Responses are cached in the ignored `data/cache/` folder. The cache is a 2026 snapshot of past schedules.

| Check | 2023 | 2024 |
|---|---|---|
| Pitch-file games found in schedule | 2,224 / 2,224 | 2,232 / 2,232 |
| Team-seasons whose main park matches `teams.csv` `default_venue_id` | 30 / 30 | 30 / 30 |
| Games played in the visitor's park (counted at the actual venue) | 3 | 7 |
| Suspended games finished at a different venue (**excluded**) | 0 | 2 |
| Games between the International League and Pacific Coast League | 0 | 0 |

- **Join on IDs, not abbreviations or names.** `COL` means Columbus (Triple-A) and also Columbia (Single-A). Venue names change while IDs stay the same: the API now calls Innovative Field "ESL Ballpark" and Coolray Field "Gwinnett Field".
- **Split games** (752285, SYR–WOR; 752681, NOR–CLT) were finished at the visitor's park. Their pitch rows don't show which PAs happened where, so they are left out.
- **Venue changes:** none between 2023 and 2024. Before extending to 2025, check Sacramento: Sutter Health Park was shared with the MLB Athletics.[^3]
- **Venue versus label:** assigning by the `home_team` label instead moves 576 of 344,431 PAs (0.17%). The wOBA factor changes by a median of 0.0001 and at most 0.009 (Memphis 2024).

## Methods

Equations are numbered. Each one the code computes is followed by a **Code** line linking to [`callup/parks.py`](../callup/parks.py). [Appendix A](#appendix-a-implementation-map) collects the links, with the test that checks each one.

### Notation

| Symbol | Meaning | Code |
|---|---|---|
| $`i`$ | A plate appearance (PA) | one row of the `pa` frame |
| $`y_i`$ | Its value for the chosen statistic (see [Statistics](#statistics)) | `value` |
| $`v(i)`$ | The venue where PA $`i`$ was played (from the schedule) | `venue_id` |
| $`t`$, $`k_t`$ | A team, and the venue of most of its nominal home games | `home_team`, `park_id` |
| $`\ell(t)`$, $`N`$ | The team's league, and the number of parks in it ($`N = 15`$) | `league`, `n_parks` |
| $`X`$ | A season. Season $`X`$ uses only seasons $`X-1`$ and $`X`$, so every factor is available by January 1 of $`X+1`$ | `season` |
| $`n_H`$, $`n_R`$ | PAs in the home and road samples | `n_home_pa`, `n_away_pa` |
| $`f_t`$, $`\tilde{f}_t`$ | Normalized factor, and the shrunk factor reported in the output | `factor` |
| $`\mathrm{se}_t`$ | Standard error of $`\log f_t`$ | `se_log` |

*Code:* [`plate_appearances`](../callup/parks.py#L59-L77), [`schedule_venues`](../callup/parks.py#L40-L56), and [`home_parks`](../callup/parks.py#L80-L95), which takes the most common venue at [lines 83–85](../callup/parks.py#L83-L85).

### Statistics

Every statistic is a rate per PA. For the three event rates, $`y_i = 1`$ if PA $`i`$ ended in one of the listed events and 0 otherwise, so walks, strikeouts and outs count in the denominator as 0.

| `--stat` | $`y_i`$ | Park features it reflects |
|---|---|---|
| `woba` | `woba_value` | all of the below, weighted |
| `hr_rate` | 1 for a home run | fence distance, altitude, wind |
| `doubles_triples_rate` | 1 for a double or triple | outfield size and shape, wall height |
| `singles_rate` | 1 for a single | infield surface, foul territory, outfield size |

*Code:* [`STATS` and `EVENT_STATS`, lines 30–36](../callup/parks.py#L30-L36); the value is set at [line 70](../callup/parks.py#L70).

### Home and road samples

For each team-season, the **home sample** $`H_t`$ is every PA at the team's park, by both teams. The **road sample** $`R_t`$ is every PA in the team's games at other venues:

```math
H_t = \lbrace i : v(i) = k_t \rbrace, \qquad
R_t = \lbrace i : t \text{ plays in the game of } i,\ v(i) \neq k_t \rbrace \qquad (1)
```

*Code:* [`home_away_sums`, lines 103–106](../callup/parks.py#L103-L106): `at_park` is $`H_t`$; `in_game & ~at_park` is $`R_t`$.

Each sample has a size $`n`$, a mean $`\bar{y}`$ and a per-PA variance $`s^2`$:

```math
\bar{y}_{H} = \frac{1}{n_{H}} \sum_{i \in H_t} y_i, \qquad
\bar{y}_{R} = \frac{1}{n_{R}} \sum_{i \in R_t} y_i \qquad (2)
```

*Code:* sums at [lines 107–108](../callup/parks.py#L107-L108); means in [`ratio_factors`, lines 116–117](../callup/parks.py#L116-L117).

### Method 1: single-season home/road ratio (`home_away_ratio`)

**Raw ratio.**[^4]

```math
r_t = \frac{\bar{y}_{H}}{\bar{y}_{R}} \qquad (3)
```

*Code:* [line 118](../callup/parks.py#L118): `raw = home_rate / away_rate`.

**Own-park correction.** Road games are spread over the other $`N - 1`$ parks. If the true factors $`\pi_k`$ average 1 and the schedule is balanced:

```math
\mathbb{E}[\bar{y}_R] \propto \frac{N - \pi_t}{N - 1}
\qquad\Longrightarrow\qquad
r_t = \frac{\pi_t\,(N - 1)}{N - \pi_t} \qquad (4)
```

Solving (4) for $`\pi_t`$:

```math
p_t = \frac{r_t\,N}{N - 1 + r_t} \qquad (5)
```

*Code:* [lines 120–121](../callup/parks.py#L120-L121): `corrected = raw * n_parks / (n_parks - 1 + raw)`. (4) is the derivation only.

**Normalization** to a home-PA-weighted league average of 1:

```math
f_t = \frac{p_t}{\bar{p}_{\ell}}, \qquad
\bar{p}_{\ell} = \frac{\sum_{u \in \ell} n_{H_u}\, p_u}{\sum_{u \in \ell} n_{H_u}} \qquad (6)
```

*Code:* [lines 125–127](../callup/parks.py#L125-L127); blank factors are left out of the average.

Team quality mostly cancels: team $`t`$ bats and pitches in both $`H_t`$ and $`R_t`$, so under a multiplicative model its own player effects divide out of $`r_t`$.

**Standard error** by the delta method, treating PAs as independent:

```math
\mathrm{se}_t^2 \approx \text{Var}(\log r_t) \approx \frac{s_{H}^2}{n_{H}\,\bar{y}_{H}^2} + \frac{s_{R}^2}{n_{R}\,\bar{y}_{R}^2} \qquad (7)
```

*Code:* [lines 129–131](../callup/parks.py#L129-L131) (`se_log`).

It is used for $`\log f_t`$ unadjusted. The correction in (5) actually scales errors by $`(N-1)/(N-1+r) \approx 0.93`$, so $`\mathrm{se}_t`$ is overstated by about 7%.

With equal samples of size $`n`$, two rules of thumb show how noise depends on the statistic. For wOBA ($`s \approx 0.52`$, $`\bar{y} \approx 0.36`$), and for an event rate with base rate $`p`$ (where $`s^2 = p(1-p)`$):

```math
\mathrm{se}_{\text{wOBA}} \approx \frac{\sqrt{2}\,s}{\bar{y}\,\sqrt{n}} \approx \frac{2}{\sqrt{n}} \qquad (8)
```

```math
\mathrm{se}_{\text{rate}} \approx \sqrt{\frac{2\,(1-p)}{n\,p}} \qquad (9)
```

At a typical season's 5,700 PAs per side, these give 0.027 for wOBA, 0.046 for singles ($`p = 0.144`$), 0.080 for doubles + triples ($`p = 0.052`$) and 0.105 for home runs ($`p = 0.031`$). These match the measured values in the [results](#comparing-the-candidate-statistics). Nothing computes (8) or (9).

**Minimum sample.** $`f_t`$ is left blank, not set to 1, unless $`\min(n_{H}, n_{R}) \ge n_{\min} = 2000`$, for every statistic.

*Code:* [line 122](../callup/parks.py#L122) (`enough`; it also requires both means to be positive).

### Method 2: pooled and shrunk (`home_away_shrunk`, proposed)

**Pooling.** For season $`X`$, samples from $`X-1`$ and $`X`$ are combined when the park is unchanged, and (3)–(7) are recomputed from the pooled sums. 2023 has no earlier season.

```math
H_t^{\text{pool}} = H_t^{(X-1)} \cup H_t^{(X)} \quad \text{if } k_t^{(X-1)} = k_t^{(X)} \qquad (10)
```

*Code:* [`pooled_sums`](../callup/parks.py#L135-L146), same-park condition at [line 139](../callup/parks.py#L139); called from [`prototype`, line 210](../callup/parks.py#L210).

**Why pool:**
- **Less noise.** Doubling the PAs cuts $`\mathrm{se}`$ by about $`1/\sqrt{2}`$, as (7) implies. The mean 2024 $`\mathrm{se}`$ falls from 0.028 to 0.019 for wOBA, and from 0.108 to 0.074 for home runs.
- **The cost is bias** if a park's true effect changed between seasons. The same-park condition in (10) rules out venue changes, though not renovations or league-wide changes such as rule experiments.
- **No later data:** only the earlier season is added, so the factor still uses only data available by January 1 of $`X+1`$.
- **Common practice:** published park factors also combine several seasons.[^1]
- **Evidence:** a split-half test supports pooling for all four statistics; see [Does pooling help?](#does-pooling-help)

**Shrinkage.**[^5] Each observed log factor is its true value plus sampling noise:

```math
\log f_t = \theta_t + \varepsilon_t, \qquad
\theta_t \sim (0,\ \tau^2), \qquad
\varepsilon_t \sim \mathcal{N}(0,\ \mathrm{se}_t^2) \qquad (11)
```

The best linear estimate shrinks toward 0, that is, toward $`f = 1`$:

```math
\hat{\theta}_t = w_t \log f_t, \qquad
w_t = \frac{\tau^2}{\tau^2 + \mathrm{se}_t^2} \qquad (12)
```

*Code:* [`shrink_weights`, lines 156–163](../callup/parks.py#L156-L163); saved as `shrink_weight`.

$`\tau^2`$ is estimated by the method of moments, once per season across both leagues:

```math
\hat{\tau}^2 = \max\left(0,\ \widehat{\text{Var}}(\log f) - \overline{\mathrm{se}^2}\right) \qquad (13)
```

*Code:* [`between_park_variance`, lines 149–153](../callup/parks.py#L149-L153).

The reported factor is

```math
\tilde{f}_t = \exp\left(w_t \log f_t\right) = f_t^{\,w_t} \qquad (14)
```

*Code:* [`prototype`, lines 211–212](../callup/parks.py#L211-L212): `pooled.factor ** pooled.shrink_weight`.

Example: Sugar Land's 2023 wOBA factor goes from $`f = 0.866`$ to $`0.866^{0.76} \approx 0.896`$.

**Why empirical Bayes:**
- With 30 parks, shrinking toward the common mean lowers expected squared error (the James–Stein result).[^5]
- The amount of shrinkage comes from the data ($`\hat{\tau}^2`$) and each park's sample size ($`\mathrm{se}_t`$), not from a fixed percentage.

Whether it helps for each statistic is tested in the [results](#comparing-the-candidate-statistics).

### Supplementary check: player-adjusted model (`player_adjusted`)

This model is not used for the output. It is a ridge regression on every PA in seasons $`X-1`$ and $`X`$:[^6]

```math
y_i = \mu + b_{\text{bat}(i)} + c_{\text{pit}(i)} + u_{v(i)} + e_i \qquad (15)
```

- Batter-season and pitcher-season effects are penalized with $`\lambda = 200`$ PAs; venue effects are not.
- Factors are $`(\mu + u_k)/\mu`$, normalized to all of Triple-A.
- It is the only method that compares parks across both leagues, similar in spirit to Statcast's park factors.[^7]
- **Caveats:** results depend on $`\lambda`$ (with $`\lambda = 0`$, 2023 wOBA factors move by up to 0.074). The league comparison rests on about 40 batters and 60 pitchers per season who played in both leagues. It gives no standard errors.

*Code:* [`player_adjusted`, lines 171–195](../callup/parks.py#L171-L195); the window is set at [`prototype`, line 214](../callup/parks.py#L214).

## Results

Run `python scripts/park_prototype.py` (about 75 seconds for all four statistics; add `--offline` after the first run). Per-park tables are in `data/processed/park_method_comparison.csv`.

### Comparing the candidate statistics

2023–2024. The weight $`w`$ is the median across parks. "Out-of-sample error" uses each 2023 estimate to predict the 2024 single-season ratio, which comes from separate games.

| | `woba` | `hr_rate` | `doubles_triples_rate` | `singles_rate` |
|---|---|---|---|---|
| Base rate per PA | 0.357 | 0.031 | 0.052 | 0.144 |
| Range: single-season ratio $`f`$ | 0.87–1.11 | 0.54–1.48 | 0.75–1.31 | 0.86–1.18 |
| Range: shrunk $`\tilde{f}`$ (output) | 0.90–1.09 | 0.73–1.33 | 0.84–1.15 | 0.93–1.06 |
| $`\hat{\tau}`$, single season: 2023 / 2024 | 0.048 / 0.056 | 0.145 / 0.233 | 0.097 / 0.092 | 0.017 / 0.053 |
| Mean $`\mathrm{se}`$, single season | 0.027 | 0.105 | 0.080 | 0.046 |
| $`w`$ used in output: 2023 / 2024 (pooled) | 0.76 / 0.87 | 0.66 / 0.86 | 0.60 / 0.70 | 0.12 / 0.55 |
| Year-to-year correlation of $`f`$ | 0.62 | 0.67 | 0.42 | 0.30 |
| Year-to-year slope of $`\log f`$ | 0.70 | 0.99 | 0.39 | 0.43 |
| Out-of-sample error: every park = 1 | 0.061 | 0.242 | 0.122 | 0.069 |
| Out-of-sample error: raw $`f`$ | 0.050 | **0.179** | 0.131 | 0.071 |
| Out-of-sample error: shrunk $`\tilde{f}`$ | **0.047** | 0.184 | **0.112** | **0.068** |
| Median change using 25% / 50% of games | 0.037 / 0.021 | 0.151 / 0.073 | 0.085 / 0.052 | 0.038 / 0.035 |
| Correlation of $`\tilde{f}`$ with wOBA's | 1.00 | 0.82 | 0.69 | 0.52 |
| Correlation with player-adjusted (within league) | 0.92 | 0.90 | 0.87 | 0.72 |
| 2024 highest $`\tilde{f}`$ | ABQ 1.08, RNO 1.08, STP 1.07 | STP 1.33, CLT 1.24, ABQ 1.23 | IOW 1.15, RNO 1.15, ABQ 1.14 | RNO 1.06, SL 1.05, TOL 1.04 |
| 2024 lowest $`\tilde{f}`$ | RR 0.95, SUG 0.91, SAC 0.90 | OKC 0.77, SUG 0.77, TOL 0.73 | TAC 0.89, SAC 0.88, SUG 0.86 | TAC 0.97, SUG 0.96, SAC 0.93 |

What the table shows:
- **Noise rises as events get rarer**, as (9) predicts. A home-run factor's standard error is about four times wOBA's.
- **Shrinkage improved out-of-sample error for wOBA, doubles + triples and singles, but not for home runs.** For home runs, raw factors did slightly better (0.179 versus 0.184). The year-to-year slope of 0.99 suggests the 2023 HR factors were shrunk too much: $`\hat{\tau}`$ for home runs differs a lot between seasons.
- **For doubles + triples and singles, raw single-season factors predicted 2024 worse than assuming every park is neutral.** Only the shrunk versions beat that baseline, and for singles only barely.
- **Singles parks differ little.** In 2023, $`\hat{\tau}`$ for singles is only 0.017, so $`w \approx 0.12`$ pulls almost every park to 1. The two seasons disagree on how much parks differ (0.017 versus 0.053).
- **The components overlap with wOBA only partly** (correlations 0.52–0.82), so each measures a somewhat different park effect.
- **Which statistic suits the study also depends on how factors will be used**, for example adjusting overall offense versus adjusting matching component features from #1 and #2.

### Does pooling help?

There's no 2025 AAA season to test on, so the test holds out half of 2024. Over 20 random splits of the 2024 games, each park's factor in half B is predicted from half A alone, or from half A pooled with 2023. Run `python scripts/park_pooling_check.py`.

The numbers are RMSE across parks against half B. Half B is itself noisy, so compare rows within a column rather than absolute values.

| | `woba` | `hr_rate` | `doubles_triples_rate` | `singles_rate` |
|---|---|---|---|---|
| Half A alone | 0.056 | 0.233 | 0.152 | 0.087 |
| Half A + 2023, pooled | **0.049** | **0.198** | 0.134 | **0.073** |
| Half A alone, shrunk | 0.052 | 0.214 | 0.135 | 0.076 |
| Half A + 2023, pooled and shrunk | 0.050 | 0.202 | **0.130** | 0.076 |
| Splits where pooling beat half A alone | 80% | 95% | 90% | 100% |

- **Pooling cut error by 12–17% for every statistic.** The earlier season carries information about the later season's parks, so park effects were stable enough across 2023–2024 to pool.
- **After shrinkage, pooling's gain is smaller, and for singles it disappears.** Both steps reduce noise, so they partly overlap.
- **Shrinking the pooled factors helped only for doubles + triples here.** For the other three statistics, the unshrunk pooled factors did as well or better. This bears on the shrinkage judgment call.
- **The gain here is larger than in the output.** The test pools 1.5 seasons against half a season; the output pools 2 seasons against 1.

### Sample sizes and league level

| | 2023 | 2024 |
|---|---|---|
| Median PAs per park, single season (home / road) | 5,778 / 5,800 | 5,655 / 5,699 |
| Median PAs pooled for `home_away_shrunk` (home / road) | same (no 2022 data) | 11,429 / 11,510 |

**League level (wOBA, player-adjusted):** the PCL averages 1.02 and the IL 0.99 in both seasons. Home/away factors can't show this, because each league is normalized to its own average. For example, Salt Lake (about 4,200 ft[^8]) rates 0.99 within the PCL but about 1.0 across all of AAA.

## Conclusion

**Proposed: `home_away_shrunk` factors for wOBA.** They are provisional until Anish confirms.

**Why wOBA:**
- **Least noise:** a standard error of 0.027, against 0.046–0.105 for the other statistics ([results](#comparing-the-candidate-statistics)).
- **The method works best for it:** shrunk factors had the lowest out-of-sample error (0.047, against 0.061 for treating every park as neutral), and pooling cut held-out error by 12% ([pooling test](#does-pooling-help)).
- **It covers every park feature at once**, weighted the way the study's outcome, next-season MLB wOBA, weights them.
- **It agrees with the independent check:** correlation 0.92 with the player-adjusted factors.

**Why `home_away_shrunk`:**
- Pooling lowered held-out error for every statistic.
- Shrinking single-season factors lowered out-of-sample error for 3 of 4 statistics, including wOBA.
- It is transparent, and uses only data available by January 1 of the following year.
- **Caveat:** for pooled wOBA factors, shrinkage made no difference in the split-half test (0.050 shrunk versus 0.049 unshrunk).

**How the other statistics compare:**

| Statistic | Verdict | Main evidence |
|---|---|---|
| `hr_rate` | Usable for a home-run-specific feature, pooled but not shrunk | Noisiest ($`\mathrm{se}`$ 0.105). Shrinkage raised out-of-sample error (0.184 versus 0.179 raw); pooling lowered it (0.198 versus 0.233) |
| `doubles_triples_rate` | Usable only pooled and shrunk | Raw factors did worse than assuming neutral parks (0.131 versus 0.122). Pooled and shrunk factors had the lowest held-out error (0.130) |
| `singles_rate` | Not useful as a park factor yet | Parks differ little ($`\hat{\tau}`$ = 0.017 in 2023). Shrunk factors beat neutral parks by only 0.001 out of sample (0.068 versus 0.069) |

If #1 or #2 builds home-run or extra-base-hit features, statistic-specific factors may suit them better than wOBA factors (correlations 0.69–0.82).


## Distortions to watch

- **Small samples.** One season has about 5,700 home PAs per park. Noise varies by statistic; see the [results](#comparing-the-candidate-statistics). Use pooled and shrunk factors, and leave thin samples blank.
- **Team and opponent quality** mostly cancel in the home/away ratio. They don't when a roster changes a lot during the season.
- **League differences.** With no games between the leagues, home/away factors are relative to each park's own league. A PCL park at 1.00 is not equivalent to an IL park at 1.00.
- **Altitude.** Albuquerque, Reno, Salt Lake, El Paso and Las Vegas are high; thinner air increases fly-ball distance.[^8]
- **Handedness.** Fences and wind affect left- and right-handed hitters differently.[^9] Not yet estimated.
- **Uneven schedules** break the own-park correction's balanced-schedule assumption.
- **Renovations** within the same venue ID would need a separate check.
- **Rule experiments** such as the automated ball-strike system could look like park effects if applied unevenly.[^10]

## Output: `data/processed/park_prototype.csv`

One row per `(season, home_team)`, 60 rows, following the [data contract](data-contract.md#park-prototype-output). It holds the statistic named by `--stat`; the default, `woba`, is the proposed statistic.

| Column | Meaning |
|---|---|
| `season`, `home_team` | Integer year and AAA team abbreviation (unique key) |
| `park_id` | Stats API `venue.id`, verified per game from the schedule |
| `factor` | $`\tilde{f}_t`$ from (14). Blank when either side has fewer than `--min-pa` PAs (default 2,000) |
| `reference_scale` | `1.0`: a neutral park within the league |
| `n_home_pa`, `n_away_pa` | $`n_{H}`$ and $`n_{R}`$, summed over the seasons used |
| `method`, `provisional` | For example `home_away_shrunk_woba`; always `True` for now |

The script also writes:
- `park_method_comparison.csv`: all four statistics × three methods, with the raw ratio, `se_log` and `shrink_weight`.
- `park_venue_audit.csv`: venue checks for each team-season.

All stay in ignored `data/processed/`.

**For Persons 1, 2 and 4:** don't join factors to hitter rows on `home_team`. Use each hitter's actual park exposure. For hitter $`j`$ with PAs $`P_j`$:

```math
\bar{f}_j = \frac{1}{\lvert P_j \rvert} \sum_{i \in P_j} \tilde{f}_{v(i)}, \qquad
\text{adjusted rate}_j = \frac{\text{observed rate}_j}{\bar{f}_j} \qquad (16)
```

*Code:* **not yet implemented.**

The usual shortcut $`(1 + \tilde{f})/2`$ assumes half of a hitter's PAs are at home.[^1] Use only the same season's factors, so 2024 features use 2023–2024 data and nothing from 2025.

## Checks performed

- **Home/away direction:** on invented data, an inflated park gets a factor above 1 and the others below 1. A relocated game counts at its actual park. The own-park correction recovers the true 1.2 ratio (raw ratios show 1.32).
- **Statistic scoring:** each statistic counts the right events, and an unknown statistic is rejected.
- **Plausibility:** Albuquerque, El Paso and Las Vegas rank in the top 7 of 30 for wOBA, HR and doubles + triples in both seasons. Salt Lake is the exception among high-altitude parks: it ranks 15th–27th, because its home/away ratio compares it mostly with other high PCL parks.
- **Blanks:** no real factor is blank at $`n_{\min} = 2000`$. Tests confirm that thin samples are left blank, not set to 1.0.

## Next steps

1. Confirm the proposed statistic and method with Anish, and review the other [judgment calls](#judgment-calls).
2. Decide between within-league and all-AAA factors before comparing hitters across leagues.
3. Add handedness-specific factors.
4. Use game-level bootstrap standard errors, and consider estimating $`\hat{\tau}`$ across seasons for rare events.
5. Add the hitter exposure helper, Eq. (16), once the join format is agreed.

## Appendix A: implementation map

Links point to [`callup/parks.py`](../callup/parks.py) in this PR; recheck them if the code changes. Tests are in [`tests/test_parks.py`](../tests/test_parks.py) and use invented data. Code docstrings write the season as $`Y`$.

| Eq. | Quantity | Function | Lines | Tested by |
|---|---|---|---|---|
| — | Statistic value $`y_i`$ | `STATS`, `EVENT_STATS`, `plate_appearances` | [30–36](../callup/parks.py#L30-L36), [70](../callup/parks.py#L70) | `test_statistics_score_the_right_events` |
| — | Venue $`v(i)`$ | `schedule_venues` | [40–56](../callup/parks.py#L40-L56) | `test_schedule_keeps_played_games_and_blanks_split_venues`, `test_plate_appearances_drop_missing_denominators_and_split_games` |
| — | Team's park $`k_t`$ | `home_parks` | [83–85](../callup/parks.py#L83-L85) | `test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park` |
| (1) | Home and road samples | `home_away_sums` | [103–106](../callup/parks.py#L103-L106) | `test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park` |
| (2) | Sample means | `home_away_sums`, `ratio_factors` | [107–108](../callup/parks.py#L107-L108), [116–117](../callup/parks.py#L116-L117) | (via (3)) |
| (3) | Raw ratio $`r_t`$ | `ratio_factors` | [118](../callup/parks.py#L118) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (5) | Corrected $`p_t`$ | `ratio_factors` | [120–121](../callup/parks.py#L120-L121) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (6) | Normalized $`f_t`$ | `ratio_factors` | [125–127](../callup/parks.py#L125-L127) | `test_single_season_ratio_is_normalized_and_corrects_for_own_park` |
| (7) | Standard error $`\mathrm{se}_t`$ | `ratio_factors` | [129–131](../callup/parks.py#L129-L131) | not directly tested |
| — | Minimum sample | `ratio_factors` | [122](../callup/parks.py#L122) | `test_small_samples_stay_blank_not_neutral` |
| (10) | Pooling | `pooled_sums` | [135–146](../callup/parks.py#L135-L146) | `test_pooling_uses_same_park_and_never_later_seasons` |
| (12) | Weight $`w_t`$ | `shrink_weights` | [156–163](../callup/parks.py#L156-L163) | `test_shrinkage_moves_toward_one_and_noise_only_gives_one`, `test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park` |
| (13) | Between-park variance $`\hat{\tau}^2`$ | `between_park_variance` | [149–153](../callup/parks.py#L149-L153) | `test_shrinkage_moves_toward_one_and_noise_only_gives_one` |
| (14) | Shrunk $`\tilde{f}_t`$ | `prototype`, `shrink` | [211–212](../callup/parks.py#L211-L212), [168](../callup/parks.py#L168) | `test_shrinkage_moves_toward_one_and_noise_only_gives_one` |
| (15) | Player-adjusted model | `player_adjusted` | [171–195](../callup/parks.py#L171-L195) | `test_player_model_separates_strong_team_from_neutral_parks` |
| (16) | Hitter exposure $`\bar{f}_j`$ | not yet implemented | — | — |


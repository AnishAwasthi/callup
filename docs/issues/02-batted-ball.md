# Person 2: Build and validate batted-ball features

Owner: Person 2 (handle pending). Read methodology/contract and complete the README offline exercise. Inputs: genuine `data/parquet/AAA` pitch shards with `batter, game_date, home_team, away_team, game_pk, at_bat_number, pitch_number, events, type, launch_speed, launch_angle`, frozen team metadata and the shared hitter-season cohort. Use `data/local_sample/` once permitted access is resolved; public synthetic sample is for scaffolding only.

Deliver a runnable feature script, methodology/validation note and ignored `data/processed/features_batted.csv` or `.parquet`. Schema: unique integer `player_id, season`; nullable floats `ev_mean, ev_p90, ev_max` (mph), `hard_hit_rate` (fraction), `la_mean, la_median, la_std` (degrees); integer `n_bbe, n_ev, n_la, n_hard_hit`; nullable fractions `ev_coverage, la_coverage`. State percentile interpolation and SD convention.

Filter true AAA with both opponent candidates, restrict to feature-year dates and deduplicate event keys before aggregation. Define a batted-ball event explicitly; avoid counting nonterminal/foul measurements twice. Parse raw staging strings as numbers with errors raised. Hard hit is EV ≥95 mph; its denominator is valid-EV batted balls. Missing EV/LA never becomes zero. Keep all cohort rows via a one-to-one left join, with explicit missing coverage and null stats for no measurements. Source measurements may include upstream estimates.

Dependencies: contract and permitted raw data; independent of Person 1 features. Person 4 will consume these after review. No park adjustment or modeling required.

Acceptance:

- CLI works on genuine small sample/full inputs offline; identical schema regardless of outcome class.
- Validate several real players (at least 3), showing raw selected BBE, valid measurement counts, manual arithmetic and percentile/maximum checks.
- Confirm min EV ≤mean/p90≤max where defined, hard-hit rate in [0,1], and correct zero-denominator behavior.
- Document missingness and coverage by season; no selection on `label_available`, no future fields.
- Focused duplicate/missing-value validation, passing CI and PR linked to this Issue. Commit code/docs/tests only.

# Person 3: Research park factors and build one small prototype

Owner: Person 3 (handle pending). Start immediately with cited research; full-data access is not required for the methodology comparison. Read the timing/contract docs and Savant/Stats API source references. Inspect permitted AAA home/away data and the current team metadata when available.

Deliver `docs/park-factor-research.md`, one runnable preliminary prototype and a small synthetic CI fixture. Generated prototype output is ignored `data/processed/park_prototype.csv`. Schema: `season` integer; `home_team` text and optional `park_id` integer (explicit nullable mapping); `factor` nullable numeric; `reference_scale` text (`1.0` or `100`); integer `n_home_pa, n_away_pa`; `method` text; `provisional` boolean. Key is `(home_team, season)` until a validated venue key exists; do not silently treat a team as a fixed park.

Compare at least two approaches (e.g., team home/away ratios vs multiyear regression/shrinkage), citing primary definitions/data sources. Discuss offensive environment, altitude, league composition, sample size, opponent/team quality, handedness, venue moves and schedule imbalance. Identify a permitted venue-mapping source and research rights. Prototype one narrow metric/season or a few venues, not a full park-factor system. Keep any data used in evaluation pre-prediction; no 2025 outcomes used to adjust 2024 feature-season rows.

Dependencies: research is independent; prototype needs approved data access and explicit metric choice with Anish. Coordinate output scale/key with Persons 1/2/4 before integration; prototype need not block Week 1 models.

Acceptance:

- At least two methods compared, with citations, assumptions, denominator definitions and recommendation for later work.
- One reproducible narrow prototype with minimum-sample/null handling and mapping limitations.
- Sanity checks: league/reference normalization, home/away sign and extreme values, sample-size sensitivity; no unexplained factor units.
- Note Columbus/Columbia ambiguity and any venue move/name uncertainty; unique park/team-season keys.
- Passing CI for code contributed, reviewable PR; no full park system or fabricated venue mapping.

# Shared team data

These files arrive with `git clone` or `git pull`. There is no separate data download or extraction step.

Start with `processed/hitter_seasons.csv` (926 player-seasons). The `pitches/` folder has AAA 2023/2024 and MLB 2023/2024/2025 CSVs. Python reads compressed CSVs directly: `pd.read_csv("data/shared/pitches/aaa_2024.csv.gz")`. AAA files already contain only Triple-A games; issues #1/#2 select `in_cohort=True`. MLB files include all hitters and have no cohort flag. The `local_sample/` folder has a five-player example.

Added columns include pitch type, speed, spin, movement, location and pitcher handedness. `release_speed` is mph, `release_spin_rate` is rpm, and `pfx_x`/`pfx_z` are feet from the catcher's perspective. Empty values mean missing, not zero. Compare matching seasons and pitch types. Do not use following-year MLB measurements as predictors of that year's outcome.

The original CSV columns and outcomes are preserved, and gzip decompression reproduces each verified CSV byte for byte. `manifest.json` records compressed and decompressed SHA-256 checksums, row counts and columns. This is the frozen research snapshot, not a live refresh. wOBA outcomes and venue mappings remain provisional. Source: MLB Baseball Savant and MLB Stats API. The source terms and unresolved source-specific redistribution license are documented in `docs/dataset-card.md`; publishing this copy does not grant an open-data license.

Write generated feature tables and model outputs under ignored `data/processed/`. Treat this folder as read-only. The original compressed CSV archive and Parquet copies remain preserved separately.

# Team data

## Get it with Git

The approved working snapshot is included under **`data/shared/`**. Existing teammates only need to update their clone:

```bash
git pull --no-rebase origin main
```

No separate downloader, unzipping, copying folders, Parquet, Git LFS, or API account is needed. The data are about 184 MB compressed, with each file below 50 MiB. Existing ignored data folders and generated work are not replaced. The older 14 MB GitHub Release and downloader remain for reproducibility, but they are no longer the default setup.

## Which file to use

All paths below are inside `data/shared/`:

| File | Use |
|---|---|
| `processed/hitter_seasons.csv` | All 926 study player-seasons; modeling, participation summaries, and player profiles |
| `pitches/aaa_2023.csv.gz`, `aaa_2024.csv.gz` | Actual Triple-A pitches. Issues #1/#2 select `in_cohort=True`; park research uses all rows |
| `pitches/mlb_2023.csv.gz`, `mlb_2024.csv.gz`, `mlb_2025.csv.gz` | MLB comparisons and source checks; no `in_cohort` flag |
| `teams.csv` | Starting team/venue lookup; historical mappings still need verification |
| `local_sample/hitter_seasons.csv`, `local_sample/pitches.csv` | Optional five-player practice sample; final analyses use full files |

## Open a pitch table

```python
import pandas as pd

hitters = pd.read_csv("data/shared/processed/hitter_seasons.csv", keep_default_na=False, na_values=[""])
pitches = pd.read_csv("data/shared/pitches/aaa_2024.csv.gz", keep_default_na=False, na_values=[""])
study_pitches = pitches.loc[pitches["in_cohort"].eq(True)]
```

Pandas decompresses `.csv.gz` automatically. Group features by `batter, season` and join using `batter = player_id` and matching `season`. Keep missing measurements blank. Read the practice CSVs directly; the older sample-loader script expects a different original-archive format.

For Eva's pitch analysis, select `pitch_type`, `release_speed` (mph), `release_spin_rate` (rpm), and `pfx_x`/`pfx_z` (movement in feet, catcher perspective). Handedness, location, extension, spin axis, and served wOBA components are also available. Compare matching seasons and pitch types. Following-year MLB measurements must not become predictors of that year's outcome.

## Preserve the snapshot

Treat `data/shared/` as read-only. Write generated tables, predictions and plots in ignored `data/processed/`. Old inputs under `data/pitches/` or `data/processed/` can stay; use the shared paths for the expanded input columns. The original raw archive, Parquet copies and API cache are preserved separately and are not required for ordinary team work.

`data/shared/manifest.json` records checksums for compressed files and the exact decompressed CSV bytes, row counts, columns and source version. Git's commit SHA identifies the exact snapshot; record it with experiments. CI verifies every shared data file. This is frozen historical data, not a live update of source seasons.

All original AAA values, IDs, missing positions, sample records and outcomes are unchanged from the v1 CSV release; extra pitch columns and MLB tables come from the preserved archive. Outcomes and venue mappings remain provisional. Source terms and unresolved source-specific redistribution-license status are documented in the [dataset card](dataset-card.md).

Maintainers can reproduce the shared files from the verified expanded CSV package with `python scripts/prepare_shared_data.py --source /path/to/callup-csv --output /path/to/new-output`. It verifies source checksums, compresses pitches without changing their CSV bytes, and enforces a 50 MiB per-file budget. The underlying expanded package is reproducible with `scripts/package_working_data.py`; the full source archive remains on [Google Drive](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link).

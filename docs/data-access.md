# Get the team data

Keep your existing clone. From the project folder, update the code and install the data:

```bash
git pull --no-rebase origin main
python scripts/download_working_data.py
```

Use the Python environment from the README. The downloader needs only standard Python, no GitHub account, API token, or new service. It downloads the pinned `callup-csv-v2` GitHub Release, verifies the ZIP and file checksums, and installs the CSVs in the right folders. There is no manual unzipping or folder copying.

The package is about **183 MB** compressed. It contains the existing study data plus speed, spin, movement and MLB comparison files. Cloning/pulling downloads code and the invented demo; running the second command downloads the real data. No re-clone is needed.

## Which file to open

| File | Use |
|---|---|
| `data/processed/hitter_seasons.csv` | All 926 player-seasons; starting table for modeling, participation summaries, and the player page |
| `data/pitches/aaa_2023.csv`, `aaa_2024.csv` | Actual Triple-A pitches. Issues #1/#2 select `in_cohort=True`; park research uses all rows |
| `data/pitches/mlb_2023.csv`, `mlb_2024.csv`, `mlb_2025.csv` | All archived MLB pitches for league comparisons and source checks; these files have no `in_cohort` flag |
| `data/teams.csv` | Starting team/venue lookup; historical venue mappings still need verification |
| `data/local_sample/hitter_seasons.csv`, `pitches.csv` | Optional five-player practice sample; run final analyses on full files |

## Read the CSVs

```python
import pandas as pd

hitters = pd.read_csv("data/processed/hitter_seasons.csv", keep_default_na=False, na_values=[""])
pitches = pd.read_csv("data/pitches/aaa_2023.csv", keep_default_na=False, na_values=[""])
study_pitches = pitches.loc[pitches["in_cohort"].eq(True)]
```

Group hitter features by `batter, season` and join to the study table using `batter = player_id` and the matching season. Empty cells mean missing, not zero. Existing outcomes, split assignments, pitch keys and original AAA columns are unchanged from the first CSV release. The older sample-loader command expects the original archive's different sample format; read these working CSVs directly.

For Eva's pitch analysis, the added columns include `pitch_type`, `release_speed` (mph), `release_spin_rate` (rpm), `pfx_x` and `pfx_z` (movement in feet, catcher perspective). Location, pitcher handedness, extension, spin axis and served wOBA components are also included. Match pitch types and seasons when comparing AAA with MLB. Only pre-prediction information can become a predictor; following-year MLB data are for outcomes and evaluation.

## Updating an older installation

Run the same two commands. Files already matching this release are left alone. Differing downloaded inputs are backed up under `data/incoming/backups/` before replacement. Generated feature tables, model outputs and your scripts are not changed. The installer never copies the package README or reports over repository files.

The new ZIP is saved under `data/incoming/`. The committed `working-data-lock.json` fixes the release URL and SHA-256; `reports/working-data-v2.json` lists table checksums and coverage. To use a ZIP downloaded separately, run `python scripts/download_working_data.py --archive /path/to/callup-csv.zip`.

All full data paths are ignored by Git, so the data download does not create Git conflicts. Commit code, notes and small invented fixtures only. The older `download_dataset.py` is a separate, unconfigured Hugging Face downloader and is not needed here.

## Original archive and reproduction

Anish's original compressed CSVs, Parquet copies and API cache are preserved locally and in the [Google Drive archive](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link). Teammates do not need those folders for the current tasks. This release adds columns from the preserved archive; it does not fetch new seasons or refresh outcomes. wOBA and venue mappings remain provisional; the [dataset card](dataset-card.md) records source limitations and the unresolved redistribution-license status.

Maintainers can rebuild from the unchanged original Parquet/cache folders and the frozen v1 ZIP using `python scripts/package_working_data.py --base-zip /path/to/callup-minimal-csv.zip --output data/incoming/new-build`. The script verifies all existing AAA values, keys, sample records and new CSV round trips, and records source hashes. Use a new release tag and update the lock after verifying any later package; do not replace a versioned asset in place.

# Get the team data

Keep your existing clone. From the project folder, update the code and install the data:

```bash
git pull --no-rebase origin main
python scripts/download_working_data.py
```

Use the Python environment from the README. The downloader needs only standard Python, no GitHub account, API token, or new service. It downloads the pinned `callup-csv-v1` GitHub Release, verifies the ZIP and file checksums, and installs the CSVs in the right folders. There is no manual unzipping or folder copying.

The published package is about **14 MB** compressed and 113 MB uncompressed. It contains the study table and the CSV inputs for issues #1–#5. Cloning/pulling downloads code and the invented demo; running the second command downloads the real data. No re-clone is needed.

## Which file to open

| File | Use |
|---|---|
| `data/processed/hitter_seasons.csv` | All 926 player-seasons; starting table for modeling, participation summaries, and the player page |
| `data/pitches/aaa_2023.csv`, `aaa_2024.csv` | Actual Triple-A pitches. Issues #1/#2 select `in_cohort=True`; park research uses all rows |
| `data/teams.csv` | Starting team/venue lookup; historical venue mappings still need verification |
| `data/local_sample/hitter_seasons.csv`, `pitches.csv` | Optional five-player practice sample; run final analyses on full files |

## Read the CSVs

```python
import pandas as pd

hitters = pd.read_csv("data/processed/hitter_seasons.csv", keep_default_na=False, na_values=[""])
pitches = pd.read_csv("data/pitches/aaa_2023.csv", keep_default_na=False, na_values=[""])
study_pitches = pitches.loc[pitches["in_cohort"].eq(True)]
```

Group hitter features by `batter, season` and join to the study table using `batter = player_id` and the matching season. Empty cells mean missing, not zero. The installer uses the original CSV release without changing its outcomes, split assignments, columns or values. The older sample-loader command expects the original archive's different sample format; read these working CSVs directly.

The public package does not include pitch speed, spin or movement. An expanded CSV package has been built locally with those fields and MLB comparison files, preserving every original AAA value. It is **not published**: automatic approval review rejected uploading the expanded public payload because authorization and source redistribution rights remain unresolved. The one-command installer therefore uses only the already published package. No additional data were uploaded as a workaround.

## Updating an older installation

Run the same two commands. Files already matching this release are left alone. Differing downloaded inputs are backed up under `data/incoming/backups/` before replacement. Generated feature tables, model outputs and your scripts are not changed. The installer never copies the package README or reports over repository files.

The new ZIP is saved under `data/incoming/`. The committed `working-data-lock.json` fixes the release URL and SHA-256; `reports/working-data-v2.json` records the checksums and pending publication status of the separate expanded package. To use a ZIP downloaded separately, run `python scripts/download_working_data.py --archive /path/to/callup-minimal-csv.zip`.

All full data paths are ignored by Git, so the data download does not create Git conflicts. Commit code, notes and small invented fixtures only. The older `download_dataset.py` is a separate, unconfigured Hugging Face downloader and is not needed here.

## Original archive and reproduction

Anish's original compressed CSVs, Parquet copies and API cache are preserved locally and in the [Google Drive archive](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link). Teammates do not need those folders for the current tasks. The pending expanded package adds columns from the preserved archive; it does not fetch new seasons or refresh outcomes. wOBA and venue mappings remain provisional; the [dataset card](dataset-card.md) records source limitations and the unresolved redistribution-license status.

Maintainers can rebuild from the unchanged original Parquet/cache folders and the frozen v1 ZIP using `python scripts/package_working_data.py --base-zip /path/to/callup-minimal-csv.zip --output data/incoming/new-build`. The script verifies all existing AAA values, keys, sample records and new CSV round trips, and records source hashes. Use a new release tag and update the lock after verifying any later package; do not replace a versioned asset in place.

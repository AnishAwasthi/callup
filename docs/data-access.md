# Working with the data

## Download the CSV working data

The [GitHub Release](https://github.com/AnishAwasthi/callup/releases/tag/callup-csv-v1) includes [callup-minimal-csv.zip](https://github.com/AnishAwasthi/callup/releases/download/callup-csv-v1/callup-minimal-csv.zip): about **14 MB** compressed and **113 MB** unzipped. It is the working package for issues #1–#5.

Unzip it to get `callup-csv/`. Copy its `data/` contents into the cloned project's `data/` folder, or use the unzipped folder as your working directory. Retain the included README, `manifest.json`, and `reports/cohort_preparation.json`. The manifest records individual table hashes; the release's `.sha256` attachment records the ZIP hash.

| Input | Use |
|---|---|
| `data/processed/hitter_seasons.csv` | All 926 study player-seasons; primary input for issues #4–#5 |
| `data/pitches/aaa_2023.csv`, `data/pitches/aaa_2024.csv` | Actual Triple-A pitches; issues #1–#2 select `in_cohort=True`, while issue #3 uses all rows |
| `data/teams.csv` | Issue #3's starting team/venue lookup; verify historical mappings |
| `data/local_sample/hitter_seasons.csv`, `data/local_sample/pitches.csv` | Optional five-player practice sample, with 6,617 pitches; do not append it to full data |
| `reports/cohort_preparation.json` | Issue #5's totals check |

Read the reduced CSVs directly, for example:

```python
import pandas as pd

hitters = pd.read_csv("data/processed/hitter_seasons.csv", keep_default_na=False, na_values=[""])
pitches = pd.read_csv("data/pitches/aaa_2023.csv", keep_default_na=False, na_values=[""])
cohort_pitches = pitches.loc[pitches["in_cohort"].eq(True)]
```

Aggregate hitter features by `batter, season`, then attach them to all 926 study rows using `batter = player_id` and matching `season`. Empty cells mean missing, not zero. Outcomes and the existing split are unchanged; wOBA and venue mappings remain provisional.

The older `offline_example.py --sample-dir` loader expects the original archive's sample schema and does not load this reduced package. No API/cache download or Parquet conversion is needed for normal CSV analysis. Keep the CSV inputs and generated data out of Git.

## Original archive on Google Drive

The remaining setup, sample-loader, and source-rebuilding instructions on this page apply to the **original larger archive**, retained for audits and additional research. They are not required for the reduced CSV package.

Anish has uploaded the dataset to the [team's shared Google Drive folder](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link). The prepared package is about **1.9 GB**. Download the complete package, unzip it if needed, and copy these folders into your cloned project's `data/` folder:

| Folder | What it contains |
|---|---|
| `raw/` | Original daily pitch downloads, saved as compressed CSV (`.csv.gz`) |
| `cache/` | Saved MLB API responses, so analysis can run without fetching them again |
| `parquet/` | Compact copies of the pitch tables for Python analysis |
| `processed/` | The prepared table of 926 player-seasons, in CSV and Parquet |
| `local_sample/` | A smaller real-data sample for checking your code |

Keep the folder structure: for example, `parquet/AAA/` should become `data/parquet/AAA/`, not `data/release/parquet/AAA/`. Keep `checksums.json` and `provenance.json` with your downloaded package; they identify its contents and preparation version. The trusted file hashes are also committed in `reports/release_checksums.json`, with the manifest hash in `reports/release_summary.json`. Compare against those records if checking a transfer.

GitHub includes a separate **invented-data demo** in `data/sample/`. That demo checks installation; use the downloaded data for baseball analysis. The full data folders are excluded from Git. The uploaded package includes an older README; use this repository's current README for setup.

## Open a table and check your setup

Follow the installation steps in the README, then run:

```bash
python scripts/offline_example.py --sample-dir data/local_sample
```

Expect 13 player-seasons and 14,067 Triple-A pitches. This checks that the sample loads and its player IDs match.

For an Excel overview, open `data/processed/hitter_seasons.csv`. For Python:

```python
import pandas as pd

hitters = pd.read_parquet("data/processed/hitter_seasons.parquet")
print(hitters.head())
```

You can start from the supplied tables. You do not need to rerun ingestion or conversion. If you need to rebuild them from the preserved downloads:

```bash
python scripts/prepare_storage.py
python scripts/prepare_analysis.py
```

These use the downloaded archive and saved API responses; they preserve the original compressed CSV files.

## Calculate features from pitch data

Process the daily files one at a time rather than loading the full archive into memory. **The `AAA` folder includes Single-A games too.** Use our team metadata to select actual Triple-A games:

```python
from pathlib import Path
import pandas as pd
from callup.ingest import derive_levels
from callup.statsapi import StatsAPI

api = StatsAPI(offline=True)
for season in (2023, 2024):
    teams = api.team_level_candidates(season)
    for path in sorted(Path("data/parquet/AAA").glob(f"{season}-*.parquet")):
        day = pd.read_parquet(path, columns=[
            "batter", "game_date", "home_team", "away_team", "events", "launch_speed"
        ])
        day = day.loc[derive_levels(day, teams).eq("AAA")]
        day["launch_speed"] = pd.to_numeric(day["launch_speed"], errors="raise")
        # Aggregate your assigned statistics by batter and season here.
```

Pitch-table IDs are integers; other source columns retain their original text. Convert measurement columns to numbers before arithmetic. Missing measurements stay missing. Build features for every player-season in the prepared table, not just the few players you manually validate.

## Background and sharing status

The downloads come from Baseball Savant's CSV exports and the MLB Stats API. The entry point is `scripts/ingest_statcast.py`; this project does not use PyBaseball. Coverage, preparation and known gaps are recorded in the [dataset card](dataset-card.md). The analysis design and table columns are in [methodology.md](methodology.md) and [data-contract.md](data-contract.md).

GitHub Releases provides the reduced CSV working package; Google Drive retains the original archive. No Hugging Face dataset has been published, and `scripts/download_dataset.py` is a Hugging Face downloader, not a downloader for these packages. If we use Hugging Face later, set `dataset-lock.json` to the exact dataset commit and checksum manifest before using it.

The data uploads do not change the source's license: no open redistribution license or written permission has been recorded. Keep that unresolved status separate from where the files are stored. See the [MLB data notice](https://gdx.mlb.com/components/copyright.txt) and [source terms](https://www.mlb.com/official-information/terms-of-use).

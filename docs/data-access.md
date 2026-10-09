# Working with the data

## Download from Google Drive

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

Google Drive is the current handoff. No Hugging Face dataset has been published, and `scripts/download_dataset.py` is a Hugging Face downloader, not a Google Drive downloader. If we use Hugging Face later, set `dataset-lock.json` to the exact dataset commit and checksum manifest before using it.

The Drive upload does not change the source's license: no open redistribution license or written permission has been recorded. Keep that unresolved status separate from where the files are stored. See the [MLB data notice](https://gdx.mlb.com/components/copyright.txt) and [source terms](https://www.mlb.com/official-information/terms-of-use).

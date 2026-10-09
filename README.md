# Callup

Given a hitter's Triple-A season, how well can we predict their performance in MLB the following year?

Triple-A is the highest level of minor-league baseball. We are starting with 2023–2024 hitters who had at least 150 plate appearances (batting turns). Our target is next-season MLB **wOBA**, a batting statistic that weights different ways of reaching base, for players with at least 75 MLB plate appearances. These outcome values still need checking before we draw conclusions.

## Get started

Install Python 3.13, then run these commands in Terminal:

```bash
git clone https://github.com/AnishAwasthi/callup.git
cd callup
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/offline_example.py
```

On Windows, use `py -3.13 -m venv .venv` and `.venv\Scripts\Activate.ps1` instead of the two environment commands above.

The example uses **invented data** included in GitHub to check that your setup works. It is not for baseball analysis.

## Get the real data

Download the [CSV working-data ZIP](https://github.com/AnishAwasthi/callup/releases/download/callup-csv-v1/callup-minimal-csv.zip) (about **14 MB**, or 113 MB unzipped) from the [GitHub Release](https://github.com/AnishAwasthi/callup/releases/tag/callup-csv-v1). It contains the files needed for issues #1–#5.

Unzip it to get `callup-csv/`. Copy the contents of its `data/` folder into this project's `data/` folder, or work directly inside `callup-csv/`. Keep the package's README, `manifest.json`, and `reports/cohort_preparation.json` for instructions and checking totals.

Start with **`data/processed/hitter_seasons.csv`**: 926 rows, one per player and Triple-A season. You can open it in Excel. For pitch analysis, use `data/pitches/aaa_2023.csv` and `aaa_2024.csv`; these are already filtered to actual Triple-A games. Issues #1–#2 should select `in_cohort=True`; issue #3 uses all pitch rows and `data/teams.csv`. Join hitter features using `batter = player_id` and matching `season`. Keep missing measurements and outcomes blank.

The two CSVs in `data/local_sample/` are an **optional five-player practice sample**. Read these CSVs directly; the older `offline_example.py --sample-dir` loader expects the original archive's schema. Run final analyses on the full files.

[Data instructions](docs/data-access.md) cover loading and verification. The original **1.9 GB** archive remains in the [shared Google Drive folder](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link) for source audits and additional research.

## Team work

The five [GitHub issues](https://github.com/AnishAwasthi/callup/issues) cover basic hitting statistics, batted-ball statistics, ballpark research, a first prediction model, and summaries of who plays in MLB the following year.

Build features for **all players in the study**; manually check 3–5 players to verify your calculations. Work on a separate branch and open a pull request for Anish to review. Commit code and notes; keep downloaded data and generated data files out of Git.

When you need them, [study notes](docs/methodology.md) explain the analysis choices and [column definitions](docs/data-contract.md) explain the prepared table.

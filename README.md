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

**The team data is included in the repository.** Already have a clone? From that project folder, run:

```bash
git pull --no-rebase origin main
```

That adds `data/shared/` automatically, including speed, spin, movement, and MLB comparison data. No re-clone, separate download, folder copying, Git LFS, or Parquet setup is needed. The initial data transfer is about **184 MB**. Your existing data folders and generated results are left alone.

Start with **`data/shared/processed/hitter_seasons.csv`**: 926 rows, one per player and Triple-A season. You can open it in Excel.

For pitch analysis, use `data/shared/pitches/aaa_2023.csv.gz` and `aaa_2024.csv.gz`. These are compressed CSVs; Python opens them directly:

```python
import pandas as pd
pitches = pd.read_csv("data/shared/pitches/aaa_2024.csv.gz")
```

The AAA files contain actual Triple-A games. Issues #1/#2 select `in_cohort=True`; park research uses all AAA rows and `data/shared/teams.csv`. MLB 2023–2025 comparison files are in the same pitch folder. Join hitter features using `batter = player_id` and matching `season`. Missing values stay missing.

The CSVs in `data/shared/local_sample/` are an optional five-player practice sample. [Data instructions](docs/data-access.md) describe the fields and checksums. Write generated features and model outputs under ignored `data/processed/`; treat `data/shared/` as read-only. The full original archive remains preserved separately.

## Team work

The initial five [GitHub issues](https://github.com/AnishAwasthi/callup/issues) cover basic hitting statistics, batted-ball statistics, ballpark research, a first prediction model, and summaries of who plays in MLB the following year.

Build features for **all players in the study**; manually check 3–5 players to verify your calculations. Work on a separate branch and open a pull request for Anish to review. Commit code and notes; keep generated data files and new source downloads out of Git. The approved frozen inputs in `data/shared/` are already tracked.

When you need them, [study notes](docs/methodology.md) explain the analysis choices and [column definitions](docs/data-contract.md) explain the prepared table.

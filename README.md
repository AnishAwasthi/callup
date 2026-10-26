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
python scripts/download_working_data.py
python scripts/offline_example.py
```

On Windows, use `py -3.13 -m venv .venv` and `.venv\Scripts\Activate.ps1` instead of the two environment commands above.

The example uses **invented data** included in GitHub to check that your setup works. It is not for baseball analysis.

## Get the real data

The setup command above downloads the team's CSV files from a fixed GitHub Release, checks them, and puts them in `data/`. **No folder copying, Parquet setup, or Google Drive download is needed for team tasks.**

Already have a clone? Keep it. From that project folder, run:

```bash
git pull --no-rebase origin main
python scripts/download_working_data.py
```

Use the same Python environment as before. The command can be repeated; it leaves current files alone and backs up older inputs before updating them. It does not change your generated feature tables or code.

Start with **`data/processed/hitter_seasons.csv`**: 926 rows, one per player and Triple-A season. You can open it in Excel. For pitch analysis, use `data/pitches/aaa_2023.csv` and `aaa_2024.csv`; these already contain only actual Triple-A games. Issues #1–#2 select `in_cohort=True`; issue #3 uses all AAA rows and `data/teams.csv`. Join using `batter = player_id` and matching `season`. Keep missing values blank.

The same pitch CSVs now include **speed, spin, and movement**. Matching `mlb_2023.csv`, `mlb_2024.csv`, and `mlb_2025.csv` files are in `data/pitches/` for MLB comparisons. The CSVs in `data/local_sample/` are an optional five-player practice sample. Read CSVs directly; run final analyses on full files.

[Data instructions](docs/data-access.md) describe the columns and reproducible download. Large data stay outside Git history; cloning or pulling alone gets code and the invented sample. The original archive is preserved for source audits.

## Team work

The initial five [GitHub issues](https://github.com/AnishAwasthi/callup/issues) cover basic hitting statistics, batted-ball statistics, ballpark research, a first prediction model, and summaries of who plays in MLB the following year.

Build features for **all players in the study**; manually check 3–5 players to verify your calculations. Work on a separate branch and open a pull request for Anish to review. Commit code and notes; keep downloaded data and generated data files out of Git.

When you need them, [study notes](docs/methodology.md) explain the analysis choices and [column definitions](docs/data-contract.md) explain the prepared table.

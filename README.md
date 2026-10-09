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

Download the full dataset from the team's [shared Google Drive folder](https://drive.google.com/drive/folders/1WRWRfMqxtrhO1dX38Dc5pqrttF2wyu-W?usp=share_link). The complete package is about **1.9 GB**; it is kept outside GitHub.

Unzip the package if needed. Copy its `raw`, `cache`, `parquet`, `processed`, and `local_sample` folders into this project's `data/` folder. Then check the real sample:

```bash
python scripts/offline_example.py --sample-dir data/local_sample
```

Start with **`data/processed/hitter_seasons.csv`**: 926 rows, one per player and Triple-A season. You can open it in Excel. For pitch-level analysis, use the Parquet files in `data/parquet/`; Parquet is a compact table format read with Python. Keep the original compressed CSV files in `data/raw/`.

The `AAA` pitch folder includes other minor-league levels, so filter to actual Triple-A games before calculating features. [Data instructions](docs/data-access.md) explain the files and filtering. You do not need to download the data again from MLB or use Hugging Face.

## Team work

The five [GitHub issues](https://github.com/AnishAwasthi/callup/issues) cover basic hitting statistics, batted-ball statistics, ballpark research, a first prediction model, and summaries of who plays in MLB the following year.

Build features for **all players in the study**; manually check 3–5 players to verify your calculations. Work on a separate branch and open a pull request for Anish to review. Commit code and notes; keep downloaded data and generated data files out of Git.

When you need them, [study notes](docs/methodology.md) explain the analysis choices and [column definitions](docs/data-contract.md) explain the prepared table.

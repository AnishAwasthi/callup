# Sample for checking setup

These players and pitches are **invented**. They let you check installation and player-ID matching without downloading the full dataset. They are not for baseball analysis.

Run `python scripts/offline_example.py` from the project folder. The example has 8 player-seasons and 96 pitches and needs no network connection.

The real team data arrives with Git in `data/shared/`, including a five-player practice sample under `data/shared/local_sample/`. No data-download command is needed. Read those CSVs directly; the older sample loader expects a different original-archive format. See the main README for the one-command update instructions.

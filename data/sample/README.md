# Sample for checking setup

These players and pitches are **invented**. They let you check installation and player-ID matching without downloading the full dataset. They are not for baseball analysis.

Run `python scripts/offline_example.py` from the project folder. The example has 8 player-seasons and 96 pitches and needs no network connection.

For real data, run `python scripts/download_working_data.py`. It installs the complete working CSV package and a five-player practice sample under `data/local_sample/`. Read those CSVs directly; the older sample loader expects a different original-archive format. See the main README for the two-command update workflow.

# Sample for checking setup

These players and pitches are **invented**. They let you check installation and player-ID matching without downloading the full dataset. They are not for baseball analysis.

Run `python scripts/offline_example.py` from the project folder. The example has 8 player-seasons and 96 pitches and needs no network connection.

The Google Drive package also contains a **real-data sample**: 13 player-seasons and 14,067 Triple-A pitches. Copy its `local_sample/` folder into `data/`, then run `python scripts/offline_example.py --sample-dir data/local_sample`. See the main README for the Drive link and setup steps.

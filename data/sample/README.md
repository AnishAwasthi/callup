# Offline demo

These **synthetic** invented players and pitches test installation, joins and the shared contract. They are not evidence about baseball, representative data, or a sample for model evaluation. `data_kind=synthetic` is carried in every row. Counts/labels are invented independently of the 96 toy pitches.

Run `python scripts/offline_example.py` with no network or API cache.

The genuine 13-player-season sample and 14,067 AAA pitches are generated at `data/local_sample/` by `scripts/prepare_analysis.py`. They remain outside Git pending source redistribution permission; use `--sample-dir data/local_sample` on the preparation machine. Public access to an endpoint does not establish a redistribution license. See `docs/data-access.md`.

# Person 2: Calculate batted-ball stats

Summarize how hard each Triple-A hitter hits the ball and the angles at which it leaves the bat.

## Data

Download the Google Drive package using the [README](https://github.com/AnishAwasthi/callup#readme). Use `data/parquet/AAA/`, saved team information, and `data/processed/hitter_seasons.csv`. Try `data/local_sample/` first. You can start without waiting for Person 1.

## Work

- Calculate average, 90th-percentile, and maximum **exit velocity** (ball speed off the bat, in mph).
- Calculate **hard-hit rate**: the share of measured batted balls hit at least 95 mph.
- Calculate average, median, and standard deviation of **launch angle** (the ball's angle off the bat).
- Report how many batted balls have usable measurements. Missing values stay missing, rather than becoming zero.
- Use actual Triple-A games in 2023–2024, define which events count as batted balls, and avoid counting repeated or foul-ball records twice.

## Deliver

A runnable script, `data/processed/features_batted.csv` (or Parquet), and a short calculation note. Include **all 926 player-seasons**, leaving unavailable measurements blank. See the [required output columns](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#batted-ball-output). Person 4 can use the results after review.

## Check before submitting

Run on the full study data and manually check **3–5 players**. Show their batted balls, measurement counts, and calculations. Check valid ranges, duplicate events, and missing values; explain measurement coverage by season.

Open a pull request linked to this issue, with GitHub checks passing. Keep generated data out of Git.

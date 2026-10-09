# Person 1: Calculate basic hitting stats

Calculate useful hitting statistics for every player-season in our Triple-A study.

## Data

Download [callup-minimal-csv.zip](https://github.com/AnishAwasthi/callup/releases/download/callup-csv-v1/callup-minimal-csv.zip) from the [GitHub Release](https://github.com/AnishAwasthi/callup/releases/tag/callup-csv-v1) and unzip it to get `callup-csv/`.

Use the files inside the unzipped `callup-csv` folder: `data/pitches/aaa_2023.csv`, `data/pitches/aaa_2024.csv`, and `data/processed/hitter_seasons.csv`. Filter pitches to `in_cohort=True`, calculate PA, strikeout, walk, swing, and contact rates per player-season, and join to all 926 study rows using `batter = player_id` and matching `season`.

The two CSVs in `data/local_sample/` are an optional five-player practice sample; check calculations there, then run on the full files. Keep missing measurements and outcomes blank rather than replacing them with zero. You can start independently of the other tasks.

## Work

- Calculate plate appearances (completed batting turns), strikeout rate, walk rate, swing rate, and contact rate.
- Include **all 926 player-seasons**, even when a player has no next-season MLB outcome.
- The pitch CSVs are already filtered to actual Triple-A games in 2023–2024; select `in_cohort=True` and match each player's season.
- Count each batting turn once. Explain what counts as a swing or contact, and leave rates blank when there is nothing to divide by.

## Deliver

A runnable script, `data/processed/features_basic.csv` (or Parquet), and a short calculation note. Include the counts behind each rate. See the [required output columns](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#basic-hitting-output).

## Check before submitting

Run on the full study data, then manually check **3–5 players**, including a Columbus hitter. Show the arithmetic and explain differences from saved API totals. Check duplicate rows, zero denominators, rates between 0 and 1, and contacts no greater than swings.

Open a pull request linked to this issue, with GitHub checks passing. Commit code and notes; keep generated data out of Git.

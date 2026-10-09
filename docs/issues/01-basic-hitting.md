# Person 1: Calculate basic hitting stats

Calculate useful hitting statistics for every player-season in our Triple-A study.

## Data

Download the Google Drive package using the [README](https://github.com/AnishAwasthi/callup#readme). Use `data/parquet/AAA/`, the saved team information in `data/cache/`, and `data/processed/hitter_seasons.csv`. Try `data/local_sample/` first. You can start independently of the other tasks.

## Work

- Calculate plate appearances (completed batting turns), strikeout rate, walk rate, swing rate, and contact rate.
- Include **all 926 player-seasons**, even when a player has no next-season MLB outcome.
- Use actual Triple-A games from each player's 2023 or 2024 season. The `AAA` folder also includes Single-A games; follow the data instructions to filter them.
- Count each batting turn once. Explain what counts as a swing or contact, and leave rates blank when there is nothing to divide by.

## Deliver

A runnable script, `data/processed/features_basic.csv` (or Parquet), and a short calculation note. Include the counts behind each rate. See the [required output columns](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#basic-hitting-output).

## Check before submitting

Run on the full study data, then manually check **3–5 players**, including a Columbus hitter. Show the arithmetic and explain differences from saved API totals. Check duplicate rows, zero denominators, rates between 0 and 1, and contacts no greater than swings.

Open a pull request linked to this issue, with GitHub checks passing. Commit code and notes; keep generated data out of Git.

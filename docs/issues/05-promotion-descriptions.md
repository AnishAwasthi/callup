# Person 5: Summarize who plays in MLB the following year

Describe which Triple-A hitters play in MLB next season, and how much usable information we have about them.

## Data

Download the Google Drive package using the [README](https://github.com/AnishAwasthi/callup#readme). Use **all 926 rows** in `data/processed/hitter_seasons.csv`. You can start independently of the other four tasks.

## Work

- Count three groups separately: players with any next-season MLB batting appearances, those with at least 75 appearances, and those with usable preliminary wOBA values.
- Compare their Triple-A statistics and missing measurements.
- Make **2–4 clear plots**, such as group counts by season, Triple-A playing time by MLB participation, and missing-value rates.
- Include nonparticipants. No batting appearances next season does not mean a player never reached MLB; participants can include returning MLB players.
- Distinguish player-season rows from unique people: one hitter can contribute two seasons.

## Deliver

A runnable script or notebook and `docs/promotion-analysis.md`. Save plots and tables under `data/processed/promotion/`; explain the sample, data version, and limitations. See the [output columns](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#participation-summary-output).

## Check before submitting

Match counts to `reports/cohort_preparation.json`, including 926 player-seasons and 239 meeting the MLB playing-time threshold. Cover every group, keep missing values blank, and make the plots reproducible.

Open a pull request linked to this issue, with GitHub checks passing. Keep generated outputs out of Git.

Optional: try a simple participation model using Triple-A information and the agreed split. The plots are the required work; they do not establish why players were promoted.

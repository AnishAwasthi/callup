# Person 4: Build and test a first prediction model

Build a simple starting point for predicting next-season MLB batting performance, measured by wOBA. The current outcome values and results are preliminary.

## Data

Download `data/processed/hitter_seasons.csv` from the Google Drive package using the [README](https://github.com/AnishAwasthi/callup#readme). Start with its Triple-A counts: plate appearances, hits, at-bats, walks, strikeouts, and home runs. You can begin before Persons 1 and 2 finish.

## Work

- Build an **average baseline**: predict the average training-set wOBA for every test player.
- Build **Ridge regression**, a simple regression model that limits overly large coefficients.
- Follow the existing `split` column: train on its 2023 training rows and test on its 2024 test rows. Verify that no player appears in both sets.
- Fit and evaluate only rows with `label_available=True`. Use Triple-A information as predictors, without future MLB information or player IDs. Do not invent missing outcomes.
- Learn missing-value replacements and scaling from training data only. Keep test data out of model tuning.

## Deliver

A runnable script, a short results note, `data/processed/model_metrics.json`, and `data/processed/predictions.csv`. Compare MAE (average absolute error), RMSE, and R². See the [output details](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#model-output) for columns, settings, and reproducibility requirements.

## Check before submitting

Run both models on the full prepared table. Test for overlapping players and test data influencing preprocessing. Explain that results apply to players with usable MLB outcomes, not every Triple-A hitter. Ask Anish before changing the outcome or split.

Open a pull request linked to this issue, with GitHub checks passing. Keep model outputs out of Git.

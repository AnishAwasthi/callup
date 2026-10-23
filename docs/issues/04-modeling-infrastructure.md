# Person 4: Build and test a first prediction model

Build a simple starting point for predicting next-season MLB batting performance, measured by wOBA. The current outcome values and results are preliminary.

## Data

Download [callup-minimal-csv.zip](https://github.com/AnishAwasthi/callup/releases/download/callup-csv-v1/callup-minimal-csv.zip) from the [GitHub Release](https://github.com/AnishAwasthi/callup/releases/tag/callup-csv-v1) and unzip it to get `callup-csv/`.

Use `data/processed/hitter_seasons.csv` inside the unzipped `callup-csv` folder: its existing Triple-A counts, provisional next-season MLB wOBA, and frozen `split` are enough to evaluate the training-average baseline and Ridge model using available labels. Keep missing outcomes blank rather than replacing them with zero. You can begin before Persons 1 and 2 finish.

## Work

- Build an **average baseline**: predict the average training-set wOBA for every test player.
- Build **Ridge regression**, a simple regression model that limits overly large coefficients.
- Follow the existing `split` column: train on its 2023 training rows and test on its 2024 test rows. Verify that no player appears in both sets.
- Fit and evaluate only rows with `label_available=True`. Use Triple-A information as predictors, without future MLB information or player IDs. Do not invent missing outcomes.
- Learn missing-value replacements and scaling from training data only. Keep test data out of model tuning.
- Verify the prepared MLB wOBA values used as outcomes. Start with 3–5 players and compare against an independent season-level reference, recording its source and season. Extend the comparison to eligible rows where reference values are available; explain differences and mark unresolved cases. The original archive linked in the README can support source investigations. Coordinate interpretation or outcome changes with Anish.

## Deliver

A runnable script, a short outcome-validation note (with comparisons saved under ignored `data/processed/`), a short results note, `data/processed/model_metrics.json`, and `data/processed/predictions.csv`. Compare MAE (average absolute error), RMSE, and R². See the [output details](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#model-output) for columns, settings, and reproducibility requirements.

## Check before submitting

Confirm that outcome checks are documented and Anish has reviewed unresolved differences before treating model results as reliable. Keep exploratory results preliminary while this review is ongoing. Run both models on the full prepared table. Test for overlapping players and test data influencing preprocessing. Explain that results apply to players with usable MLB outcomes, not every Triple-A hitter. Ask Anish before changing the outcome or split.

Open a pull request linked to this issue, with GitHub checks passing. Keep model outputs out of Git.

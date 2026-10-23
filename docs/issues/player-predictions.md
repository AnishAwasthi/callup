# Show predictions in the player profile

Add next-season MLB wOBA predictions to the existing player page and make clear what the numbers mean.

## When to start

Wait for #7's player page and #4's saved model outputs. #4 includes outcome verification; unresolved results must remain clearly marked preliminary. This does not need to wait for #5, which describes participation rather than generating performance predictions.

The first version can use #4's original basic-count model. Predictions using the combined features can follow after #8 and a documented model rerun. Always identify which model/data version is displayed.

## Work

- Load saved `data/processed/predictions.csv` and `model_metrics.json`; join predictions by player ID, feature season, and model. Do not retrain a model every time someone selects a player.
- Show predicted next-season MLB wOBA beside the training-average baseline, with the outcome year and a plain explanation of wOBA. These are not projected home-run totals or a full batting line.
- For historical test players, show predicted versus observed wOBA and the difference. Keep actual outcomes visibly distinct from predictions, and distinguish test results from training results.
- Explain that the model was evaluated on players with sufficient MLB playing time. This projection is not a probability of being called up.
- If predictions or outcomes are missing, keep the profile usable and show unavailable values rather than inventing numbers or uncertainty ranges.

## Deliver

An updated prediction panel, a simple table-loading interface that accepts later model versions, and short instructions for supplying a new saved model run. Make sure displayed metrics belong to that same run.

## Check before submitting

Match several displayed values against the saved files. Check repeated players across seasons, missing predictions, multiple model rows, and preliminary-outcome labels. Confirm that reported test performance uses held-out players.

Open a pull request linked to this issue, with GitHub checks passing. Keep generated predictions and model files out of Git.

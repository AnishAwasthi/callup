# Combine the hitting statistics into one table

Create one reliable player-season table that the model and player-profile page can both use.

## When to start

The finished version needs reviewed outputs from #1 and #2. The joining code can begin with the existing study table and the first available feature output, but do not call the full table complete until both are integrated.

## Work

- Write `scripts/combine_features.py` to join `data/shared/processed/hitter_seasons.csv`, `features_basic.csv`, and `features_batted.csv` by `player_id` and `season`.
- Keep all 926 study rows, including players without next-season MLB outcomes. A missing feature must stay missing rather than removing the player or becoming zero.
- Reject duplicate keys and unexpected player-seasons. Keep original reference counts separate from newly calculated counts; do not silently overwrite columns with the same name.
- Preserve the existing outcome flags and training/test assignments. Keep outcome fields clearly separate from the list of inputs allowed in a model.
- Include a small feature list with readable labels, units, and groups for the player page. Use #7's display-settings format, agreeing it with that task's owner first. Later approved features should use the same joining approach.

## Deliver

`data/processed/player_features.csv`, the combining script, shared display settings, and one documented command to rebuild the table. Treat this CSV as the shared input for the enriched model and profile page; keep it out of Git.

## Check before submitting

Confirm one row per player-season, exactly the same study keys and split values, and no lost players. Manually compare several merged rows with their source tables. Check that duplicate inputs fail clearly and missing features stay missing.

Open a pull request linked to this issue, with GitHub checks passing. Generating the table does not by itself retrain the model; coordinate that handoff with the owner of #4.

# Add a readable player summary with Hugging Face

Turn a player's verified statistics and model prediction into a short, understandable report in the player-profile page.

## When to start

This comes after #9, once the player page, prediction format, and displayed statistics are stable. Use the same player-season keys and model/data versions as the page.

## Work

- Write a small script that gives a Hugging Face language model a structured set of player facts: statistics, any calculated comparisons, the saved prediction, and data limitations.
- Generate three short sections: **Strengths**, **Concerns**, and **MLB outlook**. Describe the evidence without inventing injuries, mechanics, scouting observations, or reasons for promotion. If a comparison is not supplied, do not claim above/below average performance.
- Use a suitably licensed model downloaded from Hugging Face and run locally. Generate and save reports before the demo; the app should load them without making paid API calls. Choose a model that works on the available hardware; no paid service or GPU rental.
- Match each report to the player, season, and data/model versions. Rebuild it when those inputs change. Keep the numerical statistics visible beside the text.
- Show a clear unavailable message if the report is missing or fails the factual checks. The language model explains the statistical model's prediction; it does not create the prediction itself.

## Deliver

A reproducible generation script, saved reports in ignored `data/processed/player_reports/`, and a summary section in the app. Record the model revision, prompt, and generation settings.

## Check before submitting

Review reports for several players. Check every number and comparison against the supplied facts, include preliminary-outcome limitations, and reject unsupported claims. Confirm that changing the player cannot show another player's report and that stale reports are not displayed as current.

Open a pull request linked to this issue, with GitHub checks passing. Commit code and an invented-data example, not real player reports or model weights.

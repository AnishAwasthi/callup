# Build a simple player-profile page

Create the first Streamlit page where someone can choose a Triple-A hitter and season and understand his hitting statistics.

## Start

This can begin now. Follow the [README](https://github.com/AnishAwasthi/callup#readme) to install the CSV working data. Start with `data/processed/hitter_seasons.csv`; you do not need to wait for the other feature or model tasks.

## Work

- Add a player selector and season selector. Use player ID and season to find the right record, even when names repeat.
- Show the player's name, season, and available Triple-A counts, with plain-language labels and definitions. Display missing measurements as unavailable, rather than zero.
- Build the page around one data-loading function and a small display-settings file containing approved statistics, labels, units, and groups.
- Start with the existing table, then use `data/processed/player_features.csv` from #8 when it becomes available. Newly approved features should appear by updating the table and display settings, without rewriting the page layout. Keep historical MLB outcomes separate from Triple-A statistics.
- Leave room for the prediction panel added in #9. Until its saved inputs exist, show “Prediction not available yet” and keep the rest of the page working.

## Deliver

A working `app.py`, the display settings, and short launch instructions (`streamlit run app.py`). Add the required dependency. Keep the data source configurable so teammates can use their downloaded files.

## Check before submitting

Try several players and both seasons. Check that changing a selection changes the statistics, missing values display correctly, and the page works before optional feature/prediction files exist. Demonstrate that an added approved feature appears without a new page component. Use invented data for committed examples and keep real data out of Git.

Open a pull request linked to this issue, with GitHub checks passing.

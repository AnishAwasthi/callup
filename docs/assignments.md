# Week 1 assignment links

Use your role placeholder until names/handles are supplied. Each Issue includes the input paths, output schema, dependencies, validation and acceptance criteria.

| Role | GitHub Issue |
|---|---|
| Person 1 | [Basic hitting stats](https://github.com/AnishAwasthi/callup/issues/1) |
| Person 2 | [Batted-ball stats](https://github.com/AnishAwasthi/callup/issues/2) |
| Person 3 | [How ballparks affect hitting](https://github.com/AnishAwasthi/callup/issues/3) |
| Person 4 | [First prediction model](https://github.com/AnishAwasthi/callup/issues/4) |
| Person 5 | [Who plays in MLB the following year](https://github.com/AnishAwasthi/callup/issues/5) |

Follow the README to install the project and download the CSV working data using the README. Find your task in the table above, work on a branch, and open a pull request for Anish to review. If you need help with branches or forks, see `docs/git-workflow.md`. The invented sample in GitHub is only for checking setup.

## Next implementation tasks

| Task | When to start |
|---|---|
| [#7: Player-profile page](https://github.com/AnishAwasthi/callup/issues/7) | Now, using the existing hitter-season CSV |
| [#8: Combined hitting table](https://github.com/AnishAwasthi/callup/issues/8) | Can scaffold now; finish after #1 and #2 are reviewed |
| [#9: Predictions in the profile](https://github.com/AnishAwasthi/callup/issues/9) | After #7 and #4; does not require #5 |
| [#10: Hugging Face player summary](https://github.com/AnishAwasthi/callup/issues/10) | After #9 and stable player statistics |

MLB wOBA outcome verification is part of #4; feature checks remain in #1 and #2, and participation/count checks remain in #5. The enriched model and profile will share #8's `data/processed/player_features.csv`; rebuild predictions before presenting newly added features as model inputs.

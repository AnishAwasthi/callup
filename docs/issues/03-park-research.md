# Person 3: Research how ballparks affect hitting

Recommend a practical way to account for Triple-A ballpark differences, then try one small example. A **park factor** estimates whether a park increases or reduces a hitting statistic compared with a typical park.

## Start

Download [callup-minimal-csv.zip](https://github.com/AnishAwasthi/callup/releases/download/callup-csv-v1/callup-minimal-csv.zip) from the [GitHub Release](https://github.com/AnishAwasthi/callup/releases/tag/callup-csv-v1) and unzip it to get `callup-csv/`.

Begin with research; you do not need the dataset yet. For the small prototype, agree on a statistic with Anish and use `data/pitches/aaa_2023.csv`, `data/pitches/aaa_2024.csv`, and `data/teams.csv` inside the unzipped `callup-csv` folder. Use **all pitch rows**, including hitters outside the study cohort; compare park-factor methods and verify historical venue mappings before treating the team metadata as a final venue map. Keep missing measurements and outcomes blank rather than replacing them with zero.

## Work

- Compare **at least two methods**, such as home-versus-away ratios and a model combining several seasons. Cite original sources and recommend a starting approach.
- Explain likely distortions, including small samples, team/opponent quality, league differences, altitude, handedness, uneven schedules, and venue changes.
- Find a documented, usable source linking teams to ballparks. A team can change venues; Columbus and Columbia also share the `COL` abbreviation.
- Try one statistic for one season or a few parks, using information available by January 1 of the following year.

## Deliver

`docs/park-factor-research.md`, a runnable prototype, and `data/processed/park_prototype.csv`. Explain whether a neutral park is **1.0 or 100**. See the [output columns](https://github.com/AnishAwasthi/callup/blob/main/docs/data-contract.md#park-prototype-output); coordinate the format with Persons 1, 2, and 4.

## Check before submitting

Check home/away direction, extreme factors, and sensitivity to sample size. Explain uncertain venue mappings and leave results blank when data are insufficient.

Open a pull request linked to this issue, with a small invented-data test and GitHub checks passing. Keep generated data out of Git. Other tasks can proceed during this research.

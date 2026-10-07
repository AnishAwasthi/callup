# Callup first meeting reference

## What we are building

We study how Triple-A hitter performance translates to next-season MLB performance. AAA is the highest minor-league level. A call-up is a move to MLB, but our initial outcome window measures next-season MLB batting participation, including returning MLB players. We observe outcomes only for players who participate, and useful playing-time samples for fewer players. Team decisions and unobserved information make this selection important; correction is a research question, not an automatic cure.

Initial contract approved by Anish: AAA ≥150 PA in 2023–2024; prediction January 1 of Y+1; next regular-season MLB wOBA with ≥75 PA. Player-disjoint 2023 training / 2024 test: remove from training all players in the 2024 pool. Do not use later MLB data or outcome-availability flags as predictors. `docs/methodology.md` explains the design, verified old counts and provisional outcomes.

The old README totals are 2,529 across hitting **and pitching**, with 638 clearing workload thresholds. Hitters alone: 1,385/353 across 2023–2025, including incomplete cached 2026 outcomes. Our initial 2023–2024 hitter pool is 926 with 239 provisional next-season outcomes. Split: 208 training pool rows / 62 labels; 456 test rows / 125 labels; 262 excluded overlap rows / 52 labels. Do not advertise all 239 as training examples. Archive-vs-official PA differs in 464 AAA rows and 104 participating MLB rows; investigate before final outcome claims. Availability/coverage and split counts are in `reports/cohort_preparation.json`. Pitchers are outside Week 1 scope.

## Baseball primer

PA (plate appearance) is a completed batting turn; AB (at-bat) excludes walks and some other outcomes. K=strikeout; BB=walk. K% and BB% divide their counts by PA. A pitch is not a PA. EV (exit velocity) is how hard a batted ball travels, in mph; launch angle is in degrees. Hard hit means EV ≥95 mph. Missing EV is not a weakly hit zero. wOBA weights different offensive events; xwOBA is an estimated measure and is not our selected target. Park factors describe how venues influence outcomes and must name their reference scale.

## Assignments and handoffs

| Owner | Week 1 work | Deliverable / validation |
|---|---|---|
| Person 1 | Basic hitting features | PA, K%, BB%, swing/contact rates; one row/player-season; validate 3–5 players |
| Person 2 | Batted-ball features | EV mean/p90/max, hard-hit rate, LA summaries; coverage denominators; validate several players |
| Person 3 | Park-factor research | Compare methods, venue mapping risks, one small prototype and sanity checks |
| Person 4 | Modeling infrastructure | Mean baseline and Ridge pipeline, metrics, frozen split, no player overlap; use preliminary AAA counts until features arrive |
| Person 5 | Promotion descriptions | Class balance, missingness, summaries, 2–4 plots; distinguish participation vs eligibility; optional simple logistic regression |
| Anish | Methodology, review, integration, blockers | Resolve provisional outcomes, source permissions and team data access; review PRs |

Issue bodies in `docs/issues/` specify inputs, outputs, dependencies and acceptance criteria. Handles can be attached later. No one needs to wait for another person's full feature suite to create scaffolding: Persons 1/2 have raw-defined pitch inputs, Person 3 can begin cited research, and Persons 4/5 have the preliminary player-season contract.

## Setup exercise (10–15 minutes)

1. Each teammate clones the public repository and follows README install instructions using Python 3.13.
2. Run `python scripts/offline_example.py`, `pytest` and `ruff check .`. Expect eight **synthetic** player-seasons and 96 toy pitches in the demo; this verifies setup, not analysis.
3. Open `docs/data-contract.md`, find your Issue and make a task branch using `docs/git-workflow.md`.
4. Create a brief methodology note or script scaffold, commit it, push the branch and open a draft PR. Add the issue link and ask Anish for review.
5. For genuine work, use the approved data release and locked downloader when available. On Anish's preparation machine, `data/local_sample/` and `data/processed/` are ready. Public teammate data access is still blocked by source permission; do not describe the handoff as complete until a permitted release/access route is tested.

## Suggested agenda (45 minutes)

5 min project/baseball overview; 10 min cohort, timing, selection and provisional outcome caveats; 15 min setup exercise; 10 min assignment/dependency review; 5 min agree first PR review and unblock data access. GitHub basics: Issues are tasks, branches are isolated work, commits are checkpoints, PRs request review, and main is the integrated code. Bring blockers into the Issue/PR rather than inventing undocumented definitions in a private file.

Current data access recommendation: preserve original gzip CSV; use Parquet for repeated scans. Hugging Face is a potential free distribution route, but do not upload until source redistribution is cleared and namespace/visibility/capacity are chosen. See `docs/data-access.md` for the exact steps. No full models, final feature suite, park system or Streamlit app are built in preparation.

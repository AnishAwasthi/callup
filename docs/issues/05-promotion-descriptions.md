# Person 5: Describe next-season MLB participation and outcome selection

Owner: Person 5 (handle pending). Inputs: all rows of `data/processed/hitter_seasons.csv` and shared contract/methodology; preliminary AAA counts are sufficient. Start script/notebook scaffolding with the public synthetic demo, then use permitted genuine starter/full data. Do not wait for final features or labels to begin.

Deliver a runnable descriptive script or notebook plus `docs/promotion-analysis.md`; generated tables/figures go into ignored `data/processed/promotion/`. Summary schema: `season`, `outcome_status`, integer `n_rows, n_players, n_reached, n_eligible, n_label_available`, numeric `participation_rate, eligibility_rate, label_rate`. Missingness schema: `season, field, n_missing, n_total, missing_rate`. Document player-season vs unique-player denominators.

Describe class balance, preliminary feature distributions and missingness by season and selection state. Make 2–4 clear plots, for example participation/eligibility counts by season, missingness heatmap, AAA PA distribution by participation and usable-label share. Separate next-season MLB batting PA>0 from MLB PA≥75 and from a reconstructible provisional wOBA. `not_observed` is window-specific, not never promoted in a career. Include all pool rows; never restrict descriptions to labeled players.

Optional simple logistic regression predicts next-season participation with only pre-outcome AAA features. If attempted, use the agreed player-disjoint split, train-only preprocessing and appropriate class-balance metrics; don't infer causal promotion effects or selection-correction validity. Descriptive plots are the required work, logistic regression is optional.

Dependencies: shared starter table and permitted access only; independent of Persons 1–4. Coordinate selection definitions with Anish. No final selection correction or app required.

Acceptance:

- Counts reconcile to shared report (926 pool, 239 workload-eligible; other counts from regenerated report), with unique-player counts separately stated.
- Missing values remain missing; zero MLB PA represents no observed batting participation, not an imputed outcome.
- 2–4 readable, labeled plots and summaries on genuine data, with sample/revision/caveats identified; synthetic runs labeled as demo only.
- Key uniqueness and all-class inclusion checks, reproducible command, passing CI and focused PR linked to this Issue.

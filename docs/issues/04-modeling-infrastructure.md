# Person 4: Add mean baseline and Ridge modeling infrastructure

Owner: Person 4 (handle pending). Inputs: `data/processed/hitter_seasons.csv`, approved provisional label flags and frozen splits, then optional reviewed Person 1/2 feature outputs. Read `docs/methodology.md` and `docs/data-contract.md`. Download the prepared hitter-season table from the shared Google Drive package using the README. `data/sample/` contains invented data for checking setup only.

Deliver a training/evaluation CLI, a feature allowlist/config, experiment note and ignored outputs `data/processed/model_metrics.json` and `predictions.csv`. Start with available preliminary `aaa_pa, aaa_hits, aaa_ab, aaa_bb, aaa_k, aaa_hr`; later feature integration is optional. Implement mean-of-training-label baseline and Ridge in a scikit-learn Pipeline with train-fitted imputation/scaling. Explicitly record dependencies and random seeds.

Prediction schema: integer `player_id, season, outcome_year`; `split` text; numeric `y_true, y_pred`; `model` text; code/data revision identifiers. Metrics JSON: model, feature list, training/test row and player counts, MAE/RMSE/R², data/code revision, seed, null/drop diagnostics. Report R² as undefined for insufficient/constant targets rather than inventing a number.

Use 2024 cohort rows as test; exclude all 2023 players present in the 2024 pool. Split before filtering to available labels. Assert no train/test player overlap. Fit only `label_available=True`, disclose provisional outcomes, and keep MLB playing time/flags/dates, labels, IDs, provenance and split out of predictors. If tuning, use player-grouped CV within training only; no test tuning, no full-cohort scaler fit. Retain excluded rows in diagnostic counts. Explain generalization is to held-out eligible participants, not all AAA players.

Dependencies: approved contract and preliminary real labels sufficient to start; final Person 1/2 outputs are not blocking. Independent of a finished park system. Ask Anish before any selection-corrected model, outcome change or split change.

Acceptance:

- Runnable mean baseline and Ridge only; no final model or Streamlit app.
- Tests that detect player overlap and preprocessing leakage; explicit allowlist rejects post-outcome fields.
- Reproducible metrics/predictions with counts, revisions and limitations; no outcome imputation.
- Real small-sample smoke test distinguished from meaningful full-cohort evaluation, passing CI and reviewable PR.

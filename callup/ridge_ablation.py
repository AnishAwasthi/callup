"""Controlled Ridge ablation using frozen provisional labels and training-only folds."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GridSearchCV, GroupKFold

from callup.contract import FEATURE_INPUTS
from callup.modeling import RIDGE_ALPHAS, labeled_partitions, regression_metrics, ridge_pipeline

BATTED_PREDICTORS = ["ev_mean", "ev_p90", "ev_max", "hard_hit_rate", "la_mean", "la_median", "la_std"]
BATTED_COUNTS = ["n_bbe", "n_ev", "n_la", "n_hard_hit"]
BATTED_COVERAGE = ["ev_coverage", "la_coverage"]
BATTED_COLUMNS = BATTED_PREDICTORS + BATTED_COUNTS + BATTED_COVERAGE
CONFIGURATIONS = {"six_counts": list(FEATURE_INPUTS), "plus_batted": [*FEATURE_INPUTS, *BATTED_PREDICTORS]}
KEYS = ["player_id", "season"]


def join_features(study, features):
    """Validate full key coverage and measurement semantics, preserving every study field."""
    labeled_partitions(study)
    if set(features.columns) != set(KEYS + BATTED_COLUMNS):
        raise ValueError("Unexpected batted feature schema")
    if features[KEYS].isna().any().any() or features.duplicated(KEYS).any():
        raise ValueError("Missing or duplicate batted keys")
    if not all(pd.api.types.is_integer_dtype(features[k]) for k in KEYS):
        raise ValueError("Batted keys must be integers")
    if set(map(tuple, features[KEYS].to_numpy())) != set(map(tuple, study[KEYS].to_numpy())):
        raise ValueError("Batted keys must cover exactly the full study")
    if set(study.columns) & set(BATTED_COLUMNS):
        raise ValueError("Study already contains batted columns")
    for column in BATTED_COLUMNS:
        if not pd.api.types.is_numeric_dtype(features[column]):
            raise ValueError("Batted features must be numeric")
        if np.isinf(features[column].to_numpy(dtype=float, na_value=np.nan)).any():
            raise ValueError("Infinite batted feature")
    for column in BATTED_COUNTS:
        values = features[column].dropna()
        if values.lt(0).any() or values.mod(1).ne(0).any():
            raise ValueError("Invalid batted counts")
    if features[BATTED_COUNTS].notna().nunique(axis=1).gt(1).any():
        raise ValueError("Partial missing count coverage")
    for numerator, denominator in [("n_ev", "n_bbe"), ("n_la", "n_bbe"), ("n_hard_hit", "n_ev")]:
        if features[numerator].gt(features[denominator]).any():
            raise ValueError("Batted count exceeds denominator")
    for rate, numerator, denominator in [("hard_hit_rate", "n_hard_hit", "n_ev"),
                                          ("ev_coverage", "n_ev", "n_bbe"),
                                          ("la_coverage", "n_la", "n_bbe")]:
        expected = features[numerator].div(features[denominator].replace(0, np.nan))
        if not np.allclose(features[rate].to_numpy(dtype=float, na_value=np.nan),
                           expected.to_numpy(dtype=float, na_value=np.nan), equal_nan=True, atol=1e-12):
            raise ValueError("Batted rate inconsistent with measurement counts")
    for column in BATTED_PREDICTORS:
        minimum = 2 if column == "la_std" else 1
        count = features["n_ev" if column.startswith("ev_") or column == "hard_hit_rate" else "n_la"]
        if not features[column].notna().eq(count.ge(minimum).fillna(False)).all():
            raise ValueError("Measurement missingness inconsistent with counts")
    for column in ["ev_mean", "ev_p90", "ev_max"]:
        if not features[column].dropna().between(0, 130).all():
            raise ValueError("Invalid exit velocity")
    for column in ["la_mean", "la_median"]:
        if not features[column].dropna().between(-90, 90).all():
            raise ValueError("Invalid launch angle")
    if features.la_std.dropna().lt(0).any():
        raise ValueError("Negative launch-angle standard deviation")
    if (features.ev_mean.gt(features.ev_max) | features.ev_p90.gt(features.ev_max)).any():
        raise ValueError("Exit velocity summary exceeds maximum")
    joined = study.merge(features, on=KEYS, how="left", validate="one_to_one", sort=False)
    pd.testing.assert_frame_equal(joined[study.columns].reset_index(drop=True), study.reset_index(drop=True))
    labeled_partitions(joined)
    return joined


def coverage_tables(frame):
    """Missingness by full season/split/label status; measurement coverage is pooled."""
    missing, pooled = [], []
    groups = [("all", "all", frame)]
    for by in ["season", "split", "label_available"]:
        groups.extend((by, str(value), group) for value, group in frame.groupby(by))
    for split, group in frame.groupby("split"):
        groups.append(("labeled_split", str(split), group.loc[group.label_available]))
    for by, value, group in groups:
        for column in BATTED_COLUMNS:
            missing.append({"group_by": by, "group": value, "feature": column, "n_rows": len(group),
                            "n_missing": int(group[column].isna().sum()),
                            "missing_fraction": float(group[column].isna().mean())})
        total = float(group.n_bbe.sum())
        pooled.append({"group_by": by, "group": value, "n_rows": len(group),
                       "n_bbe": int(total), "n_ev": int(group.n_ev.sum()), "n_la": int(group.n_la.sum()),
                       "ev_coverage": float(group.n_ev.sum() / total) if total else None,
                       "la_coverage": float(group.n_la.sum() / total) if total else None})
    return pd.DataFrame(missing), pd.DataFrame(pooled)


def select_ablation_features(frame, predictors):
    if not predictors or len(set(predictors)) != len(predictors) or set(predictors) - set(FEATURE_INPUTS + BATTED_PREDICTORS):
        raise ValueError("Predictors outside ablation allowlist")
    result = frame[list(predictors)]
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in result.dtypes):
        raise ValueError("Predictors must be numeric")
    if np.isinf(result.to_numpy(dtype=float)).any():
        raise ValueError("Infinite predictor")
    return result


def grouped_folds(train):
    n = min(5, train.player_id.nunique())
    if n < 2:
        raise ValueError("At least two training players required")
    return list(GroupKFold(n_splits=n, shuffle=False).split(train, groups=train.player_id))


def tune(train, predictors, folds):
    pipeline = ridge_pipeline()
    # Entirely unmeasured columns are dropped in each fit, never filled with fictitious zeros.
    pipeline.set_params(imputer=SimpleImputer(strategy="median", keep_empty_features=False))
    search = GridSearchCV(pipeline, {"ridge__alpha": list(RIDGE_ALPHAS)}, cv=folds,
                          scoring={"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error"},
                          refit="mae", n_jobs=1, error_score="raise")
    search.fit(select_ablation_features(train, predictors), train.mlb_woba)
    return search


def spread(predictions):
    predictions = np.asarray(predictions, dtype=float)
    return {"mean": float(predictions.mean()), "std_population": float(predictions.std()),
            "min": float(predictions.min()), "max": float(predictions.max()),
            "p10": float(np.quantile(predictions, .1)), "p90": float(np.quantile(predictions, .9))}


def paired_bootstrap(oof, repetitions=4000, seed=4):
    """Conditional paired player bootstrap of fixed nested OOF predictions, not refitted models."""
    wide = oof.pivot(index=["player_id", "season", "y_true"], columns="model", values="y_pred").reset_index()
    groups = [np.flatnonzero(wide.player_id.eq(pid)) for pid in sorted(wide.player_id.unique())]
    errors = {name: wide.y_true.to_numpy() - wide[name].to_numpy() for name in CONFIGURATIONS}
    rng = np.random.default_rng(seed)
    changes = {"mae": [], "rmse": []}
    for _ in range(repetitions):
        indices = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        for metric in changes:
            scores = {name: float(np.abs(e[indices]).mean()) if metric == "mae" else
                      float(np.sqrt(np.square(e[indices]).mean())) for name, e in errors.items()}
            changes[metric].append(scores["plus_batted"] - scores["six_counts"])
    return {"seed": seed, "repetitions": repetitions, "unit": "player_id",
            "interpretation": "Conditional on fixed nested OOF predictions; excludes training-refit and fold-assignment uncertainty; not a definitive significance test",
            "delta_plus_minus_six_percentile_95": {
                metric: np.quantile(values, [.025, .975]).tolist() for metric, values in changes.items()}}


def experiment(frame):
    """Use identical outer/inner splits for both configurations; holdout is predicted last."""
    train, test = labeled_partitions(frame)
    train, test = train.reset_index(drop=True), test.reset_index(drop=True)
    if train.player_id.nunique() < 3:
        raise ValueError("Nested comparison requires at least three training players")
    folds = grouped_folds(train)
    predictions, fold_rows, assignments, grid_rows = [], [], [], []
    models = {}

    def record_folds(rows, splits, scope):
        for fold, (fit, valid) in enumerate(splits):
            assert not set(rows.iloc[fit].player_id) & set(rows.iloc[valid].player_id)
            for role, indices in [("fit", fit), ("validation", valid)]:
                for i in indices:
                    assignments.append({"scope": scope, "fold": fold, "role": role,
                                        "player_id": int(rows.iloc[i].player_id), "season": int(rows.iloc[i].season)})

    def grid_results(search, model, scope):
        for i, params in enumerate(search.cv_results_["params"]):
            for fold in range(search.n_splits_):
                grid_rows.append({"model": model, "scope": scope, "fold": fold,
                                  "alpha": float(params["ridge__alpha"]),
                                  "mae": float(-search.cv_results_[f"split{fold}_test_mae"][i]),
                                  "rmse": float(-search.cv_results_[f"split{fold}_test_rmse"][i])})

    record_folds(train, folds, "outer_and_final_tuning")
    # Nested outer validation estimates the whole alpha-selection procedure.
    for outer, (fit, valid) in enumerate(folds):
        fitting, validation = train.iloc[fit], train.iloc[valid]
        inner = grouped_folds(fitting)
        record_folds(fitting, inner, f"outer_{outer}_inner")
        for name, predictors in CONFIGURATIONS.items():
            search = tune(fitting, predictors, inner)
            grid_results(search, name, f"outer_{outer}_inner")
            y_pred = search.predict(select_ablation_features(validation, predictors))
            metrics = regression_metrics(validation.mlb_woba, y_pred)
            fold_rows.append({"fold": outer, "model": name, "n_fit": len(fitting),
                              "n_validation": len(validation),
                              "alpha": float(search.best_params_["ridge__alpha"]), **metrics})
            p = validation[["player_id", "season", "outcome_year", "split", "mlb_woba"]].rename(columns={"mlb_woba": "y_true"}).copy()
            predictions.append(p.assign(model=name, evaluation="nested_training_oof", fold=outer, y_pred=y_pred))
    # Both final tuning searches see only the same 62 training labels and the same five folds.
    fitted_models = {}
    for name, predictors in CONFIGURATIONS.items():
        search = tune(train, predictors, folds)
        grid_results(search, name, "final_tuning")
        fitted_models[name] = search
        fitted = search.best_estimator_
        models[name] = {
            "predictors": predictors, "selected_alpha": float(search.best_params_["ridge__alpha"]),
            "selection_cv_mae": float(-search.cv_results_["mean_test_mae"][search.best_index_]),
            "selection_cv_rmse_mean_folds": float(-search.cv_results_["mean_test_rmse"][search.best_index_]),
            "selection_score_caveat": "Alpha selected on these folds; use nested OOF for comparison",
            "fitted_medians": {p: None if np.isnan(v) else float(v) for p, v in zip(predictors, fitted['imputer'].statistics_, strict=True)},
            "retained_predictors": fitted['imputer'].get_feature_names_out().tolist(),
            "standardized_coefficients": fitted['ridge'].coef_.tolist(),
            "intercept": float(fitted['ridge'].intercept_),
        }
    for name, search in fitted_models.items():
        y_pred = search.predict(select_ablation_features(test, CONFIGURATIONS[name]))
        p = test[["player_id", "season", "outcome_year", "split", "mlb_woba"]].rename(columns={"mlb_woba": "y_true"}).copy()
        predictions.append(p.assign(model=name, evaluation="exploratory_holdout", fold=-1, y_pred=y_pred))
        models[name]["exploratory_holdout"] = regression_metrics(test.mlb_woba, y_pred)
        models[name]["exploratory_holdout_prediction_spread"] = spread(y_pred)
    predictions = pd.concat(predictions, ignore_index=True)
    oof = predictions.loc[predictions.evaluation.eq("nested_training_oof")]
    for name in CONFIGURATIONS:
        selected = oof.loc[oof.model.eq(name)]
        models[name]["nested_oof"] = regression_metrics(selected.y_true, selected.y_pred)
        models[name]["nested_oof_prediction_spread"] = spread(selected.y_pred)
    fold_rows = pd.DataFrame(fold_rows)
    paired = fold_rows.pivot(index="fold", columns="model", values=["mae", "rmse"])
    deltas = pd.DataFrame({"fold": paired.index,
                           **{f"delta_{metric}_plus_minus_six": paired[metric]["plus_batted"] - paired[metric]["six_counts"] for metric in ["mae", "rmse"]}}).reset_index(drop=True)
    summary = {
        "target": "Frozen original provisional mlb_woba; no standard-wOBA replacement",
        "primary_comparison": "Nested player-grouped training-only OOF; holdout exploratory because inspected previously",
        "counts": {s: {"rows": len(g), "players": g.player_id.nunique(), "labeled": int(g.label_available.sum())} for s, g in frame.groupby('split')},
        "settings": {"alpha_grid": list(RIDGE_ALPHAS), "selection": "Mean fold MAE; ties first ascending alpha",
                     "outer_folds": len(folds), "inner_folds": "min(5, training players)", "shuffle": False,
                     "preprocessing": "Training-fit median imputation, drop all-missing fit columns, StandardScaler, Ridge SVD with intercept",
                     "additional_predictors_fixed_before_evaluation": BATTED_PREDICTORS,
                     "diagnostics_not_predictors": BATTED_COUNTS + BATTED_COVERAGE},
        "models": models, "observed_training_spread": spread(train.mlb_woba),
        "paired_outer_folds": {metric: {"mean_delta": float(deltas[f'delta_{metric}_plus_minus_six'].mean()),
                                       "std_delta_sample": float(deltas[f'delta_{metric}_plus_minus_six'].std()),
                                       "improved_folds": int(deltas[f'delta_{metric}_plus_minus_six'].lt(0).sum())} for metric in ["mae", "rmse"]},
        "uncertainty": paired_bootstrap(oof),
    }
    return summary, predictions, fold_rows, deltas, pd.DataFrame(assignments), pd.DataFrame(grid_rows)

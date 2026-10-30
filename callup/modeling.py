"""Training-average baseline for the frozen, provisional hitter outcomes."""
from __future__ import annotations

import math

from callup.contract import FEATURE_INPUTS, validate

RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0)


def regression_metrics(y_true, y_pred):
    """Calculate unweighted metrics; undefined R² is represented by None."""
    actual, predicted = list(y_true), list(y_pred)
    if not actual or len(actual) != len(predicted):
        raise ValueError("Metrics require nonempty, equally sized inputs")
    if not all(math.isfinite(value) for value in [*actual, *predicted]):
        raise ValueError("Metrics require finite values")
    errors = [value - prediction for value, prediction in zip(actual, predicted, strict=True)]
    squared_error = math.fsum(error**2 for error in errors)
    mean = math.fsum(actual) / len(actual)
    total_variation = math.fsum((value - mean)**2 for value in actual)
    reason = "insufficient_targets" if len(actual) < 2 else "constant_targets" if total_variation == 0 else None
    return {
        "mae": math.fsum(abs(error) for error in errors) / len(actual),
        "rmse": math.sqrt(squared_error / len(actual)),
        "r2": None if reason else 1 - squared_error / total_variation,
        "r2_undefined_reason": reason,
    }


def labeled_partitions(frame):
    """Check the full frozen cohort before selecting available labels."""
    validate(frame)  # Includes player overlap before filtering unavailable labels.
    if frame.data_kind.nunique() != 1:
        raise ValueError("Use exactly one data kind; never mix real and synthetic rows")
    expected_season = frame.split.map({"train": 2023, "test": 2024, "excluded_overlap": 2023})
    if not frame.season.eq(expected_season).all():
        raise ValueError("Unexpected season for frozen split")
    test_players = set(frame.loc[frame.split.eq("test"), "player_id"])
    excluded_players = set(frame.loc[frame.split.eq("excluded_overlap"), "player_id"])
    if not excluded_players.issubset(test_players):
        raise ValueError("Excluded overlap players must appear in the full test cohort")
    available = frame.loc[frame.label_available]
    if not available.mlb_woba.map(math.isfinite).all():
        raise ValueError("Available labels must be finite")
    train = available.loc[available.split.eq("train")]
    test = available.loc[available.split.eq("test")]
    if train.empty or test.empty:
        raise ValueError("Baseline requires available training and test labels")
    return train, test


def training_average_baseline(frame, *, data_version, code_version, code_dirty):
    """Validate the full cohort, fit available training labels, evaluate test labels."""
    train, test = labeled_partitions(frame)
    training_mean = math.fsum(train.mlb_woba) / len(train)
    predictions = test[["player_id", "season", "outcome_year", "split"]].copy()
    predictions["model"] = "training_average"
    predictions["y_true"] = test.mlb_woba
    predictions["y_pred"] = training_mean
    predictions["data_version"] = data_version
    predictions["code_version"] = code_version
    predictions["code_dirty"] = code_dirty
    diagnostics = {}
    for split in ("train", "test", "excluded_overlap"):
        rows = frame.loc[frame.split.eq(split)]
        labeled = rows.loc[rows.label_available]
        diagnostics[split] = {
            "n_rows": len(rows), "n_players": rows.player_id.nunique(),
            "n_labeled_rows": len(labeled), "n_labeled_players": labeled.player_id.nunique(),
            "n_unavailable_labels": int((~rows.label_available).sum()),
            "n_missing_outcomes": int(rows.mlb_woba.isna().sum()),
            "n_dropped_from_evaluation": len(rows) if split == "excluded_overlap" else len(rows) - len(labeled),
        }
    metrics = {
        "model": "training_average", "predictors": [], "training_mean": training_mean,
        "evaluation_split": "test",
        **regression_metrics(predictions.y_true, predictions.y_pred),
        "counts": diagnostics, "data_version": data_version, "code_version": code_version,
        "code_dirty": code_dirty, "data_kind": frame.data_kind.iloc[0],
        "random_seed": None, "settings": {"weighting": "unweighted", "tuning": "none"},
        "preliminary": True, "outcome_validation": "independent_validation_pending",
        "evaluation_scope": "full_input_table_available_test_labels",
    }
    return metrics, predictions


def select_features(frame, predictors=FEATURE_INPUTS):
    """Select only explicitly approved numeric predictors; permit missing features."""
    import numpy as np
    import pandas as pd

    predictors = list(predictors)
    if not predictors or len(set(predictors)) != len(predictors) or set(predictors) - set(FEATURE_INPUTS):
        raise ValueError("Predictors must be unique columns from the approved AAA allowlist")
    if set(predictors) - set(frame.columns):
        raise ValueError("Missing predictor columns")
    features = frame[predictors]
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in features.dtypes):
        raise ValueError("Predictors must be numeric")
    if np.isinf(features.to_numpy(dtype=float)).any():
        raise ValueError("Infinite predictor value")
    return features


def ridge_pipeline():
    """A fresh Pipeline for every CV fold and the final training-only refit."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(fit_intercept=True, solver="svd")),
    ])


def fit_ridge(train):
    """Select alpha by deterministic grouped CV on labeled training rows only."""
    from sklearn.model_selection import GridSearchCV, GroupKFold

    n_groups = train.player_id.nunique()
    if n_groups < 2:
        raise ValueError("Ridge tuning requires at least two training players")
    search = GridSearchCV(
        ridge_pipeline(), {"ridge__alpha": list(RIDGE_ALPHAS)},
        scoring="neg_mean_absolute_error",
        cv=GroupKFold(n_splits=min(5, n_groups), shuffle=False),
        refit=True, n_jobs=1, error_score="raise",
    )
    search.fit(select_features(train), train.mlb_woba, groups=train.player_id)
    return search


def compare_models(frame, *, data_version, code_version, code_dirty):
    """Evaluate both models on identical available test rows."""
    import pandas as pd
    import sklearn

    train, test = labeled_partitions(frame)
    search = fit_ridge(train)  # No test information enters selection or refitting.
    baseline, baseline_predictions = training_average_baseline(
        frame, data_version=data_version, code_version=code_version, code_dirty=code_dirty,
    )
    predictions = baseline_predictions.copy()
    predictions["model"] = "ridge"
    predictions["y_pred"] = search.predict(select_features(test))
    fitted = search.best_estimator_
    ridge = {
        **baseline, "model": "ridge", "predictors": list(FEATURE_INPUTS),
        **regression_metrics(predictions.y_true, predictions.y_pred),
        "selected_alpha": float(search.best_params_["ridge__alpha"]),
        "settings": {
            "weighting": "unweighted", "solver": "svd", "fit_intercept": True,
            "imputation": "training_median; all-missing fold columns use zero",
            "scaling": "StandardScaler", "alpha_grid": list(RIDGE_ALPHAS),
            "cv": "GroupKFold", "n_splits": search.n_splits_, "shuffle": False,
            "groups": "player_id", "scoring": "neg_mean_absolute_error",
            "selection": "lowest mean fold MAE; ties choose first alpha in grid",
        },
        "cv_results": [
            {"alpha": float(params["ridge__alpha"]), "mean_validation_mae": float(-score)}
            for params, score in zip(search.cv_results_["params"], search.cv_results_["mean_test_score"], strict=True)
        ],
        "fitted_preprocessing": {
            "imputer_statistics": fitted.named_steps["imputer"].statistics_.tolist(),
            "scaler_mean": fitted.named_steps["scaler"].mean_.tolist(),
            "scaler_scale": fitted.named_steps["scaler"].scale_.tolist(),
        },
    }
    del ridge["training_mean"]
    metrics = {
        "preliminary": True, "outcome_validation": "independent_validation_pending",
        "models": {"training_average": baseline, "ridge": ridge},
        "sklearn_version": sklearn.__version__,
    }
    return metrics, pd.concat([baseline_predictions, predictions], ignore_index=True)

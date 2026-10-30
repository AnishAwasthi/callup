"""Training-average baseline for the frozen, provisional hitter outcomes."""
from __future__ import annotations

import math

from callup.contract import validate


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


def training_average_baseline(frame, *, data_version, code_version, code_dirty):
    """Validate the full cohort, fit available training labels, evaluate test labels."""
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

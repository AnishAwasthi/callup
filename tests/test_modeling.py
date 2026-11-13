import json
import math
import sys

import numpy as np
import pandas as pd
import pytest

from callup.contract import FEATURE_INPUTS
from callup.modeling import (
    RIDGE_ALPHAS,
    compare_models,
    fit_ridge,
    regression_metrics,
    ridge_pipeline,
    select_features,
    training_average_baseline,
)
from scripts import train_baseline, train_models


@pytest.fixture
def cohort():
    rows = []
    for player, split, label in [(1, "train", 0.2), (2, "train", 0.4),
                                 (3, "train", None), (4, "test", 0.1),
                                 (5, "test", 0.5), (6, "test", None),
                                 (4, "excluded_overlap", 0.9)]:
        season = 2024 if split == "test" else 2023
        available = label is not None
        rows.append({
            "player_id": player, "season": season, "outcome_year": season + 1,
            "prediction_date": f"{season + 1}-01-01", "split": split,
            "mlb_pa": 100 if available else 0, "mlb_woba": label,
            "label_available": available, "outcome_eligible": available,
            "reached_mlb": available, "label_provisional": True,
            "outcome_status": "eligible" if available else "not_observed",
            "data_kind": "synthetic", "aaa_pa": 150, "aaa_hits": 30,
            "aaa_ab": 120, "aaa_bb": 20, "aaa_k": 40, "aaa_hr": 5,
        })
    return pd.DataFrame(rows)


def run(frame):
    return training_average_baseline(frame, data_version="fixture", code_version="test", code_dirty=True)


def test_baseline_mean_metrics_and_diagnostics(cohort):
    metrics, predictions = run(cohort)
    assert predictions.y_pred.tolist() == pytest.approx([0.3, 0.3])
    assert predictions.player_id.tolist() == [4, 5]
    assert metrics["mae"] == pytest.approx(0.2)
    assert metrics["rmse"] == pytest.approx(0.2)
    assert metrics["r2"] == pytest.approx(0)
    assert metrics["counts"]["train"]["n_labeled_rows"] == 2
    assert metrics["counts"]["test"]["n_unavailable_labels"] == 1
    assert metrics["counts"]["excluded_overlap"]["n_dropped_from_evaluation"] == 1
    assert metrics["predictors"] == []
    assert metrics["preliminary"]


def test_test_labels_excluded_labels_and_features_cannot_influence_fit(cohort):
    original, predictions = run(cohort)
    cohort.loc[cohort.split.eq("test") & cohort.label_available, "mlb_woba"] = [0.6, 0.8]
    cohort.loc[cohort.split.eq("excluded_overlap"), "mlb_woba"] = 0.01
    cohort["aaa_hits"] = 999
    changed, changed_predictions = run(cohort)
    assert changed["training_mean"] == original["training_mean"]
    assert changed_predictions.y_pred.tolist() == predictions.y_pred.tolist()
    assert changed["mae"] != original["mae"]


def test_overlap_rejected_before_label_filter(cohort):
    cohort.loc[cohort.player_id.eq(3), "player_id"] = 6
    with pytest.raises(ValueError, match="Player overlap"):
        run(cohort)


def test_eligible_but_unavailable_outcome_is_not_imputed(cohort):
    cohort.loc[cohort.player_id.eq(3), "mlb_pa"] = 100
    cohort.loc[cohort.player_id.eq(3), ["outcome_eligible", "reached_mlb"]] = True
    cohort.loc[cohort.player_id.eq(3), "outcome_status"] = "eligible"
    metrics, _ = run(cohort)
    assert metrics["training_mean"] == pytest.approx(0.3)
    assert metrics["counts"]["train"]["n_labeled_rows"] == 2


@pytest.mark.parametrize("split", ["train", "test"])
def test_empty_labeled_partition_rejected(cohort, split):
    mask = cohort.split.eq(split)
    cohort.loc[mask, "mlb_woba"] = float("nan")
    cohort.loc[mask, "mlb_pa"] = 0
    cohort.loc[mask, ["label_available", "outcome_eligible", "reached_mlb"]] = False
    cohort.loc[mask, "outcome_status"] = "not_observed"
    with pytest.raises(ValueError, match="available training and test"):
        run(cohort)


def test_invalid_inputs_rejected(cohort):
    mixed = cohort.copy()
    mixed.loc[0, "data_kind"] = "real"
    with pytest.raises(ValueError, match="data kind"):
        run(mixed)
    cohort.loc[0, "mlb_woba"] = math.inf
    with pytest.raises(ValueError, match="finite"):
        run(cohort)


def test_wrong_frozen_season_rejected(cohort):
    cohort.loc[cohort.split.eq("train"), ["season", "outcome_year", "prediction_date"]] = [2024, 2025, "2025-01-01"]
    with pytest.raises(ValueError, match="frozen split"):
        run(cohort)


@pytest.mark.parametrize("actual, reason", [([0.3], "insufficient_targets"), ([0.3, 0.3], "constant_targets")])
def test_undefined_r2(actual, reason):
    metrics = regression_metrics(actual, [0.2] * len(actual))
    assert metrics["r2"] is None
    assert metrics["r2_undefined_reason"] == reason
    json.dumps(metrics, allow_nan=False)


def test_metric_formulas_and_negative_r2():
    metrics = regression_metrics([1, 2, 3], [0, 2, 5])
    assert metrics["mae"] == 1
    assert metrics["rmse"] == pytest.approx(math.sqrt(5 / 3))
    assert metrics["r2"] == -1.5


@pytest.mark.parametrize("actual, predicted", [([], []), ([1], [1, 2]), ([math.nan], [0])])
def test_invalid_metric_inputs(actual, predicted):
    with pytest.raises(ValueError):
        regression_metrics(actual, predicted)


def test_cli_outputs(cohort, tmp_path, monkeypatch):
    script = tmp_path / "scripts/train_baseline.py"
    script.parent.mkdir()
    source = tmp_path / "fixture.csv"
    cohort.to_csv(source, index=False)
    monkeypatch.setattr(train_baseline, "__file__", str(script))
    monkeypatch.setattr(sys, "argv", [str(script), "--input", str(source)])
    monkeypatch.setattr(train_baseline.subprocess, "check_output", lambda args, **kwargs: "abc123\n" if args[1] == "rev-parse" else "?? changes\n")
    train_baseline.main()
    output = tmp_path / "data/processed"
    metrics = json.loads((output / "model_metrics.json").read_text())
    predictions = pd.read_csv(output / "predictions.csv")
    assert metrics["data_version"].startswith("sha256:")
    assert metrics["code_dirty"] is True
    assert metrics["outcome_validation"] == "independent_validation_pending"
    assert set(predictions.columns) == {"player_id", "season", "outcome_year", "split", "model", "y_true", "y_pred", "data_version", "code_version", "code_dirty"}
    assert len(predictions) == 2


def compare(frame):
    return compare_models(frame, data_version="fixture", code_version="test", code_dirty=True)


@pytest.mark.parametrize("forbidden", ["player_id", "mlb_pa", "mlb_woba", "split", "season", "label_available", "data_kind"])
def test_ridge_rejects_forbidden_predictors(cohort, forbidden):
    with pytest.raises(ValueError, match="allowlist"):
        select_features(cohort, [*FEATURE_INPUTS, forbidden])


def test_feature_matrix_validation(cohort):
    assert select_features(cohort).columns.tolist() == FEATURE_INPUTS
    with pytest.raises(ValueError, match="Missing predictor"):
        select_features(cohort.drop(columns="aaa_hr"))
    with pytest.raises(ValueError, match="numeric"):
        select_features(cohort.assign(aaa_hr="bad"))
    with pytest.raises(ValueError, match="Infinite"):
        select_features(cohort.assign(aaa_hr=math.inf))


def test_pipeline_training_only_imputation_and_scaling():
    train = pd.DataFrame({"aaa_pa": [150., 200., 250.], "aaa_hr": [1., np.nan, 5.]})
    pipeline = ridge_pipeline().fit(train, [0.2, 0.3, 0.4])
    np.testing.assert_allclose(pipeline["imputer"].statistics_, [200, 3])
    np.testing.assert_allclose(pipeline["scaler"].mean_, [200, 3])
    expected_scale = np.std([[150, 1], [200, 3], [250, 5]], axis=0)
    np.testing.assert_allclose(pipeline["scaler"].scale_, expected_scale)
    stats = pipeline["imputer"].statistics_.copy()
    means = pipeline["scaler"].mean_.copy()
    result = pipeline.predict(pd.DataFrame({"aaa_pa": [100000., np.nan], "aaa_hr": [np.nan, 1000.]}))
    assert np.isfinite(result).all()
    np.testing.assert_array_equal(pipeline["imputer"].statistics_, stats)
    np.testing.assert_array_equal(pipeline["scaler"].mean_, means)


def test_cv_fits_preprocessing_within_each_fold(cohort, monkeypatch):
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import GroupKFold

    train = cohort.loc[cohort.split.eq("train") & cohort.label_available].copy()
    train["aaa_hits"] = [10, 90]
    seen = []
    original = SimpleImputer.fit

    def record_fit(self, X, y=None):
        seen.append(tuple(X.aaa_hits))
        return original(self, X, y)

    monkeypatch.setattr(SimpleImputer, "fit", record_fit)
    search = fit_ridge(train)
    assert len(seen) == len(RIDGE_ALPHAS) * 2 + 1
    assert seen.count((10, 90)) == 1  # Only the final refit sees all training rows.
    assert set(seen[:-1]) == {(10,), (90,)}
    for fit_indices, validation_indices in GroupKFold(2).split(train, groups=train.player_id):
        assert not set(train.iloc[fit_indices].player_id) & set(train.iloc[validation_indices].player_id)
    assert search.best_estimator_["imputer"].statistics_[1] == 50


def test_grouped_cv_keeps_repeated_players_together(cohort):
    train = cohort.loc[cohort.split.eq("train") & cohort.label_available]
    repeated = pd.concat([train, train], ignore_index=True)
    search = fit_ridge(repeated)
    for fit_indices, validation_indices in search.cv.split(repeated, groups=repeated.player_id):
        assert not set(repeated.iloc[fit_indices].player_id) & set(repeated.iloc[validation_indices].player_id)


def test_ridge_test_data_cannot_influence_selection(cohort):
    cohort.loc[cohort.split.eq("train") & cohort.label_available, "aaa_hits"] = [10, 90]
    original, predictions = compare(cohort)
    changed = cohort.copy()
    changed.loc[changed.split.eq("test"), "aaa_hits"] = 10000
    changed.loc[changed.split.eq("test") & changed.label_available, "mlb_woba"] = [0.8, 0.9]
    changed.loc[changed.split.eq("excluded_overlap"), "mlb_woba"] = 0.01
    changed.loc[~changed.label_available, "aaa_hits"] = 9999
    updated, _ = compare(changed)
    for key in ("selected_alpha", "cv_results", "fitted_preprocessing"):
        assert original["models"]["ridge"][key] == updated["models"]["ridge"][key]
    labels_only = cohort.copy()
    labels_only.loc[labels_only.split.eq("test") & labels_only.label_available, "mlb_woba"] = [0.8, 0.9]
    _, updated_predictions = compare(labels_only)
    np.testing.assert_array_equal(predictions.y_pred, updated_predictions.y_pred)


def test_comparison_deterministic_same_players_metrics_and_constant_features(cohort):
    metrics, predictions = compare(cohort)
    again, again_predictions = compare(cohort)
    assert metrics == again
    pd.testing.assert_frame_equal(predictions, again_predictions)
    baseline = predictions.loc[predictions.model.eq("training_average")]
    ridge = predictions.loc[predictions.model.eq("ridge")]
    assert baseline.player_id.tolist() == ridge.player_id.tolist() == [4, 5]
    assert baseline.y_true.tolist() == ridge.y_true.tolist()
    assert ridge.y_pred.tolist() == pytest.approx([0.3, 0.3])
    assert metrics["models"]["ridge"]["selected_alpha"] == RIDGE_ALPHAS[0]
    expected = regression_metrics(ridge.y_true, ridge.y_pred)
    for key, value in expected.items():
        assert metrics["models"]["ridge"][key] == value
    json.dumps(metrics, allow_nan=False)


def test_ridge_requires_two_training_players(cohort):
    with pytest.raises(ValueError, match="two training players"):
        compare(cohort.loc[~cohort.player_id.eq(2)])


def test_ridge_rejects_unlabeled_player_overlap(cohort):
    cohort.loc[cohort.player_id.eq(3), "player_id"] = 6
    with pytest.raises(ValueError, match="Player overlap"):
        compare(cohort)


def test_models_cli_outputs(cohort, tmp_path, monkeypatch):
    script = tmp_path / "scripts/train_models.py"
    script.parent.mkdir()
    source = tmp_path / "fixture.csv"
    cohort.to_csv(source, index=False)
    monkeypatch.setattr(train_models, "__file__", str(script))
    monkeypatch.setattr(sys, "argv", [str(script), "--input", str(source)])
    monkeypatch.setattr(train_models.subprocess, "check_output", lambda args, **kwargs: "abc123\n" if args[1] == "rev-parse" else "?? changes\n")
    train_models.main()
    output = tmp_path / "data/processed"
    metrics = json.loads((output / "model_metrics.json").read_text())
    predictions = pd.read_csv(output / "predictions.csv")
    assert set(metrics["models"]) == {"ridge", "training_average"}
    assert metrics["preliminary"] is True
    assert set(predictions.model) == {"ridge", "training_average"}
    assert len(predictions) == 4
    assert not predictions.duplicated(["player_id", "season", "model"]).any()
    assert set(predictions.columns) == {"player_id", "season", "outcome_year", "split", "model", "y_true", "y_pred", "data_version", "code_version", "code_dirty"}

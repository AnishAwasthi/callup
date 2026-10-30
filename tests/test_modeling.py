import json
import math
import sys

import pandas as pd
import pytest

from callup.modeling import regression_metrics, training_average_baseline
from scripts import train_baseline


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

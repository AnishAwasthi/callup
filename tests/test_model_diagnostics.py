import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from callup.contract import load
from callup.model_diagnostics import (
    metric_table,
    plot_diagnostics,
    residual_extremes,
    ridge_details,
)
from callup.modeling import compare_models
from scripts import model_diagnostics

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def diagnostics():
    frame = load(ROOT / "data/sample/hitter_seasons.csv")
    metrics, predictions = compare_models(frame, data_version="synthetic", code_version="test", code_dirty=False)
    coefficients, residuals = ridge_details(frame, predictions)
    return frame, metrics, predictions, coefficients, residuals


def test_coefficients_reconstruct_predictions_with_training_scaling(diagnostics):
    frame, _, predictions, coefficients, residuals = diagnostics
    inputs = frame.loc[frame.split.eq("test") & frame.label_available, coefficients.predictor]
    standardized = (inputs.to_numpy() - coefficients.training_mean.to_numpy()) / coefficients.training_scale.to_numpy()
    recovered = standardized @ coefficients.standardized_coefficient + coefficients.intercept.iloc[0]
    np.testing.assert_allclose(recovered, predictions.loc[predictions.model.eq("ridge"), "y_pred"], atol=1e-12)
    np.testing.assert_allclose(residuals.residual, residuals.y_true - residuals.y_pred)
    assert len(coefficients) == 6


def test_residual_signs_and_largest_errors():
    residuals = pd.DataFrame({"player_id": [1, 2, 3, 4, 5], "season": [2024] * 5,
                              "residual": [-.02, .07, -.15, 0, .03]})
    extremes = residual_extremes(residuals, n=1)
    assert extremes.player_id.tolist() == [3, 2]
    assert extremes.direction.tolist() == ["overprediction", "underprediction"]


def test_details_reject_missing_or_inconsistent_test_predictions(diagnostics):
    frame, _, predictions, _, _ = diagnostics
    with pytest.raises(AssertionError):
        ridge_details(frame, predictions.iloc[:-1])
    altered = predictions.copy()
    altered.loc[altered.model.eq("ridge"), "y_pred"] += .01
    with pytest.raises(AssertionError):
        ridge_details(frame, altered)


def test_plots_and_metric_table(diagnostics, tmp_path, monkeypatch):
    _, metrics, predictions, coefficients, residuals = diagnostics
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    table = metric_table(metrics)
    assert table.mae.tolist() == [metrics["models"][name]["mae"] for name in table.model]
    plot_diagnostics(predictions, residuals, coefficients, metrics, tmp_path / "figures")
    for name in ["observed_vs_predicted", "ridge_residuals", "ridge_coefficients", "model_comparison"]:
        svg = (tmp_path / f"figures/{name}.svg").read_text()
        assert "PRELIMINARY" in svg
        assert (tmp_path / f"figures/{name}.png").read_bytes().startswith(b"\x89PNG")
    scatter = (tmp_path / "figures/observed_vs_predicted.svg").read_text()
    assert "n=2" in scatter and "y = x" in scatter


def test_diagnostics_cli_outputs(diagnostics, tmp_path, monkeypatch):
    _, _, _, _, _ = diagnostics
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(model_diagnostics, "__file__", str(tmp_path / "scripts/model_diagnostics.py"))
    monkeypatch.setattr(sys, "argv", ["model_diagnostics.py", "--input", str(ROOT / "data/sample/hitter_seasons.csv")])
    monkeypatch.setattr(model_diagnostics.subprocess, "check_output", lambda args, **kwargs: "test\n" if args[1] == "rev-parse" else "")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    model_diagnostics.main()
    output = tmp_path / "data/processed"
    assert len(pd.read_csv(output / "predictions.csv")) == 4
    assert len(pd.read_csv(output / "ridge_coefficients.csv")) == 6
    assert len(pd.read_csv(output / "ridge_residuals.csv")) == 2
    assert len(pd.read_csv(output / "model_comparison.csv")) == 2

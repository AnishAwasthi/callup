#!/usr/bin/env python3
"""Reproduce the existing models and generate PRELIMINARY presentation diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.contract import load
from callup.model_diagnostics import (
    metric_table,
    plot_diagnostics,
    residual_extremes,
    ridge_details,
)
from callup.modeling import compare_models


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data/shared/processed/hitter_seasons.csv")
    args = parser.parse_args()
    frame = load(args.input)
    provenance = {
        "data_version": "sha256:" + hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "code_version": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "code_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
    }
    metrics, predictions = compare_models(frame, **provenance)
    coefficients, residuals = ridge_details(frame, predictions)
    output = root / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    (output / "model_metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    predictions.to_csv(output / "predictions.csv", index=False)
    coefficients.to_csv(output / "ridge_coefficients.csv", index=False)
    residuals.to_csv(output / "ridge_residuals.csv", index=False)
    residual_extremes(residuals).to_csv(output / "ridge_residual_extremes.csv", index=False)
    metric_table(metrics).to_csv(output / "model_comparison.csv", index=False)
    plot_diagnostics(predictions, residuals, coefficients, metrics, output / "figures")
    print("PRELIMINARY — frozen provisional labels, not independently verified FanGraphs targets.")
    print(metric_table(metrics).to_string(index=False))
    print(coefficients.to_string(index=False))
    print(residual_extremes(residuals)[["player_id", "name", "y_true", "y_pred", "residual", "direction"]].to_string(index=False))


if __name__ == "__main__":
    main()

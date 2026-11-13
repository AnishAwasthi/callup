#!/usr/bin/env python3
"""Compare preliminary training-average and Ridge models on the frozen split."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.contract import load
from callup.modeling import compare_models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/shared/processed/hitter_seasons.csv"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    code_version = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    code_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    data_version = "sha256:" + hashlib.sha256(args.input.read_bytes()).hexdigest()
    metrics, predictions = compare_models(
        load(args.input), data_version=data_version, code_version=code_version, code_dirty=code_dirty,
    )
    output = root / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    (output / "model_metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    predictions.to_csv(output / "predictions.csv", index=False)
    print("PRELIMINARY: independent outcome validation remains pending.")
    print(json.dumps(metrics, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Produce only the five-player pilot comparison; never modify model/data inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from callup.contract import load
from callup.outcome_validation import PILOT, compare_reference, load_references


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, default=root / "validation/references/fangraphs_woba_pilot.json")
    args = parser.parse_args()
    input_path = root / "data/shared/processed/hitter_seasons.csv"
    frame = load(input_path)
    references = load_references(args.references)
    results = []
    code_version = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    for reference in references:
        key = (reference["player_id"], reference["season"])
        selected = frame.loc[frame.player_id.eq(key[0]) & frame.season.eq(key[1])]
        if len(selected) != 1 or not selected.iloc[0].label_available or selected.iloc[0]["name"] != PILOT[key]:
            raise ValueError(f"Pilot key/name/available label mismatch: {key}")
        row = selected.iloc[0]
        result = compare_reference(row, reference)
        year = int(row.outcome_year)
        archive = root / f"data/shared/pitches/mlb_{year}.csv.gz"
        # Diagnosis only: these archived values are NEVER independent references.
        pitches = pd.read_csv(archive, usecols=["batter", "events", "woba_value", "woba_denom"])
        terminal = pitches.loc[pitches.batter.eq(row.player_id) & pitches.events.notna()]
        summary = terminal.groupby("events").agg(
            n=("events", "size"), numerator=("woba_value", "sum"), denominator=("woba_denom", "sum"))
        result.update(
            observed_pa_gap=int(row.mlb_observed_pa - row.mlb_pa),
            archive_terminal_rows=len(terminal),
            archive_numerator=float(terminal.woba_value.sum()),
            archive_denominator=float(terminal.woba_denom.sum()),
            archive_events_json=json.dumps(summary.to_dict("index"), sort_keys=True),
            archive_sha256=sha256(archive), data_sha256=sha256(input_path),
            reference_snapshot_sha256=sha256(args.references), code_version=code_version,
            code_dirty=dirty, preliminary=True,
        )
        if (len(terminal) != row.mlb_observed_pa
                or abs(result["archive_numerator"] - row.mlb_woba_numerator) > 1e-9
                or abs(result["archive_denominator"] - row.mlb_woba_denom) > 1e-9):
            raise ValueError(f"Archive does not reproduce prepared components: {key}")
        results.append(result)
    output = root / "data/processed/outcome_validation_comparison.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame(results)
    comparison.to_csv(output, index=False)
    print(comparison[["name", "season", "outcome_year", "split", "mlb_woba", "reference_woba", "difference", "status"]].to_string(index=False))
    print("PRELIMINARY: five checks only; unresolved differences require scientific review.")


if __name__ == "__main__":
    main()

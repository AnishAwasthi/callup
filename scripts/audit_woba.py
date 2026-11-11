#!/usr/bin/env python3
"""Read frozen inputs and write separate PRELIMINARY wOBA audit artifacts offline."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from callup.contract import load
from callup.outcome_validation import load_references
from callup.woba_audit import compare_audit, discrepancy_summary, reconstruct


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    pilot_path = root / "validation/references/fangraphs_woba_pilot.json"
    audit_path = root / "validation/references/fangraphs_woba_audit.json"
    pilot = load_references(pilot_path)
    audit = json.loads(audit_path.read_text())
    references = pilot + audit["additional_references"]
    keys = [(r["player_id"], r["season"]) for r in references]
    if len(keys) != len(set(keys)) or len(keys) != 10:
        raise ValueError("This audit requires ten distinct, documented player-seasons")
    components = {(r["player_id"], r["season"]): r for r in audit["independent_components"]}
    if len(components) != 10 or set(components) != set(keys):
        raise ValueError("Missing independent component records")
    input_path = root / "data/shared/processed/hitter_seasons.csv"
    frame = load(input_path)
    rows, events, anomalies, weights_observed, inputs = [], [], [], [], [input_path, pilot_path, audit_path]
    for year in (2024, 2025):
        path = root / f"data/shared/pitches/mlb_{year}.csv.gz"
        inputs.append(path)
        pitches = pd.read_csv(path, usecols=["batter", "events", "woba_value", "woba_denom",
                                           "game_date", "game_pk", "at_bat_number", "pitch_number"])
        weights = audit["formulas"]["standard"]["weights"][str(year)]
        basic = audit["formulas"]["basic"]["weights"]
        selected_ids = [r["player_id"] for r in references if r["outcome_year"] == year]
        served = pitches.loc[pitches.batter.isin(selected_ids) & pitches.events.notna()]
        weights_observed.append(served.groupby(["events", "woba_value", "woba_denom"], dropna=False)
                                .size().reset_index(name="n").assign(outcome_year=year))
        for reference in references:
            if reference["outcome_year"] != year:
                continue
            key = (reference["player_id"], reference["season"])
            selected = frame.loc[frame.player_id.eq(key[0]) & frame.season.eq(key[1])]
            if len(selected) != 1:
                raise ValueError(f"Missing/ambiguous prepared key {key}")
            player_pitches = pitches.loc[pitches.batter.eq(key[0])]
            if player_pitches.duplicated(["game_pk", "at_bat_number", "pitch_number"]).any():
                raise ValueError("Duplicate player pitch keys")
            reconstruction, event_table, anomaly_table = reconstruct(player_pitches, weights, basic)
            result = compare_audit(selected.iloc[0], reference, components[key], reconstruction)
            result["sample"] = "pilot" if reference in pilot else "extension"
            rows.append(result)
            events.append(event_table.assign(player_id=key[0], season=key[1], outcome_year=year))
            anomalies.append(anomaly_table.assign(season=key[1], outcome_year=year))
    comparison = pd.DataFrame(rows).sort_values(["season", "player_id"])
    summaries = {"all": discrepancy_summary(comparison)}
    for column in ("outcome_year", "split", "sample"):
        summaries[column] = {str(name): discrepancy_summary(group) for name, group in comparison.groupby(column)}
    provenance = {
        "preliminary": True, "selection": audit["selection"], "formulas": audit["formulas"],
        "formula_retrieved_at": audit["retrieved_at"],
        "input_sha256": {str(path.relative_to(root)): digest(path) for path in inputs},
        "code_sha256": {str(path): digest(root / path) for path in [
            Path("callup/woba_audit.py"), Path("scripts/audit_woba.py"), Path("scripts/prepare_analysis.py")]},
        "code_version": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "code_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
        "pandas_version": pd.__version__, "summary": summaries,
    }
    benchmark = root / "data/processed/model_metrics.json"
    if benchmark.exists():
        model_metrics = json.loads(benchmark.read_text())["models"]
        baseline, ridge = model_metrics["training_average"], model_metrics["ridge"]
        provenance["existing_model_metrics"] = {
            "sha256": digest(benchmark), "data_version": baseline["data_version"],
            "baseline_mae": baseline["mae"], "baseline_rmse": baseline["rmse"],
            "ridge_mae": ridge["mae"], "ridge_rmse": ridge["rmse"],
            "note": "read existing evaluation only; no models fitted; magnitudes concern different targets and samples",
        }
    output = root / "data/processed/woba_audit"
    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output / "comparisons.csv", index=False)
    pd.concat(events, ignore_index=True).to_csv(output / "events.csv", index=False)
    pd.concat(anomalies, ignore_index=True).to_csv(output / "anomalies.csv", index=False)
    pd.concat(weights_observed, ignore_index=True).to_csv(output / "served_weights.csv", index=False)
    (output / "audit.json").write_text(json.dumps(provenance, indent=2, allow_nan=False) + "\n")
    print(comparison[["name", "outcome_year", "split", "mlb_woba", "reference_woba", "basic_diagnostic", "standard_diagnostic", "status"]].to_string(index=False))
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()

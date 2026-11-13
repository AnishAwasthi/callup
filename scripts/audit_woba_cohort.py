#!/usr/bin/env python3
"""Offline full-cohort reconciliation. Writes diagnostics only under data/processed/."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from callup.contract import load
from callup.woba_audit import reconstruct
from callup.woba_cohort import (
    leaderboard_url,
    match_record,
    parse_leaderboard,
    reconcile,
    reference_record,
    summarize,
    validate_references,
)
from scripts.audit_woba import digest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed/woba_cohort_v1"
REFERENCE = ROOT / "validation/references/fangraphs_woba_cohort_v1.json"


def capture(cohort, source_dir, retrieved_at):
    """Explicit import of public captures; stdout can be saved as a review fixture."""
    references, attempts, sources = [], [], {}
    for year, group in cohort.groupby("outcome_year"):
        path = source_dir / f"fangraphs_{year}.html"
        source_rows, metadata = parse_leaderboard(path.read_text(), int(year))
        sources[str(year)] = {**metadata, "url": leaderboard_url(int(year)),
                              "sha256": digest(path), "retrieved_at": retrieved_at}
        for _, prepared in group.iterrows():
            status, source = match_record(int(prepared.player_id), int(year), source_rows)
            attempts.append({"player_id": int(prepared.player_id), "season": int(prepared.season), "status": status})
            if status == "matched":
                references.append(reference_record(prepared, source, retrieved_at, digest(path)))
    return {"version": "fangraphs-cohort-reference-v1", "capture_note": (
        "Curated cohort facts from independent FanGraphs public leaderboard embedded JSON, not internal reconstructions. "
        "Raw HTML stays ignored. Retrieved in the 2026-11-11 07:49–07:55 UTC session; timestamp marks capture registration. "
        "Embedded dataUpdatedAt is retained separately and is not claimed as source revision time. "
        "woba preserves source numeric token precision; UI display precision is three decimals."),
        "sources": sources, "attempts": attempts, "references": references}


def run(root=ROOT, output=OUTPUT, reference_path=REFERENCE):
    input_path = root / "data/shared/processed/hitter_seasons.csv"
    cohort = load(input_path).loc[lambda f: f.label_available].copy()
    if len(cohort) != 239:
        raise ValueError("Frozen cohort must contain 239 eligible labels")
    document = json.loads(reference_path.read_text())
    references = validate_references(document, cohort)
    attempts = {(a["player_id"], a["season"]): a["status"] for a in document["attempts"]}
    if len(attempts) != len(document["attempts"]):
        raise ValueError("Duplicate matching attempts")
    if set(attempts.values()) - {"matched", "ambiguous", "unmatched", "not_yet_verified"}:
        raise ValueError("Unknown matching status")
    if {k for k, v in attempts.items() if v == "matched"} != set(references):
        raise ValueError("Matching attempts and references disagree")
    audit_path = root / "validation/references/fangraphs_woba_audit.json"
    formulas = json.loads(audit_path.read_text())["formulas"]
    inputs = [input_path, reference_path, audit_path]
    rows, events, anomalies, inventories = [], [], [], []
    for year, group in cohort.groupby("outcome_year"):
        path = root / f"data/shared/pitches/mlb_{year}.csv.gz"
        inputs.append(path)
        archive_sha256 = digest(path)
        pitches = pd.read_csv(path, usecols=["batter", "events", "woba_value", "woba_denom",
                                            "game_date", "game_pk", "at_bat_number", "pitch_number"])
        pitches = pitches.loc[pitches.batter.isin(group.player_id)].copy()
        keys = ["game_pk", "at_bat_number", "pitch_number"]
        if pitches[keys].isna().any().any() or pitches.duplicated(keys).any():
            raise ValueError("Missing or duplicate pitch keys")
        if not pd.to_datetime(pitches.game_date).dt.year.eq(year).all():
            raise ValueError("Archive scope differs from regular season")
        terminal = pitches.loc[pitches.events.notna()]
        if terminal.duplicated(["game_pk", "at_bat_number"]).any():
            raise ValueError("Multiple terminal events per PA")
        inventories.append(terminal.groupby(["events", "woba_value", "woba_denom"], dropna=False)
                           .size().reset_index(name="n").assign(outcome_year=year))
        for _, prepared in group.iterrows():
            key = (int(prepared.player_id), int(prepared.season))
            internal, event, anomaly = reconstruct(
                pitches.loc[pitches.batter.eq(key[0])],
                formulas["standard"]["weights"][str(year)], formulas["basic"]["weights"])
            row = reconcile(prepared, internal, references.get(key))
            row["match_status"] = attempts.get(key, "not_yet_verified")
            row["outcome_version"] = "standard-woba-diagnostic-v1"
            row["adopted_as_target"] = False
            row["internal_source_sha256"] = archive_sha256
            rows.append(row)
            events.append(event.assign(player_id=key[0], season=key[1], outcome_year=year))
            anomalies.append(anomaly.assign(season=key[1], outcome_year=year))
    comparison = pd.DataFrame(rows).sort_values(["season", "player_id"])
    summary = {"all": summarize(comparison)}
    for column in ["outcome_year", "split"]:
        summary[column] = {str(k): summarize(g) for k, g in comparison.groupby(column)}
    provenance = {
        "diagnostic_only": True, "target_replacement_implemented": False,
        "formulas": formulas, "references": document["sources"],
        "input_sha256": {str(p.relative_to(root)): digest(p) for p in inputs},
        "code_sha256": {p: digest(root / p) for p in ["callup/woba_audit.py", "callup/woba_cohort.py", "scripts/audit_woba_cohort.py"]},
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
        "pandas_version": pd.__version__, "summary": summary,
    }
    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output / "reconciliation.csv", index=False)
    pd.concat(events, ignore_index=True).to_csv(output / "events.csv", index=False)
    pd.concat(anomalies, ignore_index=True).to_csv(output / "anomalies.csv", index=False)
    pd.concat(inventories, ignore_index=True).to_csv(output / "served_weights.csv", index=False)
    (output / "summary.json").write_text(json.dumps(provenance, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2))
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="Read fangraphs_YEAR.html captures and print curated reference JSON; no analysis")
    parser.add_argument("--retrieved-at", help="Explicit timezone-bearing registration timestamp of retrieval session")
    args = parser.parse_args()
    if args.capture:
        if not args.retrieved_at:
            parser.error("--capture requires --retrieved-at")
        cohort = load(ROOT / "data/shared/processed/hitter_seasons.csv").loc[lambda f: f.label_available]
        print(json.dumps(capture(cohort, args.capture, args.retrieved_at), indent=2, allow_nan=False))
    else:
        run()


if __name__ == "__main__":
    main()

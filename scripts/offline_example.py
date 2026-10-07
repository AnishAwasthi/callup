#!/usr/bin/env python3
"""Check starter inputs offline; no feature suite or model training."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from callup.contract import load

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--sample-dir", type=Path, default=Path("data/sample"))
args = parser.parse_args()
cohort = load(args.sample_dir / "hitter_seasons.csv")
pitches = pd.read_csv(args.sample_dir / "pitches.csv")
if pitches.duplicated(["game_pk", "at_bat_number", "pitch_number"]).any():
    raise SystemExit("Duplicate pitch key")
if not set(pitches.batter).issubset(set(cohort.player_id)):
    raise SystemExit("Pitch batter does not join to sample cohort")
print(f"Provenance: {', '.join(sorted(cohort.data_kind.unique()))}")
print(f"{len(cohort)} player-seasons; {len(pitches)} AAA pitches; contract checks passed")
print(cohort.groupby(["season", "split", "outcome_status"]).size().to_string())
print("Start your issue using docs/data-contract.md. Synthetic data verifies setup only.")

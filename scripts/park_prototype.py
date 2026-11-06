#!/usr/bin/env python3
"""Prototype Triple-A park factors from all AAA pitch rows; see docs/park-factor-research.md."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from callup.parks import (
    PITCH_COLUMNS,
    STATS,
    home_away_sums,
    home_parks,
    plate_appearances,
    prototype,
    ratio_factors,
    schedule_venues,
)
from callup.statsapi import SPORT_IDS, StatsAPI

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shared-dir", type=Path, default=Path("data/shared"))
parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024])
parser.add_argument("--stat", choices=sorted(STATS), default="woba")
parser.add_argument("--min-pa", type=int, default=2000, help="minimum PAs on each side of a comparison")
parser.add_argument("--offline", action="store_true", help="use only the cached Stats API schedule")
args = parser.parse_args()

api = StatsAPI(offline=args.offline)
teams = pd.read_csv(args.shared_dir / "teams.csv")
frames = []
for season in args.seasons:
    pitches = pd.read_csv(args.shared_dir / "pitches" / f"aaa_{season}.csv.gz", usecols=PITCH_COLUMNS)
    games = schedule_venues(api.get("schedule", sportId=SPORT_IDS["AAA"], season=season, gameType="R"))
    frames.append(plate_appearances(pitches, games, args.stat))
pa = pd.concat(frames, ignore_index=True)
output, comparison, parks = prototype(pa, teams, args.stat, args.min_pa)

args.out_dir.mkdir(parents=True, exist_ok=True)
output.to_csv(args.out_dir / "park_prototype.csv", index=False)
comparison.to_csv(args.out_dir / "park_method_comparison.csv", index=False)
parks.to_csv(args.out_dir / "park_venue_audit.csv", index=False)

print(f"Statistic: {STATS[args.stat]}; neutral park = 1.0; {len(pa):,} PAs in {pa.game_pk.nunique():,} games")
print(f"Venues differing from teams.csv: {(~parks.venue_matches_teams_csv).sum()}; relocated games: {parks.n_relocated_games.sum()}")
wide = comparison.pivot_table(index=["season", "home_team"], columns="method", values="factor")
wide = wide.join(parks.set_index(["season", "home_team"]).league)
print("\nFactors by method (sorted by recommended method):")
recommended = f"home_away_shrunk_{args.stat}"
print(wide.sort_values(["season", recommended], ascending=[True, False]).round(3).to_string())

print("\nChecks")
print("Blank factors:", comparison.factor.isna().sum())
for method in wide.columns.drop("league"):
    print(f"  {method}: range {wide[method].min():.3f}-{wide[method].max():.3f}")
model = f"player_adjusted_{args.stat}"
league_mean = wide.groupby(["season", "league"])[model].mean().round(3)
print("Player-adjusted mean by league (all AAA = 1.0):", league_mean.to_dict())
within = wide[model] / wide.groupby(["season", "league"])[model].transform("mean")
print("Correlation, single-season ratio vs player-adjusted (within league):", round(wide[f"home_away_ratio_{args.stat}"].corr(within), 3))
single = wide[f"home_away_ratio_{args.stat}"].unstack("season")
if single.shape[1] > 1:
    print("Year-to-year correlation of single-season ratios:", round(single.iloc[:, 0].corr(single.iloc[:, -1]), 3))

# Sample-size sensitivity: rebuild single-season ratios from random subsets of games.
rng = np.random.default_rng(0)
full = wide[f"home_away_ratio_{args.stat}"]
for share in [0.25, 0.5]:
    keep = pa.game_pk.drop_duplicates().sample(frac=share, random_state=rng.integers(1 << 31))
    subset = pa[pa.game_pk.isin(keep)]
    sub_parks = home_parks(subset, teams)
    sub = ratio_factors(home_away_sums(subset, sub_parks), sub_parks, min_pa=0).set_index(["season", "home_team"]).factor
    print(f"Using {share:.0%} of games: median |change| {(sub - full).abs().median():.3f}, max {(sub - full).abs().max():.3f}")
print(f"\nWrote {args.out_dir / 'park_prototype.csv'} ({len(output)} rows), park_method_comparison.csv and park_venue_audit.csv")

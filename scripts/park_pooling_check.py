#!/usr/bin/env python3
"""Split-half check of pooling seasons; see docs/park-factor-research.md.

Splits the later season's games in half at random. Half B is held out. Each park's half-B
factor is predicted from half A alone, or from half A pooled with the earlier season, with and
without shrinkage. Prints the error (RMSE across parks) of each, averaged over the splits.
"""
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
    pooled_sums,
    ratio_factors,
    schedule_venues,
    shrink,
)
from callup.statsapi import SPORT_IDS, StatsAPI

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--shared-dir", type=Path, default=Path("data/shared"))
parser.add_argument("--seasons", type=int, nargs=2, default=[2023, 2024], help="earlier and later season")
parser.add_argument("--stats", choices=sorted(STATS), nargs="+", default=list(STATS))
parser.add_argument("--splits", type=int, default=20)
parser.add_argument("--offline", action="store_true", help="use only the cached Stats API schedule")
args = parser.parse_args()

api = StatsAPI(offline=args.offline)
teams = pd.read_csv(args.shared_dir / "teams.csv")
earlier, later = args.seasons
inputs = []
for season in args.seasons:
    pitches = pd.read_csv(args.shared_dir / "pitches" / f"aaa_{season}.csv.gz", usecols=PITCH_COLUMNS)
    inputs.append((pitches, schedule_venues(api.get("schedule", sportId=SPORT_IDS["AAA"], season=season, gameType="R"))))

rows = {}
for stat in args.stats:
    pa = pd.concat([plate_appearances(pitches, games, stat) for pitches, games in inputs], ignore_index=True)
    later_games = pa.loc[pa.season.eq(later), "game_pk"].drop_duplicates()
    errors = {}
    for seed in range(args.splits):
        half_a = later_games.sample(frac=0.5, random_state=seed)
        held_out = pa.season.eq(later) & ~pa.game_pk.isin(half_a)
        train, test = pa[~held_out], pa[held_out]
        test_parks = home_parks(test, teams)
        target = ratio_factors(home_away_sums(test, test_parks), test_parks, 0).set_index("home_team").factor
        parks = home_parks(train, teams)
        sums = home_away_sums(train, parks)
        candidates = {
            "half A alone": ratio_factors(sums[sums.season.eq(later)], parks, 0),
            f"half A + {earlier} pooled": ratio_factors(pooled_sums(sums, later), parks, 0),
        }
        for name, frame in candidates.items():
            for label, factor in ((name, frame.factor), (f"{name}, shrunk", shrink(frame))):
                prediction = pd.Series(factor.to_numpy(), index=frame.home_team)
                errors.setdefault(label, []).append(np.sqrt(((prediction - target) ** 2).mean()))
    rows[stat] = {label: np.mean(values) for label, values in errors.items()}
    alone, pooled = np.array(errors["half A alone"]), np.array(errors[f"half A + {earlier} pooled"])
    rows[stat]["splits where pooling helped"] = f"{np.mean(pooled < alone):.0%}"

table = pd.DataFrame(rows).map(lambda value: f"{value:.3f}" if isinstance(value, float) else value)
print(f"RMSE against the held-out half of {later}, mean over {args.splits} random splits")
print(table.to_string())

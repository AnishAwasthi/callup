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
    between_park_variance,
    home_away_sums,
    home_parks,
    plate_appearances,
    pooled_sums,
    prototype,
    ratio_factors,
    schedule_venues,
    shrink_weights,
)
from callup.statsapi import SPORT_IDS, StatsAPI

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shared-dir", type=Path, default=Path("data/shared"))
parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024])
parser.add_argument("--stat", choices=sorted(STATS), default="woba", help="statistic written to park_prototype.csv; the default is the proposed statistic")
parser.add_argument("--stats", choices=sorted(STATS), nargs="+", default=list(STATS), help="statistics compared in park_method_comparison.csv")
parser.add_argument("--min-pa", type=int, default=2000, help="minimum PAs on each side of a comparison")
parser.add_argument("--offline", action="store_true", help="use only the cached Stats API schedule")
args = parser.parse_args()

api = StatsAPI(offline=args.offline)
teams = pd.read_csv(args.shared_dir / "teams.csv")
inputs = []
for season in args.seasons:
    pitches = pd.read_csv(args.shared_dir / "pitches" / f"aaa_{season}.csv.gz", usecols=PITCH_COLUMNS)
    games = schedule_venues(api.get("schedule", sportId=SPORT_IDS["AAA"], season=season, gameType="R"))
    inputs.append((pitches, games))


def summarize(stat, pa, comparison, parks):
    """Diagnostics reported in docs/park-factor-research.md for one statistic."""
    def rows(name):
        return comparison[comparison.method.eq(f"{name}_{stat}")].set_index(["season", "home_team"])

    single, shrunk, model = rows("home_away_ratio"), rows("home_away_shrunk"), rows("player_adjusted")
    summary = {"base rate per PA": pa.value.mean()}
    for name, frame in (("single-season ratio", single), ("shrunk", shrunk), ("player-adjusted", model)):
        summary[f"range: {name}"] = f"{frame.factor.min():.2f}-{frame.factor.max():.2f}"
    sums = home_away_sums(pa, parks)
    for season in args.seasons:
        one = single.xs(season).reset_index().assign(season=season)
        pooled = ratio_factors(pooled_sums(sums, season), parks, args.min_pa)
        summary[f"tau single / pooled {season}"] = f"{np.sqrt(between_park_variance(np.log(one.factor), one.se_log)):.3f} / {np.sqrt(between_park_variance(np.log(pooled.factor), pooled.se_log)):.3f}"
        summary[f"mean se single / pooled {season}"] = f"{one.se_log.mean():.3f} / {pooled.se_log.mean():.3f}"
        summary[f"median w single / used {season}"] = f"{shrink_weights(one).median():.2f} / {shrunk.xs(season).shrink_weight.median():.2f}"
    first, last = args.seasons[0], args.seasons[-1]
    pair = pd.DataFrame({"before": single.xs(first).factor, "after": single.xs(last).factor, "shrunk": shrunk.xs(first).factor}).dropna()
    summary["year-to-year corr"] = pair.before.corr(pair.after)
    summary["year-to-year slope (log)"] = np.polyfit(np.log(pair.before), np.log(pair.after), 1)[0]
    for name, prediction in (("all 1.0", 1.0), ("raw", pair.before), ("shrunk", pair.shrunk)):
        summary[f"RMSE vs {last}: {name}"] = np.sqrt(((prediction - pair.after) ** 2).mean())
    within = model.factor / model.factor.groupby([model.index.get_level_values("season"), model.index.map(parks.set_index(["season", "home_team"]).league)]).transform("mean")
    summary["corr ratio vs player-adjusted (within league)"] = single.factor.corr(within)
    # Sample-size sensitivity: rebuild single-season ratios from random subsets of games.
    rng = np.random.default_rng(0)
    for share in [0.25, 0.5]:
        keep = pa.game_pk.drop_duplicates().sample(frac=share, random_state=rng.integers(1 << 31))
        subset = pa[pa.game_pk.isin(keep)]
        sub_parks = home_parks(subset, teams)
        sub = ratio_factors(home_away_sums(subset, sub_parks), sub_parks, min_pa=0).set_index(["season", "home_team"]).factor
        summary[f"median |change|, {share:.0%} of games"] = (sub - single.factor).abs().median()
    return summary


results = {}
for stat in dict.fromkeys([*args.stats, args.stat]):
    pa = pd.concat([plate_appearances(pitches, games, stat) for pitches, games in inputs], ignore_index=True)
    output, comparison, parks = prototype(pa, teams, stat, args.min_pa)
    results[stat] = {"pa": pa, "output": output, "comparison": comparison, "parks": parks}
comparison = pd.concat([result["comparison"] for result in results.values()], ignore_index=True)
output, parks = results[args.stat]["output"], results[args.stat]["parks"]

args.out_dir.mkdir(parents=True, exist_ok=True)
output.to_csv(args.out_dir / "park_prototype.csv", index=False)
comparison.to_csv(args.out_dir / "park_method_comparison.csv", index=False)
parks.to_csv(args.out_dir / "park_venue_audit.csv", index=False)

pa = results[args.stat]["pa"]
print(f"park_prototype.csv statistic: {STATS[args.stat]}; neutral park = 1.0; {len(pa):,} PAs in {pa.game_pk.nunique():,} games")
print(f"Venues differing from teams.csv: {(~parks.venue_matches_teams_csv).sum()}; relocated games: {parks.n_relocated_games.sum()}")
print("Blank factors:", comparison.factor.isna().sum())
wide = results[args.stat]["comparison"].pivot_table(index=["season", "home_team"], columns="method", values="factor")
wide = wide.join(parks.set_index(["season", "home_team"]).league)
print(f"\nFactors by method for {args.stat} (sorted by home_away_shrunk):")
print(wide.sort_values(["season", f"home_away_shrunk_{args.stat}"], ascending=[True, False]).round(3).to_string())

summaries = {stat: summarize(stat, result["pa"], result["comparison"], result["parks"]) for stat, result in results.items()}
if "woba" in results:
    def shrunk_factors(stat):
        frame = results[stat]["comparison"]
        return frame[frame.method.eq(f"home_away_shrunk_{stat}")].set_index(["season", "home_team"]).factor

    for stat in results:
        summaries[stat]["corr of shrunk factor with wOBA's"] = shrunk_factors(stat).corr(shrunk_factors("woba"))
table = pd.DataFrame(summaries).map(lambda value: f"{value:.3f}" if isinstance(value, float) else value)
print("\nStatistic comparison")
print(table.to_string())
print(f"\nWrote {args.out_dir / 'park_prototype.csv'} ({len(output)} rows, {args.stat}), park_method_comparison.csv ({comparison.method.nunique()} methods) and park_venue_audit.csv")

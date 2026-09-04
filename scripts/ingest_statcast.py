#!/usr/bin/env python3
"""
Archive pitch-level Statcast data for MLB and Triple-A.

Resumable by design: each game-date is stored as its own file, so an interrupted run
picks up exactly where it stopped and never re-fetches a completed date. Re-running after
a full pull costs nothing but disk reads.

A complete three-season pull is roughly 1,000 requests and takes on the order of an hour
or two with the built-in politeness delay. Start small:

    python scripts/ingest_statcast.py --seasons 2024 --levels MLB --limit 5   # smoke test
    python scripts/ingest_statcast.py --estimate                              # plan the run
    python scripts/ingest_statcast.py                                         # full pull
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.ingest import (  # noqa: E402
    DEFAULT_RAW_DIR,
    REQUEST_DELAY_S,
    TruncatedResponse,
    game_dates,
    ingest_season,
)
from callup.statsapi import StatsAPI  # noqa: E402

# Triple-A tracking begins in 2023; earlier seasons have season lines but no pitch data.
DEFAULT_SEASONS = [2023, 2024, 2025]
DEFAULT_LEVELS = ["MLB", "AAA"]

# Rough per-request cost, used only for the estimate.
SECONDS_PER_REQUEST = REQUEST_DELAY_S + 4.0


def estimate(api: StatsAPI, seasons: list[int], levels: list[str], raw_dir: Path) -> None:
    print("\nPlanned ingest")
    print("=" * 62)
    total_dates = total_todo = 0

    for level in levels:
        for season in seasons:
            dates = game_dates(api, season, level)
            done = sum(1 for d in dates if (raw_dir / level / f"{d}.csv.gz").exists())
            todo = len(dates) - done
            total_dates += len(dates)
            total_todo += todo
            print(f"  {level:4} {season}:  {len(dates):>3} dates   {done:>3} archived   {todo:>3} to fetch")

    minutes = total_todo * SECONDS_PER_REQUEST / 60
    print("=" * 62)
    print(f"  {total_dates} game-dates total, {total_todo} still to fetch")
    print(f"  estimated time: ~{minutes:.0f} min ({minutes / 60:.1f} h)")
    print("\n  Resumable — interrupt any time and re-run to continue.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", default=DEFAULT_SEASONS)
    parser.add_argument("--levels", nargs="+", choices=["MLB", "AAA"], default=DEFAULT_LEVELS)
    parser.add_argument("--limit", type=int, help="only the first N dates per season (smoke test)")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--estimate", action="store_true", help="report the plan and exit")
    args = parser.parse_args()

    api = StatsAPI()
    if args.estimate:
        estimate(api, args.seasons, args.levels, args.raw_dir)
        return

    started = time.time()
    grand_total = 0
    for level in args.levels:
        for season in args.seasons:
            print(f"\n{level} {season}")
            try:
                results = ingest_season(api, season, level, args.raw_dir, limit=args.limit)
            except TruncatedResponse as exc:
                # Loud on purpose: a truncated day means real data is missing.
                print(f"\n  TRUNCATED: {exc}")
                print("  Stopping — this date needs splitting before the pull can continue.")
                raise SystemExit(1) from exc
            rows = sum(r.rows for r in results)
            grand_total += rows
            print(f"  done: {len(results)} dates, {rows:,} rows")

    elapsed = time.time() - started
    print(f"\nArchived {grand_total:,} rows in {elapsed / 60:.1f} min -> {args.raw_dir}")


if __name__ == "__main__":
    main()

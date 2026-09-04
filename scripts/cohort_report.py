#!/usr/bin/env python3
"""
Viability check: is there enough real, labeled AAA -> MLB data to train on?

This is deliberately the first thing in the repo. Any modeling work is worthless if the
answer is "sixty players", and that is worth finding out in an afternoon rather than a
month. Run it before trusting anything downstream.

    python scripts/cohort_report.py
    python scripts/cohort_report.py --threshold loose --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.cohort import THRESHOLDS, build_cohort  # noqa: E402
from callup.statsapi import StatsAPI  # noqa: E402

# AAA tracking data begins in 2023, so earlier seasons have no pitch-level features to
# pair with these labels even though the box-score lines exist.
DEFAULT_SEASONS = [2023, 2024, 2025]


def summarize(api: StatsAPI, seasons: list[int], threshold: str) -> dict:
    summary = {"threshold": threshold, "seasons": seasons, "groups": {}}
    for group in ("hitting", "pitching"):
        cohort = build_cohort(api, seasons, group, threshold)
        aaa_min, mlb_min = THRESHOLDS[group][threshold]
        summary["groups"][group] = {
            "aaa_min": aaa_min,
            "mlb_min": mlb_min,
            "labeled": len(cohort.labeled),
            "promoted_thin": len(cohort.promoted_thin),
            "never_promoted": len(cohort.never_promoted),
            "pool": cohort.pool_size,
            "promotion_rate": round(cohort.promotion_rate, 4),
            "censoring_rate": round(cohort.censoring_rate, 4),
        }
    totals = summary["groups"].values()
    summary["total_labeled"] = sum(g["labeled"] for g in totals)
    summary["total_pool"] = sum(g["pool"] for g in totals)
    return summary


def render(summary: dict) -> None:
    print(f"\nAAA -> MLB cohort  ·  seasons {summary['seasons']}  ·  {summary['threshold']} thresholds")
    print("=" * 78)

    for group, stats in summary["groups"].items():
        unit = "PA" if group == "hitting" else "IP"
        print(f"\n{group.upper()}   (AAA >= {stats['aaa_min']} {unit}, MLB >= {stats['mlb_min']} {unit})")
        print(f"  labeled  (usable for training) {stats['labeled']:>6}")
        print(f"  promoted but thin sample       {stats['promoted_thin']:>6}")
        print(f"  never reached MLB              {stats['never_promoted']:>6}")
        print(f"  {'-' * 38}")
        print(f"  pool                           {stats['pool']:>6}")
        print(f"  reached MLB at all             {stats['promotion_rate']:>6.1%}")
        print(f"  no usable outcome (censored)   {stats['censoring_rate']:>6.1%}")

    print("\n" + "=" * 78)
    print(f"TOTAL labeled training rows: {summary['total_labeled']}")
    print(f"TOTAL AAA player-seasons:    {summary['total_pool']}")
    print(
        "\nThe censored share is the project's central modeling problem: a plain\n"
        "regression fit on labeled players only is fit on a population that front\n"
        "offices already selected as good enough to promote."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", choices=sorted(THRESHOLDS["hitting"]), default="moderate")
    parser.add_argument("--seasons", type=int, nargs="+", default=DEFAULT_SEASONS)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--all-thresholds", action="store_true", help="sweep every threshold")
    args = parser.parse_args()

    api = StatsAPI()
    thresholds = sorted(THRESHOLDS["hitting"]) if args.all_thresholds else [args.threshold]
    summaries = [summarize(api, args.seasons, t) for t in thresholds]

    if args.json:
        print(json.dumps(summaries if args.all_thresholds else summaries[0], indent=2))
    else:
        for summary in summaries:
            render(summary)
        print(f"\n(api: {api.live_calls} live calls, {api.cache_hits} cache hits)")


if __name__ == "__main__":
    main()

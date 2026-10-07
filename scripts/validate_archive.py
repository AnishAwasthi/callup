#!/usr/bin/env python3
"""
Data-quality gate over the archived Statcast pull.

Run after ingestion and before building features. It checks the things that would
silently poison everything downstream:

* **Completeness** — is every scheduled game-date archived?
* **ID linkage** — do Statcast's ``pitcher``/``batter`` ids actually join to the Stats
  API player ids the cohort is keyed on? If this ever broke, the labels and the features
  would belong to different people and nothing would error.
* **Level separation** — the minors feed mixes Triple-A with the Florida State League and
  carries no level column, so the team-code join has to be doing its job.
* **Field coverage** — tracking columns should be near-complete on pitches. Contact
  columns are expected to be sparse, since they only exist on batted balls.

    python scripts/validate_archive.py
    python scripts/validate_archive.py --season 2024 --sample-every 15
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.cohort import build_cohort  # noqa: E402
from callup.ingest import DEFAULT_RAW_DIR, game_dates, load_days  # noqa: E402
from callup.statsapi import StatsAPI  # noqa: E402

# Near-complete on every tracked pitch.
PITCH_FIELDS = ["release_speed", "release_spin_rate", "pfx_x", "pfx_z"]
# Only populated on batted balls / final pitch of a plate appearance, so sparsity is
# correct here rather than a warning sign.
CONTACT_FIELDS = ["launch_speed", "launch_angle", "events"]

PITCH_COVERAGE_FLOOR = 0.95
LINKAGE_FLOOR = 0.75


def check_completeness(api: StatsAPI, raw_dir: Path, seasons, levels) -> bool:
    print("\nCompleteness")
    print("-" * 64)
    ok = True
    for level in levels:
        for season in seasons:
            expected = game_dates(api, season, level)
            missing = [d for d in expected if not (raw_dir / level / f"{d}.csv.gz").exists()]
            status = "OK" if not missing else f"MISSING {len(missing)}"
            print(f"  {level:4} {season}: {len(expected) - len(missing):>3}/{len(expected):<3} {status}")
            if missing:
                ok = False
                print(f"       first missing: {missing[:5]}")
    return ok


def check_season(api: StatsAPI, raw_dir: Path, season: int, sample_every: int) -> bool:
    paths = sorted((raw_dir / "AAA").glob(f"{season}-*.csv.gz"))[::sample_every]
    if not paths:
        print(f"\nNo archived AAA dates for {season}; run the ingest first.")
        return False

    frame = load_days(paths, team_levels=api.team_level_candidates(season))
    aaa = frame[frame["level"] == "AAA"]

    print(f"\nSample: {len(paths)} AAA dates from {season} -> {len(frame):,} rows")
    print("-" * 64)
    counts = frame["level"].value_counts(dropna=False)
    for level, n in counts.items():
        print(f"  level {str(level):5}: {n:>7,} rows")
    if aaa.empty:
        print("  no Triple-A rows found — the team-code join is broken")
        return False

    ok = True

    print("\nID linkage (Statcast ids -> Stats API cohort ids)")
    print("-" * 64)
    for group, column in (("pitching", "pitcher"), ("hitting", "batter")):
        cohort = build_cohort(api, [season], group, "moderate")
        cohort_ids = {p.player_id for p in cohort.labeled + cohort.promoted_thin + cohort.never_promoted}
        statcast_ids = set(aaa[column].dropna().astype(int))
        if not cohort_ids:
            continue
        share = len(cohort_ids & statcast_ids) / len(cohort_ids)
        # Pitchers legitimately score lower on a sampled run: a starter appears every
        # fifth day, so a sparse date sample misses many of them.
        flag = "OK" if share >= LINKAGE_FLOOR else "LOW"
        print(f"  {group:9}: {share:>6.1%} of cohort present in sample   {flag}")
        if share < LINKAGE_FLOOR:
            ok = False

    print("\nField coverage on Triple-A pitches")
    print("-" * 64)
    for field in PITCH_FIELDS:
        if field not in aaa.columns:
            print(f"  {field:20} MISSING COLUMN")
            ok = False
            continue
        coverage = aaa[field].notna().mean()
        flag = "OK" if coverage >= PITCH_COVERAGE_FLOOR else "LOW"
        print(f"  {field:20} {coverage:>6.1%}   {flag}")
        if coverage < PITCH_COVERAGE_FLOOR:
            ok = False

    print("\n  (contact fields are sparse by nature — they exist only on batted balls)")
    for field in CONTACT_FIELDS:
        if field in aaa.columns:
            print(f"  {field:20} {aaa[field].notna().mean():>6.1%}")

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--levels", nargs="+", default=["MLB", "AAA"])
    parser.add_argument("--season", type=int, default=2024, help="season to sample in depth")
    parser.add_argument("--sample-every", type=int, default=15)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args()

    api = StatsAPI()
    complete = check_completeness(api, args.raw_dir, args.seasons, args.levels)
    sane = check_season(api, args.raw_dir, args.season, args.sample_every)

    print("\n" + "=" * 64)
    if complete and sane:
        print("PASS — archive is complete and joins correctly.")
    else:
        print("FAIL — see the flags above before building features on this data.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

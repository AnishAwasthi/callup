#!/usr/bin/env python3
"""Prepare genuine starter counts and provisional wOBA labels; leave Week 1 features to teammates."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from callup.cohort import build_cohort
from callup.contract import validate
from callup.ingest import derive_levels
from callup.statsapi import StatsAPI

COUNTS = {"aaa_hits": "hits", "aaa_ab": "atBats", "aaa_bb": "baseOnBalls", "aaa_k": "strikeOuts", "aaa_hr": "homeRuns"}
PITCH_COLUMNS = ["batter", "pitcher", "game_pk", "at_bat_number", "pitch_number", "game_date", "game_type", "home_team", "away_team", "events", "description", "type", "launch_speed", "launch_angle", "woba_value", "woba_denom"]


def write_sample_pitches(sample_rows, parquet_dir, api):
    parts = []
    for year, players in sample_rows.groupby("season"):
        wanted = set(players.player_id)
        mapping = api.team_level_candidates(int(year))
        for path in sorted((parquet_dir / "AAA").glob(f"{year}-*.parquet")):
            chunk = pd.read_parquet(path, columns=PITCH_COLUMNS)
            chunk["batter"] = pd.to_numeric(chunk.batter, errors="raise").astype("int64")
            keep = chunk.batter.isin(wanted) & derive_levels(chunk, mapping).eq("AAA")
            parts.append(chunk.loc[keep].assign(level="AAA", data_kind="real"))
    pitches = pd.concat(parts)
    if pitches.empty or set(sample_rows.player_id) - set(pitches.batter):
        raise ValueError("Sample players have no matching raw pitches")
    pitches.to_csv("data/local_sample/pitches.csv", index=False)
    return len(pitches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet-dir", type=Path, default=Path("data/parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--sample-only", action="store_true", help="refresh sample pitch extraction from an existing prepared cohort")
    args = parser.parse_args()
    api = StatsAPI(offline=True)
    if args.sample_only:
        sample_rows = pd.read_csv("data/local_sample/hitter_seasons.csv")
        count = write_sample_pitches(sample_rows, args.parquet_dir, api)
        for path in (args.output / "preparation_report.json", Path("reports/cohort_preparation.json")):
            report = json.loads(path.read_text())
            report["sample_pitches"] = count
            path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Refreshed {len(sample_rows)} genuine player-seasons / {count} pitches")
        return
    for feed, years in (("AAA", (2023, 2024)), ("MLB", (2024, 2025))):
        for year in years:
            if not list((args.parquet_dir / feed).glob(f"{year}-*.parquet")):
                raise FileNotFoundError(f"Missing {feed} {year} Parquet inputs")
    cohorts = {y: build_cohort(api, [y], "hitting") for y in (2023, 2024)}
    pools = {y: c.labeled + c.promoted_thin + c.never_promoted for y, c in cohorts.items()}
    all_stats = {}
    for year in pools:
        for split in api.season_stats(year, "AAA", "hitting"):
            pid = split["player"]["id"]
            totals = all_stats.setdefault((year, pid), defaultdict(int))
            for out, source in COUNTS.items():
                totals[out] += int(split["stat"].get(source) or 0)
    summaries = {"AAA": defaultdict(lambda: defaultdict(float)), "MLB": defaultdict(lambda: defaultdict(float))}
    for requested in ("AAA", "MLB"):
        years = (2023, 2024) if requested == "AAA" else (2024, 2025)
        for year in years:
            mapping = api.team_level_candidates(year) if requested == "AAA" else None
            for path in sorted((args.parquet_dir / requested).glob(f"{year}-*.parquet")):
                frame = pd.read_parquet(path, columns=PITCH_COLUMNS)
                if mapping:
                    frame = frame[derive_levels(frame, mapping).eq("AAA")]
                for column in ("woba_value", "woba_denom", "launch_speed"):
                    frame[column] = pd.to_numeric(frame[column], errors="raise")
                for pid, chunk in frame.groupby("batter"):
                    item = summaries[requested][(year, int(pid))]
                    terminal = chunk[chunk.events.notna()]
                    denom = terminal.woba_denom.fillna(0)
                    item["pitches"] += len(chunk)
                    item["observed_pa"] += len(terminal)
                    item["woba_denom"] += denom.sum()
                    item["woba_numerator"] += terminal.woba_value.sum()
                    item["missing_woba"] += int((denom.gt(0) & terminal.woba_value.isna()).sum())
                    item["ev_observed"] += chunk.launch_speed.notna().sum()
                    dates = chunk.game_date
                    item["first_date"] = min(item.get("first_date", dates.min()), dates.min())
                    item["last_date"] = max(item.get("last_date", dates.max()), dates.max())
            print(f"Summarized {requested} {year}", flush=True)
    test_ids = {p.player_id for p in pools[2024]}
    rows = []
    for year, players in pools.items():
        for player in players:
            aaa = summaries["AAA"][(year, player.player_id)]
            mlb = summaries["MLB"][(year + 1, player.player_id)]
            reached = player.mlb_playing_time > 0
            eligible = player.mlb_playing_time >= 75
            available = eligible and mlb["woba_denom"] > 0 and mlb["missing_woba"] == 0
            split = "test" if year == 2024 else "excluded_overlap" if player.player_id in test_ids else "train"
            row = {"player_id": player.player_id, "name": player.name, "season": year, "outcome_year": year + 1, "prediction_date": f"{year+1}-01-01", "aaa_pa": int(player.aaa_playing_time), **all_stats[(year, player.player_id)], "aaa_observed_pitches": int(aaa["pitches"]), "aaa_observed_pa": int(aaa["observed_pa"]), "aaa_first_date": aaa.get("first_date"), "aaa_last_date": aaa.get("last_date"), "mlb_pa": int(player.mlb_playing_time), "reached_mlb": reached, "outcome_eligible": eligible, "label_available": bool(available), "mlb_woba": mlb["woba_numerator"] / mlb["woba_denom"] if available else None, "mlb_woba_numerator": mlb["woba_numerator"], "mlb_woba_denom": mlb["woba_denom"], "mlb_observed_pa": int(mlb["observed_pa"]), "mlb_first_date": mlb.get("first_date"), "mlb_last_date": mlb.get("last_date"), "outcome_status": "eligible" if eligible else "thin" if reached else "not_observed", "split": split, "label_provisional": True, "data_kind": "real"}
            rows.append(row)
    frame = pd.DataFrame(rows).sort_values(["season", "player_id"])
    validate(frame)
    if frame.duplicated(["player_id", "season"]).any():
        raise ValueError("Duplicate player-season")
    if set(frame.loc[frame.split.eq("train"), "player_id"]) & set(frame.loc[frame.split.eq("test"), "player_id"]):
        raise ValueError("Player leakage")
    args.output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output / "hitter_seasons.csv", index=False)
    frame.to_parquet(args.output / "hitter_seasons.parquet", index=False)
    pd.testing.assert_frame_equal(frame.reset_index(drop=True), pd.read_parquet(args.output / "hitter_seasons.parquet"))
    sample_rows = pd.concat([g.head(2) for _, g in frame.groupby(["season", "outcome_status"])]).drop_duplicates(["player_id", "season"])
    trace_row = frame.loc[frame.player_id.eq(664770) & frame.season.eq(2023)]
    sample_rows = pd.concat([sample_rows, trace_row]).drop_duplicates(["player_id", "season"])
    sample_dir = Path("data/local_sample")
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_rows.to_csv(sample_dir / "hitter_seasons.csv", index=False)
    sample_pitch_count = write_sample_pitches(sample_rows, args.parquet_dir, api)
    report = {"seasons": [2023, 2024], "pool": len(frame), "eligible": int(frame.outcome_eligible.sum()), "labels_available_provisional": int(frame.label_available.sum()), "reached": int(frame.reached_mlb.sum()), "thin": int(frame.outcome_status.eq("thin").sum()), "not_observed": int(frame.outcome_status.eq("not_observed").sum()), "splits": frame.groupby("split").agg(rows=("player_id", "size"), labels=("label_available", "sum")).to_dict("index"), "aaa_pa_mismatches": int(frame.aaa_pa.ne(frame.aaa_observed_pa).sum()), "mlb_pa_mismatches_among_reached": int((frame.reached_mlb & frame.mlb_pa.ne(frame.mlb_observed_pa)).sum()), "sample_rows": len(sample_rows), "sample_pitches": sample_pitch_count, "trace": trace_row.to_dict("records"), "limitations": ["wOBA is a provisional reconstruction from served Savant values, not an independently reconciled official season wOBA.", "Observed terminal events need not equal official PA; automatic/no-pitch events and source discrepancies require investigation.", "No 2026 pitch archive; September 3 cached 2026 API snapshot excluded."]}
    (args.output / "preparation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    # Aggregate metadata is safe to review without publishing source records.
    public = {k: v for k, v in report.items() if k != "trace"}
    Path("reports/cohort_preparation.json").write_text(json.dumps(public, indent=2) + "\n")
    (sample_dir / "player_trace.json").write_text(json.dumps(report["trace"], indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()

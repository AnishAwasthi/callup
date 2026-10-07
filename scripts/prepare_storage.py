#!/usr/bin/env python3
"""Audit every source file, convert non-destructively, and compare every cell."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duckdb
import pyarrow.parquet as pq

from callup.cohort import build_cohort
from callup.ingest import ROW_CAP, derive_levels, game_dates
from callup.statsapi import StatsAPI
from callup.storage import KEYS, check_gzip, read_source, sha256, source_table, verify_roundtrip


def benchmark(paths, output, repeats=3):
    selected = [paths[len(paths) * i // 6] for i in range(6)]
    columns = ["batter", "game_pk", "events", "launch_speed", "launch_angle", "woba_value", "woba_denom"]
    results = {}
    for kind in ("csv_full", "parquet_full", "csv_projected", "parquet_projected"):
        timings = []
        for _ in range(repeats):
            start = time.perf_counter()
            for path in selected:
                if kind.startswith("csv"):
                    if kind.endswith("full"):
                        read_source(path)
                    else:
                        import pandas as pd
                        pd.read_csv(path, usecols=columns, dtype="string", keep_default_na=False, na_values=[""])
                else:
                    target = output / path.parent.name / path.name.replace(".csv.gz", ".parquet")
                    pq.read_table(target, columns=columns if kind.endswith("projected") else None).to_pandas()
            timings.append(time.perf_counter() - start)
        results[kind] = {"median_seconds": statistics.median(timings), "runs_seconds": timings}
    return {"files": [str(p) for p in selected], "repeats": repeats, "note": "Warm OS cache; same six shards; materialized DataFrames. Not a cold/network benchmark.", "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/parquet"))
    parser.add_argument("--report", type=Path, default=Path("reports/storage.json"))
    args = parser.parse_args()
    api = StatsAPI(offline=True)
    paths = sorted(args.raw_dir.glob("*/*.csv.gz"))
    if not paths:
        raise SystemExit("No raw archive found")
    groups = defaultdict(lambda: {"files": 0, "rows": 0, "true_levels": Counter(), "nonmissing": Counter(), "aaa_rows": 0, "aaa_nonmissing": Counter()})
    ids = defaultdict(set)
    entries, problems, warnings, schemas = [], [], [], {}
    empty_dates = []
    for index, path in enumerate(paths, 1):
        digest = sha256(path)
        check_gzip(path)
        frame = read_source(path)
        season, requested = int(path.name[:4]), path.parent.name
        group = groups[f"{requested}/{season}"]
        if len(frame) >= ROW_CAP:
            problems.append(f"{path}: at row cap")
        if frame.empty:
            empty_dates.append(str(path))
        if frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
            problems.append(f"{path}: missing or duplicate pitch key")
        if not frame.game_type.eq("R").all() or not frame.game_date.eq(path.name[:10]).all():
            problems.append(f"{path}: game type/date mismatch")
        if requested == "AAA":
            mapping = api.team_level_candidates(season)
            true_level = derive_levels(frame, mapping)
            if true_level.isna().any():
                problems.append(f"{path}: unknown/mismatched team levels")
            group["true_levels"].update(true_level.fillna("UNKNOWN"))
            aaa = frame.loc[true_level.eq("AAA")]
            group["aaa_rows"] += len(aaa)
            group["aaa_nonmissing"].update(aaa.notna().sum().to_dict())
            for name in ("batter", "pitcher"):
                ids[(season, name)].update(aaa[name].dropna().astype(int))
        group["files"] += 1
        group["rows"] += len(frame)
        group["nonmissing"].update(frame.notna().sum().to_dict())
        table = source_table(frame)
        target = args.output / requested / path.name.replace(".csv.gz", ".parquet")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        pq.write_table(table, tmp, compression="zstd", compression_level=6)
        restored = pq.read_table(tmp)
        verify_roundtrip(frame, restored)
        tmp.replace(target)
        if sha256(path) != digest:
            raise RuntimeError(f"Source changed: {path}")
        schemas[str(target)] = {field.name: str(field.type) for field in table.schema}
        entries.append({"source": str(path), "target": str(target), "source_sha256": digest, "target_sha256": sha256(target), "rows": len(frame), "source_bytes": path.stat().st_size, "target_bytes": target.stat().st_size})
        if index % 100 == 0:
            print(f"Audited and verified {index}/{len(paths)} shards", flush=True)
    linkage = {}
    for key, group in groups.items():
        requested, year = key.split("/")
        actual = {p.name[:10] for p in paths if p.parent.name == requested and p.name.startswith(year)}
        expected = set(game_dates(api, int(year), requested))
        group["missing_dates"] = sorted(expected - actual)
        group["extra_dates"] = sorted(actual - expected)
        if expected != actual:
            problems.append(f"{key}: scheduled date mismatch")
        manifest = json.loads((args.raw_dir / requested / f"_manifest_{year}.json").read_text())
        if manifest["rows"] != group["rows"] or manifest["dates"] != group["files"]:
            problems.append(f"{key}: manifest mismatch")
        if requested == "AAA":
            for group_name, column in (("hitting", "batter"), ("pitching", "pitcher")):
                cohort = build_cohort(api, [int(year)], group_name)
                players = cohort.labeled + cohort.promoted_thin + cohort.never_promoted
                missing = sorted({p.player_id for p in players} - ids[(int(year), column)])
                linkage[f"{year}/{group_name}"] = {"cohort_players": len(players), "missing_ids": missing}
                if missing:
                    warnings.append(f"{year}/{group_name}: {len(missing)} cohort IDs absent from AAA archive")
    # Scheduled resume date produced no pitches: verify its official date's game is
    # represented before accepting a header-only response.
    for filename in empty_dates:
        path = Path(filename)
        requested, year, day = path.parent.name, int(path.name[:4]), path.name[:10]
        schedule = api.get("schedule", sportId=1 if requested == "MLB" else 11, startDate=f"{year}-03-01", endDate=f"{year}-11-15", gameType="R")
        games = [game for date in schedule.get("dates", []) if date["date"] == day for game in date.get("games", [])]
        explained = games and all(game.get("officialDate") != day and game.get("resumedFromDate") and (args.raw_dir / requested / f"{game['officialDate']}.csv.gz").exists() for game in games)
        if explained:
            official = {game["officialDate"] for game in games}
            found = set()
            for date in official:
                found.update(read_source(args.raw_dir / requested / f"{date}.csv.gz").game_pk.dropna().astype(int))
            explained = all(game["gamePk"] in found for game in games)
        if explained:
            warnings.append(f"{filename}: empty resume-date export; scheduled games found under officialDate")
        else:
            problems.append(f"{filename}: unexplained empty export")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    global_counts = connection.execute("SELECT count(*), count(DISTINCT struct_pack(game_pk := game_pk, at_bat_number := at_bat_number, pitch_number := pitch_number)) FROM read_parquet(?, union_by_name=true)", [str(args.output / "*" / "*.parquet")]).fetchone()
    connection.close()
    global_keys = {"rows": global_counts[0], "unique_keys": global_counts[1], "duplicates": global_counts[0] - global_counts[1]}
    if global_keys["duplicates"]:
        problems.append("Duplicate global pitch keys across shards")
    report = {"audit_problems": problems, "warnings": warnings, "empty_dates": empty_dates, "files": len(paths), "rows": sum(e["rows"] for e in entries), "source_bytes": sum(e["source_bytes"] for e in entries), "target_bytes": sum(e["target_bytes"] for e in entries), "all_cells_verified": True, "groups": dict(groups), "linkage": linkage, "benchmark": benchmark(paths, args.output), "entries": entries}
    report["global_pitch_keys"] = global_keys
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    Path("reports/pitch_schema.json").write_text(json.dumps(next(iter(schemas.values())), indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("files", "rows", "source_bytes", "target_bytes", "audit_problems")}, indent=2))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

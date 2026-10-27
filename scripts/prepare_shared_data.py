#!/usr/bin/env python3
"""Prepare the approved, frozen CSV snapshot for delivery by ordinary git pull."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from pathlib import Path


def checksum(handle):
    result = hashlib.sha256()
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        result.update(block)
    return result.hexdigest()


def digest(path):
    with path.open("rb") as source:
        return checksum(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="verified expanded CSV package root")
    parser.add_argument("--output", type=Path, default=Path("data/shared"))
    args = parser.parse_args()
    original = json.loads((args.source / "manifest.json").read_text())
    if args.output.exists():
        raise SystemExit("Use a new output folder; existing snapshots are preserved")
    args.output.mkdir(parents=True)
    files = {}
    for name, info in original["files"].items():
        if not name.startswith("data/") or not name.endswith(".csv"):
            continue
        source = args.source / name
        if source.stat().st_size != info["bytes"] or digest(source) != info["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}")
        relative = name.removeprefix("data/")
        if relative.startswith("pitches/"):
            relative += ".gz"
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".gz":
            with source.open("rb") as incoming, target.open("wb") as output:
                with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=6, mtime=0) as zipped:
                    shutil.copyfileobj(incoming, zipped)
            with gzip.open(target, "rb") as restored:
                if checksum(restored) != info["sha256"]:
                    raise ValueError(f"Compression changed CSV bytes: {relative}")
        else:
            shutil.copyfile(source, target)
        if target.stat().st_size >= 50 * 1024 * 1024:
            raise ValueError(f"Shared file exceeds the 50 MiB budget: {relative}")
        entry = {"bytes": target.stat().st_size, "sha256": digest(target),
                 "csv_bytes": info["bytes"], "csv_sha256": info["sha256"]}
        if "rows" in info:
            entry.update(rows=info["rows"], columns=info["columns"])
        else:
            with source.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                entry.update(columns=next(reader), rows=sum(1 for _ in reader))
        files[relative] = entry
        print(f"Verified {relative}: {entry['rows']:,} rows, {entry['bytes'] / 1_000_000:.1f} MB", flush=True)
    manifest = {"version": "shared-csv-v2", "distribution": "ordinary Git; no Git LFS",
                "base_release": original["base_release"], "base_zip_sha256": original["base_zip_sha256"],
                "source_data_refreshed": False, "old_aaa_columns_and_sample_verified_unchanged": True,
                "files": files}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output / "README.md").write_text(
        "# Shared team data\n\nThese files arrive with `git clone` or `git pull`. "
        "There is no separate data download or extraction step.\n\n"
        "Start with `processed/hitter_seasons.csv` (926 player-seasons). "
        "The `pitches/` folder has AAA 2023/2024 and MLB 2023/2024/2025 CSVs. "
        "Python reads compressed CSVs directly: `pd.read_csv(\"data/shared/pitches/aaa_2024.csv.gz\")`. "
        "AAA files already contain only Triple-A games; issues #1/#2 select `in_cohort=True`. "
        "MLB files include all hitters and have no cohort flag. The `local_sample/` folder has a five-player example.\n\n"
        "Added columns include pitch type, speed, spin, movement, location and pitcher handedness. "
        "`release_speed` is mph, `release_spin_rate` is rpm, and `pfx_x`/`pfx_z` are feet from the catcher's perspective. "
        "Empty values mean missing, not zero. Compare matching seasons and pitch types. "
        "Do not use following-year MLB measurements as predictors of that year's outcome.\n\n"
        "The original CSV columns and outcomes are preserved, and gzip decompression reproduces each verified CSV byte for byte. "
        "`manifest.json` records compressed and decompressed SHA-256 checksums, row counts and columns. "
        "This is the frozen research snapshot, not a live refresh. wOBA outcomes and venue mappings remain provisional. "
        "Source: MLB Baseball Savant and MLB Stats API. The source terms and unresolved source-specific redistribution license "
        "are documented in `docs/dataset-card.md`; publishing this copy does not grant an open-data license.\n\n"
        "Write generated feature tables and model outputs under ignored `data/processed/`. "
        "Treat this folder as read-only. The original compressed CSV archive and Parquet copies remain preserved separately.\n"
    )
    print(f"Total tracked CSV data: {sum(x['bytes'] for x in files.values()) / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()

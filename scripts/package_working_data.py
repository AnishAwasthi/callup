#!/usr/bin/env python3
"""Extend the frozen CSV release with pitch context, without changing old columns."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pyarrow.parquet as pq

from callup.ingest import derive_levels
from callup.statsapi import StatsAPI

BASE_SHA = "ed659ee9b8046b957d95ea45979e56db5acc67ca3c041ec898681ef1c2cccee2"
KEYS = ["game_pk", "at_bat_number", "pitch_number"]
EXTRA = ["pitch_type", "release_speed", "release_spin_rate", "pfx_x", "pfx_z",
         "p_throws", "plate_x", "plate_z", "sz_top", "sz_bot", "release_extension",
         "spin_axis", "woba_value", "woba_denom"]


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_csv(source):
    return pd.read_csv(source, dtype="string", keep_default_na=False, na_filter=False)


def append_context(base, context):
    if base.duplicated(KEYS).any() or context.duplicated(KEYS).any():
        raise ValueError("Duplicate pitch keys")
    indexed = context.set_index(KEYS)
    wanted = pd.MultiIndex.from_frame(base[KEYS])
    if not wanted.isin(indexed.index).all():
        raise ValueError("Source archive does not cover all original CSV pitch keys")
    updated = base.copy()
    updated[EXTRA] = indexed.reindex(wanted)[EXTRA].to_numpy()
    return updated.astype("string").fillna("")


def write_verified(frame, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, lineterminator="\n")
    pd.testing.assert_frame_equal(frame.reset_index(drop=True), read_csv(target))
    return {"rows": len(frame), "columns": list(frame.columns),
            "values_and_missing_positions_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-zip", type=Path, required=True)
    parser.add_argument("--parquet-dir", type=Path, default=Path("data/parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/incoming/callup-csv-v2"))
    args = parser.parse_args()
    if digest(args.base_zip) != BASE_SHA:
        raise SystemExit("Base ZIP does not match the frozen v1 release")
    if args.output.exists():
        raise SystemExit("Choose a new output folder; existing packages are preserved")
    root = args.output / "callup-csv"
    root.mkdir(parents=True)
    api = StatsAPI(offline=True)
    sources, files, sample_parts = {}, {}, []
    with ZipFile(args.base_zip) as base_zip:
        previous = json.loads(base_zip.read("callup-csv/manifest.json"))
        original_cols = previous["exports"][0]["columns"]
        sample = read_csv(base_zip.open("callup-csv/data/local_sample/pitches.csv"))
        sample_keys = pd.MultiIndex.from_frame(sample[KEYS])
        for rel in ["data/processed/hitter_seasons.csv", "data/teams.csv",
                    "data/local_sample/hitter_seasons.csv", "reports/cohort_preparation.json"]:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base_zip.read("callup-csv/" + rel))
        for feed, years in [("AAA", (2023, 2024)), ("MLB", (2023, 2024, 2025))]:
            for year in years:
                columns = [c for c in original_cols if c not in {"season", "in_cohort"}] + EXTRA
                parts = []
                paths = sorted((args.parquet_dir / feed).glob(f"{year}-*.parquet"))
                if not paths:
                    raise FileNotFoundError(f"No source Parquet files for {feed} {year}")
                mapping = api.team_level_candidates(year) if feed == "AAA" else None
                for path in paths:
                    chunk = pq.read_table(path, columns=columns).to_pandas()
                    if mapping is not None:
                        chunk = chunk.loc[derive_levels(chunk, mapping).eq("AAA")]
                    chunk = chunk.astype("string").fillna("")
                    chunk.insert(0, "season", str(year))
                    parts.append(chunk)
                    sources[str(path)] = digest(path)
                frame = pd.concat(parts, ignore_index=True).astype("string").fillna("")
                del parts, chunk
                if frame.duplicated(KEYS).any():
                    raise ValueError(f"Duplicate pitch keys in {feed} {year}")
                if feed == "AAA":
                    base = read_csv(base_zip.open(f"callup-csv/data/pitches/aaa_{year}.csv"))
                    if set(map(tuple, base[KEYS].to_numpy())) != set(map(tuple, frame[KEYS].to_numpy())):
                        raise ValueError("True AAA pitch keys changed from the v1 release")
                    frame = append_context(base, frame)
                    pd.testing.assert_frame_equal(frame[original_cols], base)
                    selected = pd.MultiIndex.from_frame(frame[KEYS]).isin(sample_keys)
                    sample_parts.append(frame.loc[selected, KEYS + EXTRA].copy())
                    del base
                rel = f"data/pitches/{feed.lower()}_{year}.csv"
                files[rel] = write_verified(frame, root / rel)
                print(f"Verified {rel}: {len(frame):,} rows; {len(frame.columns)} columns", flush=True)
                del frame
                gc.collect()
        enriched_sample = append_context(sample, pd.concat(sample_parts, ignore_index=True))
        pd.testing.assert_frame_equal(enriched_sample[original_cols], sample)
        files["data/local_sample/pitches.csv"] = write_verified(enriched_sample, root / "data/local_sample/pitches.csv")
    (root / "README.md").write_text(
        "# Callup CSV data\n\nRun `python scripts/download_working_data.py` from the cloned code repository. "
        "It installs these CSVs automatically. You do not need the original Parquet archive for team tasks.\n\n"
        "AAA 2023/2024 files contain actual Triple-A games. Issues #1/#2 select `in_cohort=True`; "
        "park research uses all AAA rows. MLB 2023/2024/2025 files contain all available MLB pitches, "
        "with no `in_cohort` flag. Compare matching seasons/types; use only pre-prediction information as features.\n\n"
        "Added fields include pitch type, release speed (mph), spin (rpm), horizontal/vertical movement "
        "(`pfx_x`/`pfx_z`, feet, catcher perspective), pitcher handedness, location, extension, spin axis, "
        "and served wOBA components. Blank cells remain missing. Source non-ID values retain their text; "
        "parse numeric fields explicitly. Old AAA columns, sample records, and outcome/split tables are unchanged.\n\n"
        "Player-season outcomes and venue mappings remain provisional. There is no new source redistribution "
        "license or written permission recorded; this package does not change that status.\n"
    )
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files.setdefault(rel, {}).update(bytes=path.stat().st_size, sha256=digest(path))
    manifest = {"version": 2, "base_release": "callup-csv-v1", "base_zip_sha256": BASE_SHA,
                "source_parquet_sha256": sources, "source_data_refreshed": False,
                "old_aaa_columns_and_sample_verified_unchanged": True, "files": files}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive = args.output / "callup-csv.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=6) as zip_out:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                info = ZipInfo("callup-csv/" + path.relative_to(root).as_posix(), (2026, 10, 26, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zip_out.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=6)
    archive.with_suffix(".zip.sha256").write_text(f"{digest(archive)}  {archive.name}\n")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size,
                      "sha256": digest(archive)}, indent=2))


if __name__ == "__main__":
    main()

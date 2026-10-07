#!/usr/bin/env python3
"""Prepare a local distribution tree. Does not upload, create accounts, or change billing."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from callup.storage import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/release"))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Release already exists; use a new --output to avoid stale files")
    if json.loads(Path("reports/storage.json").read_text())["audit_problems"]:
        raise SystemExit("Resolve archive audit problems before packaging")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise SystemExit("Commit the reviewed preparation code before packaging so provenance has an exact code revision")
    code_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    args.output.mkdir(parents=True)
    for name in ("raw", "cache", "parquet", "processed", "local_sample"):
        source = Path("data") / name
        if not source.is_dir():
            raise SystemExit(f"Missing preparation input: {source}")
        shutil.copytree(source, args.output / name)
    shutil.copyfile("docs/dataset-card.md", args.output / "README.md")
    (args.output / "reports").mkdir()
    for name in ("storage.json", "pitch_schema.json", "legacy_cohort_counts.json", "cohort_preparation.json"):
        shutil.copyfile(Path("reports") / name, args.output / "reports" / name)
    (args.output / "docs").mkdir()
    for name in ("data-contract.md", "methodology.md", "data-dictionary.md", "storage-comparison.md"):
        shutil.copyfile(Path("docs") / name, args.output / "docs" / name)
    source_files = [*Path("callup").glob("*.py"), *Path("scripts").glob("*.py"), Path("requirements-lock.txt")]
    (args.output / "provenance.json").write_text(json.dumps({"code_revision": code_revision, "source_code_sha256": {str(path): sha256(path) for path in sorted(source_files)}, "rights_status": "pending_written_permission"}, indent=2) + "\n")
    entries = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file():
            entries[path.relative_to(args.output).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    manifest = {"version": 1, "files": entries, "bytes": sum(x["bytes"] for x in entries.values()), "redistribution": "pending_written_permission"}
    checksum_file = args.output / "checksums.json"
    checksum_file.write_text(json.dumps(manifest, indent=2) + "\n")
    Path("reports/release_checksums.json").write_text(checksum_file.read_text())
    Path("reports/release_summary.json").write_text(json.dumps({"files": len(entries), "bytes": manifest["bytes"], "manifest_sha256": sha256(checksum_file), "upload_status": "not_published_rights_pending"}, indent=2) + "\n")
    print(f"Prepared {len(entries)} files, {manifest['bytes']:,} bytes. Local only; rights clearance pending.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Retrieve and verify an exact approved Hub revision using a committed lock file."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name:
        raise ValueError(f"Unsafe dataset path: {name}")
    return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("dataset-lock.json"))
    parser.add_argument("--output", type=Path, default=Path("data/incoming"))
    parser.add_argument("--install", action="store_true", help="copy verified inputs into data/; refuse differing existing files")
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    if not lock.get("repo_id") or not re.fullmatch(r"[0-9a-f]{40}", lock.get("revision") or "") or not re.fullmatch(r"[0-9a-f]{64}", lock.get("manifest_sha256") or ""):
        raise SystemExit("Dataset not published: lock requires repo_id, a 40-character commit SHA, and manifest SHA-256. See docs/data-access.md.")
    from huggingface_hub import hf_hub_download
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(hf_hub_download(repo_id=lock["repo_id"], repo_type="dataset", revision=lock["revision"], filename="checksums.json", local_dir=args.output))
    if digest(manifest_path) != lock["manifest_sha256"]:
        raise SystemExit("Checksum manifest does not match committed lock")
    manifest = json.loads(manifest_path.read_text())
    verified = []
    for name, expected in manifest["files"].items():
        safe_name(name)
        target = args.output / name
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise SystemExit(f"Symlink destination refused: {name}")
        downloaded = Path(hf_hub_download(repo_id=lock["repo_id"], repo_type="dataset", revision=lock["revision"], filename=name, local_dir=args.output))
        if downloaded.stat().st_size != expected["bytes"] or digest(downloaded) != expected["sha256"]:
            raise SystemExit(f"Integrity failure: {name}")
        verified.append((name, downloaded))
    if args.install:
        installs = [(Path("data") / name, source) for name, source in verified if PurePosixPath(name).parts[0] in {"raw", "cache", "parquet", "processed", "local_sample"}]
        # Validate every destination before writing any file.
        for target, source in installs:
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
                raise SystemExit(f"Symlink install path refused: {target}")
            if target.exists() and digest(target) != digest(source):
                raise SystemExit(f"Refusing to overwrite differing input: {target}")
        for target, source in installs:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    print(f"Verified {len(verified)} files at dataset revision {lock['revision']}")


if __name__ == "__main__":
    main()

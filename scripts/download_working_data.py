#!/usr/bin/env python3
"""Legacy release installer; current shared CSVs already arrive with git pull."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or path.as_posix() != name):
        raise ValueError(f"Unsafe package path: {name}")
    return path


def destination(root, name):
    path = root.joinpath(*safe_path(name).parts)
    for candidate in [path, *path.parents]:
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError(f"Data destination is a symlink: {candidate}")
    return path


def is_input(name):
    p = safe_path(name)
    return (name in {"data/processed/hitter_seasons.csv", "data/teams.csv",
                     "data/local_sample/hitter_seasons.csv", "data/local_sample/pitches.csv"}
            or (p.parent.as_posix() == "data/pitches" and p.suffix == ".csv"))


def install(archive, lock, root):
    if archive.stat().st_size != lock["bytes"] or digest(archive) != lock["sha256"]:
        raise ValueError("Dataset ZIP failed its checksum. No installed data were changed.")
    cache = destination(root, "data/incoming")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temp, ZipFile(archive) as package:
        members = package.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP paths")
        prefix = "callup-csv/"
        for member in members:
            safe_path(member.filename.rstrip("/"))
            if not member.filename.startswith(prefix) or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Unexpected package root or symlink")
        manifest = json.loads(package.read(prefix + "manifest.json"))
        entries = manifest.get("files")
        if entries is None:
            entries = {entry["path"]: entry for entry in manifest["exports"]}
        verified = []
        for name, expected in entries.items():
            safe_path(name)
            member = package.getinfo(prefix + name)
            if member.file_size != expected["bytes"]:
                raise ValueError(f"Size mismatch: {name}")
            staged = Path(temp).joinpath(*safe_path(name).parts)
            staged.parent.mkdir(parents=True, exist_ok=True)
            with package.open(member) as source, staged.open("wb") as target:
                shutil.copyfileobj(source, target)
            if digest(staged) != expected["sha256"]:
                raise ValueError(f"Checksum mismatch: {name}")
            if is_input(name):
                target = destination(root, name)
                if target.exists() and not target.is_file():
                    raise ValueError(f"Expected a file: {target}")
                verified.append((staged, target, name, expected["sha256"]))
        # All files/paths are checked before replacing any inputs. Preserve changed inputs.
        installed = unchanged = backed_up = 0
        for staged, target, name, expected_sha in verified:
            if target.exists():
                old_sha = digest(target)
                if old_sha == expected_sha:
                    unchanged += 1
                    continue
                backup = destination(root, f"data/incoming/backups/{old_sha}/{name}")
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backed_up += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                with staged.open("rb") as source:
                    shutil.copyfileobj(source, output)
            temporary.replace(target)
            installed += 1
        receipt = destination(root, "data/incoming/working-data-installed.json")
        receipt.write_text(json.dumps({"release": lock["release"], "sha256": lock["sha256"],
                                       "files": entries}, indent=2) + "\n")
        print(f"Team CSV data ready: {installed} installed, {unchanged} already current.")
        if backed_up:
            print(f"Preserved {backed_up} previous inputs in data/incoming/backups/.")
        print("Start with data/processed/hitter_seasons.csv. Pitch CSVs are in data/pitches/.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, help="explicit legacy release lock")
    parser.add_argument("--archive", type=Path, help="use an already downloaded ZIP (offline)")
    parser.add_argument("--output-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if args.lock is None and args.archive is None and (root / "data/shared/manifest.json").is_file():
        print("The team data already arrived with Git; no download is needed.")
        print("Use data/shared/processed/hitter_seasons.csv and data/shared/pitches/*.csv.gz.")
        return
    args.lock = args.lock or ROOT / "working-data-lock.json"
    try:
        lock = json.loads(args.lock.read_text())
        archive = args.archive
        if archive is None:
            archive = destination(root, f"data/incoming/{lock['release']}.zip")
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists() or digest(archive) != lock["sha256"]:
                print(f"Downloading team CSV data ({lock['bytes'] / 1_000_000:.1f} MB)...", flush=True)
                request = urllib.request.Request(lock["url"], headers={"User-Agent": "callup-data-download/1"})
                with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as target:
                    temporary = Path(target.name)
                    try:
                        with urllib.request.urlopen(request, timeout=180) as response:
                            shutil.copyfileobj(response, target)
                    except Exception:
                        temporary.unlink(missing_ok=True)
                        raise
                if temporary.stat().st_size != lock["bytes"] or digest(temporary) != lock["sha256"]:
                    temporary.unlink()
                    raise ValueError("Downloaded ZIP failed its checksum; retry the command.")
                temporary.replace(archive)
        install(archive, lock, root)
    except (OSError, ValueError, KeyError, BadZipFile, urllib.error.URLError) as error:
        raise SystemExit(f"Data download failed: {error}") from error


if __name__ == "__main__":
    main()

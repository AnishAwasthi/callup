import hashlib
import json
import sys
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from scripts.download_working_data import install, safe_path
from scripts.download_working_data import main as download_main
from scripts.package_working_data import EXTRA, KEYS, append_context


def package(tmp_path, payloads=None, bad_hash=False, extra_path=None, legacy=False):
    payloads = payloads or {"data/pitches/aaa_2024.csv": b"batter,speed\n1,95.00\n"}
    archive = tmp_path / "test.zip"
    manifest = {"files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in payloads.items()}}
    if bad_hash:
        manifest["files"][next(iter(payloads))]["sha256"] = "0" * 64
    if legacy:
        manifest = {"exports": [{"path": name, **entry} for name, entry in manifest["files"].items()]}
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        output.writestr("callup-csv/manifest.json", json.dumps(manifest))
        for name, data in payloads.items():
            output.writestr("callup-csv/" + name, data)
        if extra_path:
            output.writestr(extra_path, b"bad")
    lock = {"release": "test-v2", "bytes": archive.stat().st_size,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    return archive, lock


def test_install_repeat_and_backup_preserves_generated_work(tmp_path):
    archive, lock = package(tmp_path)
    root = tmp_path / "clone"
    old = root / "data/pitches/aaa_2024.csv"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old data")
    generated = root / "data/processed/features_basic.csv"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"my work")
    install(archive, lock, root)
    install(archive, lock, root)
    assert old.read_bytes() == b"batter,speed\n1,95.00\n"
    backups = list((root / "data/incoming/backups").rglob("aaa_2024.csv"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"old data"
    assert generated.read_bytes() == b"my work"
    assert not (root / "README.md").exists()


def test_bad_zip_checksum_installs_nothing(tmp_path):
    archive, lock = package(tmp_path)
    lock["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="ZIP failed"):
        install(archive, lock, tmp_path / "clone")
    assert not (tmp_path / "clone/data/pitches").exists()


def test_existing_public_csv_release_manifest_supported(tmp_path):
    archive, lock = package(tmp_path, legacy=True)
    install(archive, lock, tmp_path / "clone")
    assert (tmp_path / "clone/data/pitches/aaa_2024.csv").read_bytes() == b"batter,speed\n1,95.00\n"


def test_git_snapshot_needs_no_legacy_download(tmp_path, monkeypatch, capsys):
    shared = tmp_path / "data/shared"
    shared.mkdir(parents=True)
    (shared / "manifest.json").write_text("{}")
    monkeypatch.setattr(sys, "argv", ["download_working_data.py", "--output-root", str(tmp_path)])
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: pytest.fail("Unexpected network"))
    download_main()
    assert "already arrived with Git" in capsys.readouterr().out
    assert not (tmp_path / "data/incoming").exists()


def test_bad_member_hash_installs_nothing(tmp_path):
    archive, lock = package(tmp_path, bad_hash=True)
    with pytest.raises(ValueError, match="Checksum mismatch"):
        install(archive, lock, tmp_path / "clone")
    assert not (tmp_path / "clone/data/pitches").exists()


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a/../b", "a\\b", "C:/file", "a//b"])
def test_unsafe_paths_refused(name):
    with pytest.raises(ValueError):
        safe_path(name)


def test_zip_traversal_refused(tmp_path):
    archive, lock = package(tmp_path, extra_path="callup-csv/../../outside")
    with pytest.raises(ValueError, match="Unsafe package path"):
        install(archive, lock, tmp_path / "clone")
    assert not (tmp_path / "outside").exists()


def test_symlink_destination_refused_before_any_install(tmp_path):
    archive, lock = package(tmp_path, {
        "data/processed/hitter_seasons.csv": b"new roster",
        "data/pitches/aaa_2024.csv": b"new pitches",
    })
    root = tmp_path / "clone"
    (root / "data/processed").mkdir(parents=True)
    roster = root / "data/processed/hitter_seasons.csv"
    roster.write_bytes(b"old roster")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "data/pitches").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        install(archive, lock, root)
    assert roster.read_bytes() == b"old roster"
    assert not list(outside.iterdir())


def test_pitch_context_join_preserves_ids_missing_values_and_row_order():
    base = pd.DataFrame({KEYS[0]: ["2", "1"], KEYS[1]: ["3", "3"],
                         KEYS[2]: ["4", "4"], "events": ["", "NA"]}, dtype="string")
    context = base[KEYS].iloc[::-1].copy()
    for column in EXTRA:
        context[column] = pd.array(["95.000", ""], dtype="string")
    joined = append_context(base, context)
    pd.testing.assert_frame_equal(joined[base.columns], base)
    assert joined[EXTRA[0]].tolist() == ["", "95.000"]
    with pytest.raises(ValueError, match="Duplicate"):
        append_context(base, pd.concat([context, context]))
    with pytest.raises(ValueError, match="does not cover"):
        append_context(base, context.iloc[:1])

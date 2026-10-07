import hashlib
import json
import shutil
import sys
import types
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from callup.contract import load, validate
from callup.ingest import derive_levels
from callup.statsapi import StatsAPI
from callup.storage import source_table, verify_roundtrip
from scripts.download_dataset import main as download_main
from scripts.download_dataset import safe_name


def test_lossless_roundtrip_preserves_ids_nulls_and_tokens(tmp_path):
    frame = pd.DataFrame({"batter": ["664770", None], "value": ["1.250000", "NA"], "name": ["José, A", "NULL"], "all_missing": [None, None]}, dtype="string")
    table = source_table(frame)
    path = tmp_path / "data.parquet"
    pq.write_table(table, path, compression="zstd")
    verify_roundtrip(frame, pq.read_table(path))
    restored = pd.read_parquet(path)
    assert restored.batter.iloc[0] == 664770
    assert pd.isna(restored.batter.iloc[1])
    changed = frame.copy()
    changed.loc[0, "value"] = "1.25"
    with pytest.raises(ValueError, match="Values/null"):
        verify_roundtrip(changed, table)


def test_noncanonical_id_refused():
    with pytest.raises(ValueError, match="Noncanonical"):
        source_table(pd.DataFrame({"batter": ["0664770"]}, dtype="string"))


def test_columbus_columbia_collision_resolved_by_opponent():
    frame = pd.DataFrame({"home_team": ["COL", "COL", "DUR", "COL", "UNKNOWN"], "away_team": ["DUR", "BRD", "COL", "COL", "DUR"]})
    result = derive_levels(frame, {"COL": frozenset({"AAA", "A"}), "DUR": frozenset({"AAA"}), "BRD": frozenset({"A"})})
    assert result.iloc[:3].tolist() == ["AAA", "A", "AAA"]
    assert result.iloc[3:].isna().all()


def test_offline_cache_miss_never_fetches(tmp_path, monkeypatch):
    api = StatsAPI(cache_dir=tmp_path, offline=True)
    monkeypatch.setattr(api, "_fetch", lambda url: pytest.fail("Network attempted"))
    with pytest.raises(FileNotFoundError):
        api.get("teams")


def test_demo_contract_and_leakage_rejected():
    frame = load(Path("data/sample/hitter_seasons.csv"))
    train = frame.loc[frame.split.eq("train")].iloc[[0]].copy()
    train["season"] = 2024
    train["outcome_year"] = 2025
    train["prediction_date"] = "2025-01-01"
    train["split"] = "test"
    with pytest.raises(ValueError, match="Player overlap"):
        validate(pd.concat([frame, train]))


@pytest.mark.parametrize("name", ["../secret", "/tmp/secret", "a/../../secret", "a\\b", "a//b"])
def test_download_path_traversal_refused(name):
    with pytest.raises(ValueError):
        safe_name(name)


def test_pinned_download_verifies_before_install_and_preserves_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    content = b"preserved source bytes"
    (source / "pitch.gz").write_bytes(content)
    manifest = {"files": {"raw/AAA/pitch.gz": {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}}}
    (source / "checksums.json").write_text(json.dumps(manifest))
    manifest_digest = hashlib.sha256((source / "checksums.json").read_bytes()).hexdigest()
    revision = "a" * 40
    Path("dataset-lock.json").write_text(json.dumps({"repo_id": "example/dataset", "revision": revision, "manifest_sha256": manifest_digest}))
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        target = Path(kwargs["local_dir"]) / kwargs["filename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / ("checksums.json" if kwargs["filename"] == "checksums.json" else "pitch.gz"), target)
        return str(target)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(hf_hub_download=fake_download))
    monkeypatch.setattr(sys, "argv", ["download_dataset.py", "--install"])
    download_main()
    assert Path("data/raw/AAA/pitch.gz").read_bytes() == content
    assert all(call["revision"] == revision and call["repo_type"] == "dataset" for call in calls)
    Path("data/raw/AAA/pitch.gz").write_bytes(b"local original")
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        download_main()
    assert Path("data/raw/AAA/pitch.gz").read_bytes() == b"local original"
    Path("dataset-lock.json").write_text(json.dumps({"repo_id": "example/dataset", "revision": revision, "manifest_sha256": "0" * 64}))
    with pytest.raises(SystemExit, match="manifest does not match"):
        download_main()

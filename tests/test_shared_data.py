import csv
import gzip
import json
from pathlib import Path

from scripts.prepare_shared_data import checksum, digest

ROOT = Path(__file__).resolve().parents[1] / "data/shared"


def test_shared_files_and_csv_bytes_match_frozen_manifest():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["old_aaa_columns_and_sample_verified_unchanged"]
    for name, entry in manifest["files"].items():
        path = ROOT / name
        assert path.stat().st_size == entry["bytes"] < 50 * 1024 * 1024
        assert digest(path) == entry["sha256"], name
        opener = gzip.open if name.endswith(".gz") else open
        with opener(path, "rb") as source:
            assert checksum(source) == entry["csv_sha256"], name


def test_shared_study_and_sample_are_distinct_and_complete():
    with (ROOT / "processed/hitter_seasons.csv").open(newline="") as source:
        hitters = list(csv.DictReader(source))
    with (ROOT / "local_sample/hitter_seasons.csv").open(newline="") as source:
        sample = list(csv.DictReader(source))
    assert len(hitters) == 926
    keys = {(p["player_id"], p["season"]) for p in hitters}
    assert len(keys) == 926
    assert len(sample) == 5
    assert {(p["player_id"], p["season"]) for p in sample}.issubset(keys)
    train = {p["player_id"] for p in hitters if p["split"] == "train"}
    test = {p["player_id"] for p in hitters if p["split"] == "test"}
    assert not train & test


def test_pandas_can_read_compressed_pitch_columns_directly():
    import pandas as pd

    columns = ["batter", "pitch_type", "release_speed", "release_spin_rate", "pfx_x", "pfx_z"]
    for name in ["aaa_2024.csv.gz", "mlb_2024.csv.gz"]:
        frame = pd.read_csv(ROOT / "pitches" / name, usecols=columns, nrows=30)
        assert len(frame) == 30
        assert set(frame.columns) == set(columns)

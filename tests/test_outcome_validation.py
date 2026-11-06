import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from callup.outcome_validation import PILOT, compare_reference, load_references
from scripts import validate_outcomes

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "validation/references/fangraphs_woba_pilot.json"


@pytest.fixture
def inputs():
    row = pd.Series(dict(player_id=1, name="Fixture Hitter", season=2023,
                         outcome_year=2024, split="train", mlb_woba=0.3004,
                         mlb_woba_numerator=30.04, mlb_woba_denom=100,
                         mlb_pa=100, mlb_observed_pa=102,
                         mlb_first_date="2024-04-01", mlb_last_date="2024-09-01"))
    ref = dict(player_id=1, name="Fixture Hitter", season=2023, outcome_year=2024,
               source="FanGraphs", url="https://www.fangraphs.com/players/fixture/1/stats/batting",
               retrieved_at="2026-10-30T01:48:11+00:00", source_player_id=1,
               identity_url="https://baseballsavant.mlb.com/savant-player/fixture-1",
               identity_method="synthetic fixture", identity_verified=True,
               scope="MLB regular season; all teams; observed wOBA", precision=3,
               woba="0.300", pa=100)
    return row, ref


def test_rounding_and_signed_difference(inputs):
    row, ref = inputs
    original = row.copy()
    result = compare_reference(row, ref)
    assert result["difference"] == pytest.approx(0.0004)
    assert result["rounding_tolerance"] == 0.0005
    assert result["status"] == "consistent_with_rounding"
    pd.testing.assert_series_equal(row, original)
    row["mlb_woba"] = 0.29
    result = compare_reference(row, ref)
    assert result["difference"] == pytest.approx(-0.01)
    assert result["absolute_difference"] == pytest.approx(0.01)
    assert result["status"] == "unresolved_definition_difference"


@pytest.mark.parametrize("field,value", [("player_id", 2), ("outcome_year", 2025),
                                         ("season", 2024), ("name", "Other Hitter"),
                                         ("identity_verified", False), ("woba", None),
                                         ("scope", "postseason"), ("source", "local pitches"),
                                         ("url", "https://example.com/reference"),
                                         ("retrieved_at", "")])
def test_unmatched_or_unavailable_reference_stays_unresolved(inputs, field, value):
    row, ref = inputs
    ref[field] = value
    result = compare_reference(row, ref)
    assert result["status"] == "unresolved_reference"
    assert result["reference_woba"] is None
    assert result["difference"] is None


def test_pa_difference_does_not_claim_definite_error(inputs):
    row, ref = inputs
    ref["pa"] = 101
    result = compare_reference(row, ref)
    assert result["reference_pa_difference"] == 1
    assert result["status"] == "unresolved_coverage_difference"


@pytest.mark.parametrize("field,value", [("woba", "nan"), ("precision", -1), ("pa", -1)])
def test_invalid_reference_values_rejected(inputs, field, value):
    row, ref = inputs
    ref[field] = value
    with pytest.raises(ValueError):
        compare_reference(row, ref)


def test_reference_fixture_preserves_original_capture():
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == "53ea0bf329607fadef5e422a710dadb89f29520d65d8021a10988c9ecd2e5d30"
    references = load_references(REFERENCE)
    assert {(r["player_id"], r["season"]) for r in references} == set(PILOT)
    assert [r["woba"] for r in references] == ["0.351", "0.319", "0.301", "0.357", "0.353"]
    for reference in references:
        assert reference["source"] == "FanGraphs"
        assert reference["outcome_year"] == reference["season"] + 1
        assert reference["retrieved_at"] == "2026-10-30T01:48:11+00:00"
        assert reference["precision"] == 3
        assert str(reference["source_player_id"]) in reference["url"]
        assert str(reference["player_id"]) in reference["identity_url"]


@pytest.mark.parametrize("field", ["url", "retrieved_at", "retrieval_method", "precision", "evidence", "identity_url"])
def test_reference_loading_requires_provenance(tmp_path, field):
    document = json.loads(REFERENCE.read_text())
    del document["references"][0][field]
    path = tmp_path / "references.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="provenance"):
        load_references(path)


@pytest.mark.parametrize("change", ["duplicate", "extra", "missing", "naive_timestamp"])
def test_reference_loading_rejects_invalid_pilot(tmp_path, change):
    document = json.loads(REFERENCE.read_text())
    records = document["references"]
    if change == "duplicate":
        records[1] = records[0]
    elif change == "extra":
        records.append(records[0])
    elif change == "missing":
        records.pop()
    else:
        records[0]["retrieved_at"] = "2026-10-30T01:48:11"
    path = tmp_path / "references.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_references(path)


def test_default_and_override_reproduce_without_ignored_reference(tmp_path, monkeypatch):
    # A clone-like layout: only the tracked reference and shared inputs are present.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "validation/references").mkdir(parents=True)
    fixture = tmp_path / "validation/references/fangraphs_woba_pilot.json"
    fixture.write_bytes(REFERENCE.read_bytes())
    (tmp_path / "data").mkdir()
    (tmp_path / "data/shared").symlink_to(ROOT / "data/shared", target_is_directory=True)
    monkeypatch.setattr(validate_outcomes, "__file__", str(tmp_path / "scripts/validate_outcomes.py"))
    monkeypatch.setattr(validate_outcomes.subprocess, "check_output", lambda args, **kwargs: "fixture-revision\n" if args[1] == "rev-parse" else "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_outcomes.py"])
    validate_outcomes.main()
    output = tmp_path / "data/processed/outcome_validation_comparison.csv"
    first = output.read_bytes()
    assert not (output.parent / "outcome_validation_references.json").exists()
    monkeypatch.setattr(sys, "argv", ["validate_outcomes.py", "--references", str(fixture)])
    validate_outcomes.main()
    assert output.read_bytes() == first
    comparison = pd.read_csv(output)
    assert len(comparison) == 5
    assert comparison.reference_woba.tolist() == [0.351, 0.319, 0.301, 0.357, 0.353]
    assert comparison.difference.tolist() == pytest.approx([
        0.0126363636363636, 0.0113359683794466, 0.009,
        0.0159646697388634, 0.0113067846607669,
    ])
    assert comparison.status.eq("unresolved_definition_difference").all()
    assert comparison.reference_pa_difference.eq(0).all()

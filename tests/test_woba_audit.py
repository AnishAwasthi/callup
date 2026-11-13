import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from callup.contract import load
from callup.outcome_validation import load_references
from callup.woba_audit import compare_audit, discrepancy_summary, reconstruct
from scripts import audit_woba

ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / "validation/references/fangraphs_woba_audit.json").read_text())
BASIC = AUDIT["formulas"]["basic"]["weights"]
SEASONAL = AUDIT["formulas"]["standard"]["weights"]


@pytest.fixture
def synthetic():
    return pd.DataFrame({
        "events": ["single", "walk", "intent_walk", "sac_bunt", "field_error", "fielders_choice",
                   "catcher_interf", "field_out", "truncated_pa", "home_run", "hit_by_pitch", "sac_fly"],
        "woba_value": [.9, .7, .4, .2, .9, .9, .7, 0, 0, 2, .7, 0],
        "woba_denom": [1, 1, np.nan, 0, 1, 1, 1, np.nan, 0, 1, 1, 1],
    })


def test_three_formulas_and_exact_attribution(synthetic):
    original = synthetic.copy(deep=True)
    result, events, anomalies = reconstruct(synthetic, SEASONAL["2024"], BASIC)
    assert result["served_n"] == pytest.approx(7.4)
    assert result["served_d"] == 8
    assert result["archive_pa"] == 11  # Truncated row is not an official PA.
    assert result["standard_d"] == 8  # Excludes IBB, SH, CI, truncated; includes missing out.
    assert result["standard_n"] == pytest.approx(4.341)
    assert result["basic_n"] == pytest.approx(5.0)  # Basic includes .7 for IBB.
    assert result["basic_diagnostic"] == pytest.approx(5 / 11)
    explained = sum(result[key] for key in ["nonstandard_numerator_effect", "denominator_effect", "coefficient_effect"])
    assert explained == pytest.approx(result["prepared_reconstruction"] - result["standard_diagnostic"])
    assert result["missing_out_denominators"] == 1
    assert {"field_out", "truncated_pa", "intent_walk", "sac_bunt", "catcher_interf"}.issubset(set(anomalies.events))
    assert events.served_n.sum() == pytest.approx(7.4)
    pd.testing.assert_frame_equal(synthetic, original)


def test_missing_handling_is_reproduced_not_silently_validated(synthetic):
    synthetic.loc[0, "woba_value"] = np.nan
    result, _, _ = reconstruct(synthetic, SEASONAL["2024"], BASIC)
    assert result["missing_positive_denominator_values"] == 1
    assert result["served_n"] == pytest.approx(6.5)


def test_unknown_event_and_zero_denominator_fail(synthetic):
    with pytest.raises(ValueError, match="Unmapped"):
        reconstruct(synthetic.assign(events="unknown"), SEASONAL["2024"], BASIC)
    with pytest.raises(ValueError, match="Positive"):
        reconstruct(synthetic.assign(woba_denom=0), SEASONAL["2024"], BASIC)


def test_summary_signed_absolute_and_nonrandom_scope():
    rows = pd.DataFrame({"player_id": [1, 1, 2], "signed_discrepancy": [.01, -.02, np.nan],
                         "standard_residual": [0, .001, np.nan], "basic_residual": [.002, -.003, np.nan]})
    result = discrepancy_summary(rows)
    assert result["n_rows"] == 3 and result["n_references"] == 2 and result["n_players"] == 2
    assert result["mean_signed"] == pytest.approx(-.005)
    assert result["mean_absolute"] == pytest.approx(.015)
    assert result["n_positive"] == result["n_negative"] == 1
    assert "no population significance" in result["inference"]


def test_references_and_component_provenance():
    references = load_references(ROOT / "validation/references/fangraphs_woba_pilot.json") + AUDIT["additional_references"]
    assert len({(r["player_id"], r["season"]) for r in references}) == 10
    assert len(AUDIT["independent_components"]) == 10
    for reference in references:
        assert reference["source"] == "FanGraphs" and reference["identity_verified"]
        assert reference["outcome_year"] == reference["season"] + 1
        assert reference["scope"] == "MLB regular season; all teams; observed wOBA"
        assert reference["precision"] == 3 and reference["retrieved_at"]
    assert AUDIT["formulas"]["basic"]["denominator"] == "PA"


def test_original_pilot_reconstruction_and_coverage():
    frame = load(ROOT / "data/shared/processed/hitter_seasons.csv")
    references = load_references(ROOT / "validation/references/fangraphs_woba_pilot.json")
    components = {(r["player_id"], r["season"]): r for r in AUDIT["independent_components"]}
    expected = {.3511011235955056: 664770, .31872047244094487: 687401,
                .30127027027027026: 676632, .35640950920245396: 691406, .35269309838472834: 695578}
    missing = {664770: 1, 687401: 2, 676632: 0, 691406: 1, 695578: 3}
    for year in [2024, 2025]:
        pitches = pd.read_csv(ROOT / f"data/shared/pitches/mlb_{year}.csv.gz", usecols=["batter", "events", "woba_value", "woba_denom"])
        for reference in references:
            if reference["outcome_year"] != year:
                continue
            pid, season = reference["player_id"], reference["season"]
            row = frame.loc[frame.player_id.eq(pid) & frame.season.eq(season)].iloc[0]
            result, _, _ = reconstruct(pitches.loc[pitches.batter.eq(pid)], SEASONAL[str(year)], BASIC)
            compared = compare_audit(row, reference, components[pid, season], result)
            assert result["standard_diagnostic"] == pytest.approx(next(value for value, player in expected.items() if player == pid))
            assert result["missing_out_denominators"] == missing[pid]
            assert compared["component_mismatches"] == "{}"
            sum_parts = sum(compared[key] for key in ["nonstandard_numerator_effect", "denominator_effect", "coefficient_effect", "standard_residual"])
            assert sum_parts == pytest.approx(compared["signed_discrepancy"])
            wrong_reference = {**reference, "outcome_year": year + 1}
            with pytest.raises(ValueError, match="identity/season"):
                compare_audit(row, wrong_reference, components[pid, season], result)


def test_audit_cli_is_offline_reproducible_and_separate(tmp_path, monkeypatch):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "callup").mkdir()
    (tmp_path / "validation/references").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/shared").symlink_to(ROOT / "data/shared", target_is_directory=True)
    for name in ["fangraphs_woba_pilot.json", "fangraphs_woba_audit.json"]:
        (tmp_path / "validation/references" / name).write_bytes((ROOT / "validation/references" / name).read_bytes())
    for name in ["callup/woba_audit.py", "scripts/audit_woba.py", "scripts/prepare_analysis.py"]:
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    monkeypatch.setattr(audit_woba, "__file__", str(tmp_path / "scripts/audit_woba.py"))
    monkeypatch.setattr(audit_woba.subprocess, "check_output", lambda args, **kwargs: "test\n" if args[1] == "rev-parse" else "")
    audit_woba.main()
    output = tmp_path / "data/processed/woba_audit"
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    audit_woba.main()
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    comparisons = pd.read_csv(output / "comparisons.csv")
    assert len(comparisons) == 10 and comparisons.reference_woba.notna().all()
    assert comparisons.component_mismatches.eq("{}").all()
    assert comparisons.signed_discrepancy.gt(0).all()
    assert set(comparisons.split) == {"train", "test", "excluded_overlap"}
    assert set(comparisons.outcome_year) == {2024, 2025}
    assert not (output.parent / "predictions.csv").exists()
    assert not (output.parent / "model_metrics.json").exists()

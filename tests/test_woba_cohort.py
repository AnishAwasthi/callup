"""Guard independent identity, completeness, precision and full-cohort reconciliation."""
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from callup.contract import load
from callup.woba_cohort import (
    difference_summary,
    match_record,
    parse_leaderboard,
    reconcile,
    validate_references,
)
from scripts.audit_woba_cohort import run

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "validation/references/fangraphs_woba_cohort_v1.json"


def test_parser_preserves_source_precision_and_rejects_incomplete_scope():
    params = dict(season=2024, season1=2024, stats="bat", qual="0", team=0, ind=0,
                  month=0, postseason="", level="mlb")
    query = {"queryKey": ["leaders/major-league/data", params], "state": {
        "data": {"data": [{"Season": 2024, "wOBA": .318714123456789}], "totalCount": 1},
        "dataUpdatedAt": 123}}

    def html(q):
        return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({
            "props": {"pageProps": {"dehydratedState": {"queries": [q]}}}}) + '</script>'

    records, _ = parse_leaderboard(html(query), 2024)
    assert records[0]["wOBA"] == Decimal("0.318714123456789")
    bad = copy.deepcopy(query)
    bad["state"]["data"]["totalCount"] = 2
    with pytest.raises(ValueError, match="Incomplete"):
        parse_leaderboard(html(bad), 2024)
    bad = copy.deepcopy(query)
    bad["queryKey"][1]["postseason"] = "Y"
    with pytest.raises(ValueError, match="scope"):
        parse_leaderboard(html(bad), 2024)


def test_matching_never_uses_name_and_does_not_sum_team_rows():
    rows = [{"xMLBAMID": 1, "Season": 2024, "playerid": 10, "PlayerName": "Same Name"},
            {"xMLBAMID": 2, "Season": 2024, "playerid": 20, "PlayerName": "Same Name"},
            {"xMLBAMID": 1, "Season": 2025, "playerid": 10}]
    assert match_record(1, 2024, rows) == ("matched", rows[0])
    assert match_record(3, 2024, rows) == ("unmatched", None)
    assert match_record(1, 2024, rows + [rows[0]]) == ("ambiguous", None)


def test_reference_duplicate_and_conflicting_id_rejected():
    cohort = load(ROOT / "data/shared/processed/hitter_seasons.csv").loc[lambda f: f.label_available]
    document = json.loads(REFERENCE.read_text())
    assert len(validate_references(document, cohort)) == 239
    document["references"].append(document["references"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_references(document, cohort)
    document = json.loads(REFERENCE.read_text())
    document["references"][1]["source_player_id"] = document["references"][0]["source_player_id"]
    with pytest.raises(ValueError, match="Conflicting"):
        validate_references(document, cohort)


def test_summary_uses_signed_median_and_maximum_absolute():
    result = difference_summary([-.02, .01, None])
    assert result["n"] == 2
    assert result["mean_signed"] == pytest.approx(-.005)
    assert result["mean_absolute"] == pytest.approx(.015)
    assert result["median_signed"] == pytest.approx(-.005)
    assert result["max_absolute"] == .02


def test_full_cohort_offline_preserves_frozen_data_and_identifies_attribution(tmp_path):
    protected = [p for p in (ROOT / "data/shared").rglob('*') if p.is_file()]
    protected += [p for p in [ROOT / 'data/processed/model_metrics.json', ROOT / 'data/processed/predictions.csv'] if p.exists()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    rows = run(output=tmp_path)
    assert len(rows) == 239 and rows.player_id.nunique() == 207
    assert rows.match_status.eq("matched").all()
    assert rows.reference_woba.notna().all()
    assert rows.component_mismatches.eq('{}').sum() == 238
    assert rows.adopted_as_target.eq(False).all()  # noqa: E712
    assert rows.groupby('outcome_year').size().to_dict() == {2024: 114, 2025: 125}
    assert rows.groupby('split').size().to_dict() == {'excluded_overlap': 52, 'test': 125, 'train': 62}
    anomaly = rows.loc[rows.name.eq('Trey Sweeney')].iloc[0]
    assert anomaly.component_mismatches == '{"ab": 1, "pa": 1}'
    assert anomaly.reconciliation_status == 'unresolved_component_difference'
    assert rows.internal_pa_gap.ne(0).sum() == 1
    assert rows.missing_required_denominators.sum() == 168
    assert rows.truncated_pa.sum() == 106
    references = validate_references(json.loads(REFERENCE.read_text()), rows)
    prepared = load(ROOT / "data/shared/processed/hitter_seasons.csv").loc[lambda f: f.label_available].iloc[0]
    internal = rows.loc[rows.player_id.eq(prepared.player_id) & rows.season.eq(prepared.season)].iloc[0].to_dict()
    unverified = reconcile(prepared, internal, None)
    assert unverified['reference_woba'] is None
    assert unverified['reconciliation_status'] == 'not_independently_verified'
    assert len(references) == 239
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected} == before
    first = (tmp_path / 'reconciliation.csv').read_bytes()
    run(output=tmp_path)
    assert (tmp_path / 'reconciliation.csv').read_bytes() == first
    assert pd.read_csv(tmp_path / 'anomalies.csv').game_pk.notna().all()

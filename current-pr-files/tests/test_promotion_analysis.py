import pandas as pd
import pytest

from scripts.promotion_analysis import add_rates, check_totals, summarize


@pytest.fixture
def sample():
    # Player 1 returns in a second season; eligibility need not imply a usable label.
    return add_rates(pd.DataFrame({
        "player_id": [1, 2, 1], "season": [2023, 2023, 2024],
        "outcome_status": ["not_observed", "eligible", "eligible"],
        "reached_mlb": [False, True, True], "outcome_eligible": [False, True, True],
        "label_available": [False, False, True], "mlb_woba": [None, None, .3],
        "aaa_pa": [200, 300, 400], "aaa_ab": [0, 200, 300],
        "aaa_hits": [0, 50, 90], "aaa_bb": [0, 30, 40],
        "aaa_k": [40, 60, 80], "aaa_hr": [0, 10, 20],
        "aaa_observed_pa": [200, 290, 400], "aaa_observed_pitches": [800, 1100, 1600],
    }))


def test_distinct_players_and_separate_selection_counts(sample):
    summary = summarize(sample)["participation_summary"]
    total = summary.loc[summary.season.isna() & summary.group_by.eq("all")].iloc[0]
    assert (total.n_rows, total.n_players) == (3, 2)
    assert (total.n_reached, total.n_eligible, total.n_label_available) == (2, 2, 1)
    assert total.label_rate == pytest.approx(1 / 3)
    assert total.participation_rate == pytest.approx(2 / 3)
    eligible = summary.loc[summary.season.isna() & summary.group_by.eq("outcome_eligible") & summary.group.eq("true")].iloc[0]
    assert eligible.label_rate == .5


def test_empty_groups_and_missing_values_remain_missing(sample, tmp_path):
    tables = summarize(sample)
    empty = tables["participation_summary"].query("group_by == 'outcome_status' and group == 'thin'")
    assert empty.n_rows.eq(0).all()
    assert empty.participation_rate.isna().all()
    assert pd.isna(sample.aaa_batting_average.iloc[0])
    assert sample.aaa_bb_rate.iloc[0] == 0  # Observed zero is not missing.
    missing = tables["missing_values"]
    total = missing.loc[missing.season.isna() & missing.group_by.eq("all") & missing.field.eq("mlb_woba")].iloc[0]
    assert (total.n_missing, total.n_total) == (2, 3)
    assert total.missing_rate == pytest.approx(2 / 3)
    path = tmp_path / "summary.csv"
    empty.to_csv(path, index=False, na_rep="")
    assert pd.read_csv(path).label_rate.isna().all()


def test_preparation_report_mismatch_fails(sample):
    report = {"pool": 3, "reached": 2, "eligible": 2, "labels_available_provisional": 1,
              "thin": 0, "not_observed": 1, "seasons": [2023, 2024]}
    assert check_totals(sample, report)["pool"] == 3
    report["pool"] = 4
    with pytest.raises(ValueError, match="pool"):
        check_totals(sample, report)

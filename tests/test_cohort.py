"""Cohort construction tests. No network: the API is faked."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.cohort import build_cohort  # noqa: E402
from callup.statsapi import innings_to_float  # noqa: E402


class FakeAPI:
    """Stands in for StatsAPI. ``rows`` is keyed by (season, level, group)."""

    def __init__(self, rows):
        self.rows = rows

    def season_stats(self, season, level, group):
        return self.rows.get((season, level, group), [])


def split(player_id, name, **stat):
    return {"player": {"id": player_id, "fullName": name}, "stat": stat}


# --- innings_to_float ------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [("150.0", 150.0), ("150.1", 150 + 1 / 3), ("150.2", 150 + 2 / 3), ("0.1", 1 / 3), ("7", 7.0)],
)
def test_innings_decimal_is_thirds_not_tenths(raw, expected):
    """
    Baseball writes a third of an inning as ".1" and two thirds as ".2". Reading the
    string as a plain float understates a full season by several innings and silently
    shifts every playing-time threshold.
    """
    assert innings_to_float(raw) == pytest.approx(expected)


def test_innings_handles_missing_and_garbage():
    assert innings_to_float(None) == 0.0
    assert innings_to_float("") == 0.0
    assert innings_to_float("not-an-inning") == 0.0


def test_innings_float_differs_from_naive_parse():
    """Guard the actual bug: naive float() and the correct value must not agree."""
    assert innings_to_float("150.2") != pytest.approx(float("150.2"))


# --- cohort partitioning ---------------------------------------------------------

def _hitting_api():
    return FakeAPI(
        {
            (2024, "AAA", "hitting"): [
                split(1, "Labeled Larry", plateAppearances=400),
                split(2, "Thin Theo", plateAppearances=400),
                split(3, "Stuck Sam", plateAppearances=400),
                split(4, "Parttime Pete", plateAppearances=40),  # below AAA floor
            ],
            (2025, "MLB", "hitting"): [
                split(1, "Labeled Larry", plateAppearances=300),  # clears MLB floor
                split(2, "Thin Theo", plateAppearances=10),  # promoted, too thin
            ],
        }
    )


def test_cohort_splits_into_three_disjoint_groups():
    cohort = build_cohort(_hitting_api(), [2024], "hitting", "moderate")

    assert [p.player_id for p in cohort.labeled] == [1]
    assert [p.player_id for p in cohort.promoted_thin] == [2]
    assert [p.player_id for p in cohort.never_promoted] == [3]
    assert cohort.pool_size == 3  # player 4 never entered the pool


def test_players_below_the_aaa_floor_are_excluded_entirely():
    cohort = build_cohort(_hitting_api(), [2024], "hitting", "moderate")
    everyone = cohort.labeled + cohort.promoted_thin + cohort.never_promoted
    assert 4 not in {p.player_id for p in everyone}


def test_censoring_rate_counts_thin_samples_as_censored():
    """
    A player who was promoted but got 10 plate appearances has no usable outcome. He is
    censored for modeling purposes even though he did reach the majors -- conflating the
    two is how the selection problem gets hidden.
    """
    cohort = build_cohort(_hitting_api(), [2024], "hitting", "moderate")
    assert cohort.promotion_rate == pytest.approx(2 / 3)  # players 1 and 2 reached MLB
    assert cohort.label_rate == pytest.approx(1 / 3)  # only player 1 is usable
    assert cohort.censoring_rate == pytest.approx(2 / 3)


def test_traded_player_seasons_are_summed_not_duplicated():
    """A midseason trade produces one split per org; the player must appear once."""
    api = FakeAPI(
        {
            (2024, "AAA", "hitting"): [
                split(9, "Traded Terry", plateAppearances=90),
                split(9, "Traded Terry", plateAppearances=90),
            ],
            (2025, "MLB", "hitting"): [],
        }
    )
    cohort = build_cohort(api, [2024], "hitting", "moderate")
    assert len(cohort.never_promoted) == 1
    assert cohort.never_promoted[0].aaa_playing_time == 180  # clears the 150 floor


def test_pitching_cohort_uses_innings_with_thirds():
    api = FakeAPI(
        {
            (2024, "AAA", "pitching"): [split(5, "Inning Ian", inningsPitched="39.2")],
            (2025, "MLB", "pitching"): [],
        }
    )
    # 39.2 IP is 39 2/3, which clears the 40-inning floor only if parsed as thirds...
    cohort = build_cohort(api, [2024], "pitching", "moderate")
    assert cohort.pool_size == 0  # 39.67 < 40, correctly excluded

    api.rows[(2024, "AAA", "pitching")] = [split(5, "Inning Ian", inningsPitched="40.1")]
    assert build_cohort(api, [2024], "pitching", "moderate").pool_size == 1


def test_thresholds_trade_sample_size_against_label_quality():
    api = FakeAPI(
        {
            (2024, "AAA", "hitting"): [split(i, f"P{i}", plateAppearances=120) for i in range(10)],
            (2025, "MLB", "hitting"): [split(i, f"P{i}", plateAppearances=60) for i in range(10)],
        }
    )
    assert build_cohort(api, [2024], "hitting", "moderate").pool_size == 0  # 120 < 150
    loose = build_cohort(api, [2024], "hitting", "loose")
    assert len(loose.labeled) == 10  # 120 >= 100 and 60 >= 50

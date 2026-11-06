"""Park-factor prototype checks on invented data (not baseball analysis)."""
import itertools

import numpy as np
import pandas as pd
import pytest

from callup.parks import (
    OUTPUT_COLUMNS,
    home_away_sums,
    home_parks,
    plate_appearances,
    player_adjusted,
    pooled_sums,
    prototype,
    ratio_factors,
    schedule_venues,
    shrink,
)

PARKS = {"AAA": 1, "BBB": 2, "CCC": 3}
TEAMS = pd.DataFrame({
    "season": 2023, "team_id": [10, 20, 30], "abbreviation": list(PARKS), "league": "Invented League",
    "default_venue_id": list(PARKS.values()), "default_venue_name": ["Park A", "Park B", "Park C"],
})


def invented_pitches(boost=1.2, quality=None, season=2023, relocate=True):
    """Each team hosts every other team four times; park 1 inflates PA values by ``boost``."""
    quality = quality or {}
    games, rows = [], []
    for home, away in itertools.permutations(PARKS, 2):
        games += [(home, away, PARKS[home])] * 4
    if relocate:
        games.append(("BBB", "AAA", PARKS["AAA"]))  # makeup game played in the visitor's park
    for game_pk, (home, away, venue) in enumerate(games, start=season * 1000):
        for at_bat in range(40):
            batting, fielding = (away, home) if at_bat % 2 == 0 else (home, away)
            value = 0.6 * (at_bat % 4 < 2) * (boost if venue == 1 else 1.0) * quality.get(batting, 1.0)
            rows.append({
                "season": season, "game_pk": game_pk, "at_bat_number": at_bat + 1,
                "batter": PARKS[batting] * 100 + at_bat % 9, "pitcher": PARKS[fielding] * 100 + 50,
                "home_team": home, "away_team": away, "events": "single" if value else "field_out",
                "woba_value": value, "woba_denom": 1.0,
            })
    pitches = pd.DataFrame(rows)
    schedule = pitches.drop_duplicates("game_pk")[["game_pk"]].assign(split_venue=False)
    schedule["venue_id"] = [venue for *_, venue in games]
    return pitches, schedule


def test_schedule_keeps_played_games_and_blanks_split_venues():
    def game(pk, state, venue):
        return {"gamePk": pk, "status": {"detailedState": state}, "venue": {"id": venue}}

    payload = {"dates": [
        {"games": [game(1, "Postponed", 9), game(2, "Final", 2), game(3, "Cancelled", 3)]},
        {"games": [game(1, "Final", 1), game(2, "Final", 5), game(4, "Completed Early", 4)]},
    ]}
    games = schedule_venues(payload).set_index("game_pk")
    assert list(games.index) == [1, 2, 4]
    assert games.loc[1, "venue_id"] == 1 and games.loc[4, "venue_id"] == 4
    assert games.loc[2, "split_venue"] and pd.isna(games.loc[2, "venue_id"])


def test_plate_appearances_drop_missing_denominators_and_split_games():
    pitches, schedule = invented_pitches()
    pitches.loc[0, "woba_denom"] = np.nan
    pitches.loc[1, "events"] = np.nan  # non-terminal pitch
    schedule.loc[schedule.index[-1], ["venue_id", "split_venue"]] = [pd.NA, True]
    pa = plate_appearances(pitches, schedule)
    assert len(pa) == len(pitches) - 2 - 40
    with pytest.raises(ValueError, match="no played venue"):
        plate_appearances(pitches, schedule.iloc[1:])


def test_hitter_park_is_above_one_and_relocated_game_counts_at_actual_park():
    pitches, schedule = invented_pitches()
    pa = plate_appearances(pitches, schedule)
    output, comparison, audit = prototype(pa, TEAMS, min_pa=100)
    assert list(output.columns) == OUTPUT_COLUMNS
    assert not output.duplicated(["season", "home_team"]).any()
    factor = output.set_index("home_team").factor
    assert factor["AAA"] > 1 > factor["BBB"] and factor["CCC"] < 1
    assert output.reference_scale.eq("1.0").all() and output.provisional.all()
    assert audit.set_index("home_team").loc["BBB", "n_relocated_games"] == 1
    assert output.set_index("home_team").loc["AAA", "n_home_pa"] == 9 * 40
    assert comparison.method.nunique() == 3


def test_single_season_ratio_is_normalized_and_corrects_for_own_park():
    pa = plate_appearances(*invented_pitches(relocate=False))
    parks = home_parks(pa, TEAMS)
    frame = ratio_factors(home_away_sums(pa, parks), parks, min_pa=100)
    assert np.average(frame.factor, weights=frame.n_home_pa) == pytest.approx(1.0)
    frame = frame.set_index("home_team")
    assert frame.loc["AAA", "raw_factor"] == pytest.approx(1.2)
    # Raw ratios overstate the gap (B's road games include A's park); the correction recovers 1.2.
    assert frame.loc["AAA", "raw_factor"] / frame.loc["BBB", "raw_factor"] == pytest.approx(1.32)
    assert frame.loc["AAA", "factor"] / frame.loc["BBB", "factor"] == pytest.approx(1.2)


def test_small_samples_stay_blank_not_neutral():
    output, comparison, _ = prototype(plate_appearances(*invented_pitches()), TEAMS, min_pa=10_000)
    assert output.factor.isna().all() and comparison.factor.isna().all()


def test_shrinkage_moves_toward_one_and_noise_only_gives_one():
    frame = pd.DataFrame({"season": 2023, "factor": [1.2, 0.9, 1.0, 1.05], "se_log": 0.05})
    shrunk = shrink(frame)
    assert (np.abs(np.log(shrunk)) <= np.abs(np.log(frame.factor)) + 1e-12).all()
    assert shrink(frame.assign(se_log=1.0)).eq(1.0).all()


def test_pooling_uses_same_park_and_never_later_seasons():
    sums = pd.DataFrame({
        "season": [2022, 2023, 2024, 2022, 2023, 2024], "home_team": ["AAA"] * 3 + ["BBB"] * 3,
        "park_id": [1, 1, 1, 7, 2, 2], "n_home_pa": [10, 20, 40, 10, 20, 40], "home_sum": 1.0, "home_sq": 1.0,
        "n_away_pa": [10, 20, 40, 10, 20, 40], "away_sum": 1.0, "away_sq": 1.0,
    })
    pooled = pooled_sums(sums, 2023).set_index("home_team")
    assert pooled.loc["AAA", "n_home_pa"] == 30 and pooled.loc["AAA", "seasons_used"] == 2
    assert pooled.loc["BBB", "n_home_pa"] == 20 and pooled.loc["BBB", "seasons_used"] == 1


def test_player_model_separates_strong_team_from_neutral_parks():
    pa = plate_appearances(*invented_pitches(boost=1.0, quality={"AAA": 1.5}))
    factors = player_adjusted(pa, penalty=0.0, iterations=50)
    assert factors.factor.to_numpy() == pytest.approx(1.0, abs=0.01)
    boosted = player_adjusted(plate_appearances(*invented_pitches(boost=1.3))).set_index("venue_id").factor
    assert boosted[1] > 1.1 and boosted[2] < 1 and boosted[3] < 1

#!/usr/bin/env python3
"""Build batted-ball features for every study player-season (issue #2).

Reads Triple-A pitch data for 2023 and 2024, keeps balls put in play by
study players, and summarizes each player-season:

    Exit velocity    ev_mean, ev_p90, ev_max, hard_hit_rate (95+ mph)
    Launch angle     la_mean, la_median, la_std
    Counts           n_bbe, n_ev, n_la, n_hard_hit
    Coverage         ev_coverage, la_coverage  (share of batted balls measured)

Output: data/processed/features_batted.csv, one row for each of the 926
study player-seasons.

Decisions
---------
* A batted ball is a pitch with description == "hit_into_play". Fouls are
  left out even when they have launch data, because the at-bat continues.
* Only games where both teams are in data/shared/teams.csv are kept.
* A pitch is identified by (game_pk, at_bat_number, pitch_number). If a
  duplicate ever appears, the first copy is kept and a warning is printed.
* Missing measurements stay blank, never zero. Count columns are 0 when a
  player had pitches but no batted balls, and blank when the player has no
  pitch data at all.
* ev_p90 uses linear interpolation (the pandas default). la_std is the
  sample standard deviation, so it is blank with fewer than 2 values.
* Coverage by season is printed pooled: total measured / total batted balls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# --- Settings -----------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "data" / "shared"

PITCH_FILES = [
    SHARED / "pitches" / "aaa_2023.csv.gz",
    SHARED / "pitches" / "aaa_2024.csv.gz",
]
TEAMS_CSV = SHARED / "teams.csv"
HITTER_SEASONS = SHARED / "processed" / "hitter_seasons.csv"
OUT_CSV = ROOT / "data" / "processed" / "features_batted.csv"

EXPECTED_STUDY_ROWS = 926
HARD_HIT_MPH = 95.0

PITCH_COLUMNS = [
    "season", "game_pk", "at_bat_number", "pitch_number", "batter",
    "home_team", "away_team", "description",
    "launch_speed", "launch_angle", "in_cohort",
]
PITCH_KEY = ["game_pk", "at_bat_number", "pitch_number"]
COUNT_COLUMNS = ["n_bbe", "n_ev", "n_la", "n_hard_hit"]

OUTPUT_COLUMNS = [
    "player_id", "season",
    "ev_mean", "ev_p90", "ev_max", "hard_hit_rate",
    "la_mean", "la_median", "la_std",
    "n_bbe", "n_ev", "n_la", "n_hard_hit",
    "ev_coverage", "la_coverage",
]


# --- Loading ------------------------------------------------------------------

def load_study_rows() -> pd.DataFrame:
    """The 926 player-seasons that must appear in the output."""
    study = pd.read_csv(HITTER_SEASONS, usecols=["player_id", "season"])
    study = study.astype({"player_id": "int64", "season": "int64"})

    assert len(study) == EXPECTED_STUDY_ROWS, (
        f"Expected {EXPECTED_STUDY_ROWS} study rows, got {len(study)}"
    )
    return study


def load_aaa_teams() -> set[str]:
    """Team codes for Triple-A clubs."""
    teams = pd.read_csv(TEAMS_CSV, usecols=["pitch_codes"])
    return set(teams["pitch_codes"].dropna())


def load_pitches(aaa_teams: set[str]) -> pd.DataFrame:
    """Pitches from Triple-A games, thrown to study players, without duplicates."""
    seasons = []

    for path in PITCH_FILES:
        pitches = pd.read_csv(path, usecols=PITCH_COLUMNS)

        # Fail loudly if a refresh ever stores numbers as text.
        for column in ["launch_speed", "launch_angle"]:
            pitches[column] = pd.to_numeric(pitches[column], errors="raise")
        pitches = pitches.astype({"batter": "int64", "season": "int64"})

        # Keep games where both teams are Triple-A.
        both_aaa = (
            pitches["home_team"].isin(aaa_teams)
            & pitches["away_team"].isin(aaa_teams)
        )
        if not both_aaa.all():
            print(f"  {path.name}: dropped {(~both_aaa).sum():,} non-AAA rows")
        pitches = pitches[both_aaa]

        # Keep study players. The column must be true/false, not text.
        assert pitches["in_cohort"].dtype == bool, (
            f"in_cohort is {pitches['in_cohort'].dtype}, expected bool"
        )
        pitches = pitches[pitches["in_cohort"]]

        seasons.append(pitches)

    pitches = pd.concat(seasons, ignore_index=True)

    n_duplicates = pitches.duplicated(subset=PITCH_KEY).sum()
    if n_duplicates:
        print(f"WARNING: {n_duplicates} duplicate pitches; keeping the first copy.",
              file=sys.stderr)
        pitches = pitches.drop_duplicates(subset=PITCH_KEY, keep="first")

    return pitches


# --- Calculations -------------------------------------------------------------

def filter_batted_balls(pitches: pd.DataFrame) -> pd.DataFrame:
    """Balls put in play. Fouls are excluded."""
    return pitches[pitches["description"] == "hit_into_play"].copy()


def summarize_batted_balls(batted: pd.DataFrame) -> pd.DataFrame:
    """One row per player-season. Missing measurements are skipped, not zeroed."""
    batted = batted.assign(is_hard_hit=batted["launch_speed"] >= HARD_HIT_MPH)

    summary = batted.groupby(["batter", "season"]).agg(
        n_bbe=("launch_speed", "size"),
        n_ev=("launch_speed", "count"),
        n_la=("launch_angle", "count"),
        n_hard_hit=("is_hard_hit", "sum"),
        ev_mean=("launch_speed", "mean"),
        ev_p90=("launch_speed", lambda ev: ev.quantile(0.90)),
        ev_max=("launch_speed", "max"),
        la_mean=("launch_angle", "mean"),
        la_median=("launch_angle", "median"),
        la_std=("launch_angle", "std"),
    )

    # Rates use only measured batted balls (0/0 gives a blank).
    summary["hard_hit_rate"] = summary["n_hard_hit"] / summary["n_ev"]
    summary["ev_coverage"] = summary["n_ev"] / summary["n_bbe"]
    summary["la_coverage"] = summary["n_la"] / summary["n_bbe"]

    return summary.reset_index().rename(columns={"batter": "player_id"})


def join_to_study(study: pd.DataFrame, summary: pd.DataFrame,
                  pitches: pd.DataFrame) -> pd.DataFrame:
    """Attach features to all study rows.

    Counts become 0 for players who had pitches but no batted balls, and
    stay blank for players with no pitch data.
    """
    result = study.merge(summary, on=["player_id", "season"], how="left")

    had_pitches = (
        pitches[["batter", "season"]]
        .drop_duplicates()
        .rename(columns={"batter": "player_id"})
        .assign(had_pitches=True)
    )
    result = result.merge(had_pitches, on=["player_id", "season"], how="left")
    seen = result["had_pitches"].fillna(False).astype(bool)

    for column in COUNT_COLUMNS:
        result.loc[seen & result[column].isna(), column] = 0
        result[column] = result[column].astype("Int64")

    assert len(result) == EXPECTED_STUDY_ROWS, (
        f"Expected {EXPECTED_STUDY_ROWS} output rows, got {len(result)}"
    )
    return result[OUTPUT_COLUMNS]


def print_coverage_by_season(result: pd.DataFrame) -> None:
    print("\nCoverage by season (measured / batted balls):")
    for season, rows in result.groupby("season"):
        total = rows["n_bbe"].sum()
        no_data = rows["n_bbe"].isna().sum()
        print(f"  {season}: exit velocity {rows['n_ev'].sum() / total:.3f}, "
              f"launch angle {rows['n_la'].sum() / total:.3f}, "
              f"study rows with no pitch data {no_data}")


# --- Main ---------------------------------------------------------------------

def main() -> None:
    study = load_study_rows()

    aaa_teams = load_aaa_teams()
    print(f"{len(aaa_teams)} Triple-A team codes")

    pitches = load_pitches(aaa_teams)
    print(f"{len(pitches):,} study-player pitches in Triple-A games")

    batted = filter_batted_balls(pitches)
    print(f"{len(batted):,} batted balls")

    summary = summarize_batted_balls(batted)
    result = join_to_study(study, summary, pitches)
    print_coverage_by_season(result)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {len(result)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
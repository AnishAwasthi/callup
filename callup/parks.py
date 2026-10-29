"""Triple-A park factors on a 1.0 neutral scale, keyed by (season, home_team).

Games are assigned to the venue where they were actually played (MLB Stats API schedule),
not to the nominal home team: a few makeup games each season are played in the visitor's
park. Three methods are provided so they can be compared:

* ``home_away_ratio``: one season; offense in a team's park / offense in that team's
  road games, corrected for the team never visiting its own park, then normalized so the
  home-PA-weighted league average is 1.0. Leagues never play each other, so factors compare
  parks only within the International League or the Pacific Coast League.
* ``home_away_shrunk``: the same home ratio pooled over the target season and the season before
  (same venue only), then shrunk toward 1.0 by empirical Bayes. Recommended starting point.
* ``player_adjusted``: an additive ridge model of each PA with batter-season, pitcher-season
  and venue effects. Controls for who played where and links the two leagues through players
  who appeared in both; normalized to all of Triple-A.

Factors stay blank when either side of the comparison has fewer than ``min_pa`` PAs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REFERENCE_SCALE = "1.0"
OUTPUT_COLUMNS = ["season", "home_team", "park_id", "factor", "reference_scale", "n_home_pa", "n_away_pa", "method", "provisional"]
PITCH_COLUMNS = ["season", "game_pk", "at_bat_number", "batter", "pitcher", "home_team", "away_team", "events", "woba_value", "woba_denom"]
STATS = {"woba": "wOBA per wOBA-denominator PA", "hr_rate": "home runs per wOBA-denominator PA"}
PLAYED = {"Final", "Completed Early"}


def schedule_venues(payload: dict) -> pd.DataFrame:
    """One row per played game from a Stats API ``schedule`` response; postponed entries dropped.

    A suspended game appears once per date it was played. When its parts were played in
    different venues, ``venue_id`` is blank and ``split_venue`` is true: the pitch rows do not
    say which PAs happened where, so those games cannot be assigned to one park.
    """
    rows = [
        {"game_pk": game["gamePk"], "venue_id": game["venue"]["id"]}
        for date in payload.get("dates", [])
        for game in date["games"]
        if game["status"]["detailedState"] in PLAYED
    ]
    games = pd.DataFrame(rows, columns=["game_pk", "venue_id"]).groupby("game_pk").venue_id.agg(["first", "nunique"])
    games = pd.DataFrame({"venue_id": games["first"].astype("Int64"), "split_venue": games["nunique"].gt(1)}).reset_index()
    games.loc[games.split_venue, "venue_id"] = pd.NA
    return games


def plate_appearances(pitches: pd.DataFrame, games: pd.DataFrame, stat: str = "woba") -> pd.DataFrame:
    """Terminal pitches with a wOBA denominator of 1, joined to the venue actually used.

    PAs with a missing denominator are dropped, not scored as zero, as are PAs from games
    split across venues. ``value`` is the PA's contribution to the chosen statistic.
    """
    if stat not in STATS:
        raise ValueError(f"Unknown statistic {stat!r}; choose from {sorted(STATS)}")
    pa = pitches.loc[pitches.events.notna() & pitches.woba_denom.eq(1)].copy()
    if pa.duplicated(["game_pk", "at_bat_number"]).any():
        raise ValueError("Duplicate PA key")
    pa["value"] = pa.woba_value.astype(float) if stat == "woba" else pa.events.eq("home_run").astype(float)
    pa = pa.merge(games[["game_pk", "venue_id", "split_venue"]], on="game_pk", how="left", validate="many_to_one")
    if pa.split_venue.isna().any():
        missing = pa.loc[pa.split_venue.isna(), "game_pk"].nunique()
        raise ValueError(f"{missing} games have no played venue in the schedule")
    pa = pa[~pa.split_venue.astype(bool)].drop(columns="split_venue")
    pa["venue_id"] = pa.venue_id.astype("int64")
    return pa


def home_parks(pa: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Each team-season's park: the venue of most nominal home games, checked against teams.csv."""
    games = pa.drop_duplicates("game_pk")
    counts = games.groupby(["season", "home_team", "venue_id"]).size().rename("n_games").reset_index()
    counts = counts.sort_values("n_games", ascending=False)
    parks = counts.drop_duplicates(["season", "home_team"]).rename(columns={"venue_id": "park_id"})
    totals = games.groupby(["season", "home_team"]).size().rename("n_home_games")
    parks = parks.join(totals, on=["season", "home_team"])
    parks["n_relocated_games"] = parks.n_home_games - parks.n_games
    meta = teams.rename(columns={"abbreviation": "home_team"})[["season", "home_team", "team_id", "league", "default_venue_id", "default_venue_name"]]
    parks = parks.merge(meta, on=["season", "home_team"], how="left", validate="one_to_one")
    if parks.league.isna().any():
        raise ValueError(f"Teams missing from teams.csv: {parks.loc[parks.league.isna(), 'home_team'].tolist()}")
    parks["venue_matches_teams_csv"] = parks.park_id.eq(parks.default_venue_id)
    columns = ["season", "home_team", "team_id", "league", "park_id", "default_venue_name", "venue_matches_teams_csv", "n_home_games", "n_relocated_games"]
    return parks[columns].sort_values(["season", "home_team"]).reset_index(drop=True)


def home_away_sums(pa: pd.DataFrame, parks: pd.DataFrame) -> pd.DataFrame:
    """Per team-season sums for PAs at its park (both teams batting) and in its road games."""
    park_of = parks.set_index(["season", "home_team"]).park_id
    rows = []
    for (season, team), park_id in park_of.items():
        in_game = pa.season.eq(season) & (pa.home_team.eq(team) | pa.away_team.eq(team))
        at_park = pa.season.eq(season) & pa.venue_id.eq(park_id)
        row = {"season": season, "home_team": team, "park_id": park_id}
        for side, mask in (("home", at_park), ("away", in_game & ~at_park)):
            values = pa.loc[mask, "value"]
            row |= {f"n_{side}_pa": len(values), f"{side}_sum": values.sum(), f"{side}_sq": values.pow(2).sum()}
        rows.append(row)
    return pd.DataFrame(rows)


def ratio_factors(sums: pd.DataFrame, parks: pd.DataFrame, min_pa: int) -> pd.DataFrame:
    """Home/away rate ratio with own-park correction, normalized to 1.0 within league-season."""
    frame = sums.merge(parks[["season", "home_team", "league"]], on=["season", "home_team"], validate="one_to_one")
    home_rate = frame.home_sum / frame.n_home_pa
    away_rate = frame.away_sum / frame.n_away_pa
    raw = home_rate / away_rate
    # Road games visit the other N-1 parks only; Baseball-Reference-style correction.
    n_parks = frame.groupby(["season", "league"]).home_team.transform("size")
    corrected = raw * n_parks / (n_parks - 1 + raw)
    enough = frame.n_home_pa.ge(min_pa) & frame.n_away_pa.ge(min_pa) & away_rate.gt(0) & home_rate.gt(0)
    frame["raw_factor"] = raw.where(enough)
    frame["factor"] = corrected.where(enough)
    weight = frame.n_home_pa.where(frame.factor.notna())
    league_mean = (frame.factor * weight).groupby([frame.season, frame.league]).transform("sum") / weight.groupby([frame.season, frame.league]).transform("sum")
    frame["factor"] = frame.factor / league_mean
    # Delta-method standard error of log(factor); treats PAs as independent, so slightly optimistic.
    home_var = frame.home_sq / frame.n_home_pa - home_rate**2
    away_var = frame.away_sq / frame.n_away_pa - away_rate**2
    frame["se_log"] = np.sqrt(home_var / (frame.n_home_pa * home_rate**2) + away_var / (frame.n_away_pa * away_rate**2)).where(enough)
    return frame


def pooled_sums(sums: pd.DataFrame, season: int, window: int = 2) -> pd.DataFrame:
    """Add earlier seasons' sums for teams whose park is unchanged; never uses later seasons."""
    current = sums[sums.season.eq(season)].set_index("home_team")
    earlier = sums[sums.season.between(season - window + 1, season - 1)]
    earlier = earlier[earlier.park_id.eq(earlier.home_team.map(current.park_id))]
    totals = current.drop(columns=["season", "park_id"]).add(earlier.groupby("home_team")[current.columns.drop(["season", "park_id"])].sum(), fill_value=0)
    totals["seasons_used"] = 1 + earlier.groupby("home_team").size().reindex(totals.index, fill_value=0)
    totals["season"] = season
    totals["park_id"] = current.park_id
    for column in ["n_home_pa", "n_away_pa"]:
        totals[column] = totals[column].astype("int64")
    return totals.reset_index()


def shrink(frame: pd.DataFrame) -> pd.Series:
    """Empirical-Bayes shrinkage of log factors toward 1.0, one between-park variance per season."""
    log_factor = np.log(frame.factor)
    observed = log_factor.notna()
    shrunk = pd.Series(np.nan, index=frame.index)
    for _, index in frame[observed].groupby("season").groups.items():
        values, se2 = log_factor[index], frame.se_log[index] ** 2
        true_var = max(0.0, values.var(ddof=1) - se2.mean()) if len(values) > 1 else 0.0
        shrunk[index] = np.exp(values * true_var / (true_var + se2))
    return shrunk


def player_adjusted(pa: pd.DataFrame, penalty: float = 200.0, iterations: int = 30) -> pd.DataFrame:
    """Venue factors from PA value = mean + batter-season + pitcher-season + venue (ridge backfitting).

    ``penalty`` is the number of league-average PAs added to each player's effect, so thin
    samples stay near average. Venue effects are unpenalized. Returns one row per venue,
    normalized so the PA-weighted mean across all venues in ``pa`` is 1.0.
    """
    keys = pd.DataFrame({
        "batter": pa.season.astype(str) + ":" + pa.batter.astype(str),
        "pitcher": pa.season.astype(str) + ":" + pa.pitcher.astype(str),
        "venue_id": pa.venue_id,
    })
    value = pa.value.to_numpy(float)
    mean = value.mean()
    fitted = {column: np.zeros(len(pa)) for column in keys}
    for _ in range(iterations):
        for column, lam in (("batter", penalty), ("pitcher", penalty), ("venue_id", 0.0)):
            residual = value - mean - sum(effect for other, effect in fitted.items() if other != column)
            grouped = pd.Series(residual).groupby(keys[column].to_numpy())
            effect = grouped.sum() / (grouped.size() + lam)
            fitted[column] = keys[column].map(effect).to_numpy(float)
    venues = pd.DataFrame({"venue_id": keys.venue_id, "effect": fitted["venue_id"]}).groupby("venue_id").agg(effect=("effect", "first"), n_venue_pa=("effect", "size"))
    venues["factor"] = (mean + venues.effect) / mean
    venues["factor"] /= np.average(venues.factor, weights=venues.n_venue_pa)
    return venues[["factor", "n_venue_pa"]].reset_index()


def prototype(pa: pd.DataFrame, teams: pd.DataFrame, stat: str = "woba", min_pa: int = 2000) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (contract output, method comparison, venue audit) for every season in ``pa``.

    Season Y uses only seasons Y-1 and Y, so each factor is available by January 1 of Y+1.
    """
    parks = home_parks(pa, teams)
    sums = home_away_sums(pa, parks)
    single = ratio_factors(sums, parks, min_pa)
    single["seasons_used"] = 1
    single["method"] = f"home_away_ratio_{stat}"
    comparisons, outputs = [single], []
    for season in sorted(parks.season.unique()):
        pooled = ratio_factors(pooled_sums(sums, season), parks, min_pa)
        pooled["factor"] = shrink(pooled)
        pooled["method"] = f"home_away_shrunk_{stat}"
        model = player_adjusted(pa[pa.season.between(season - 1, season)])
        model = parks[parks.season.eq(season)].merge(model, left_on="park_id", right_on="venue_id")
        model["factor"] = model.factor.where(model.n_venue_pa.ge(min_pa))
        model["seasons_used"] = pa.loc[pa.season.between(season - 1, season), "season"].nunique()
        model["method"] = f"player_adjusted_{stat}"
        comparisons += [pooled, model]
        outputs.append(pooled)
    columns = ["season", "home_team", "park_id", "method", "factor", "raw_factor", "se_log", "n_home_pa", "n_away_pa", "n_venue_pa", "seasons_used"]
    comparison = pd.concat(comparisons, ignore_index=True).reindex(columns=columns)
    output = pd.concat(outputs, ignore_index=True)
    output["reference_scale"] = REFERENCE_SCALE
    output["provisional"] = True
    output = output[OUTPUT_COLUMNS].sort_values(["season", "home_team"]).reset_index(drop=True)
    if output.duplicated(["season", "home_team"]).any():
        raise ValueError("Duplicate (season, home_team) key")
    return output, comparison.sort_values(["season", "method", "home_team"]).reset_index(drop=True), parks

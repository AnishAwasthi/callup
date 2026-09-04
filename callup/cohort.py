"""
Build the AAA -> MLB cohort.

The unit of analysis is a **player-season at Triple-A**, optionally paired with that
same player's major-league line the following season. Three groups come out of this,
and keeping them distinct is the whole point:

``labeled``
    Played enough at AAA in year Y *and* enough in MLB in year Y+1. These are the only
    rows a supervised model can train on.

``promoted_thin``
    Reached MLB but below the sample threshold. Promoted, but the outcome is too noisy
    to use as a label.

``never_promoted``
    Never reached MLB at all. **These rows have no outcome and never will.**

That last group is roughly three quarters of the pool, and it is the reason this project
needs a selection correction rather than a plain regression. A model fit only on
``labeled`` players is fit on a population that a front office already decided was good
enough to call up. Scoring it on everyone else assumes the call-up decision carried no
information, which is precisely backwards -- it carried a great deal.

Same structural problem as estimating the wage return to a degree using only people who
are employed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from callup.statsapi import StatsAPI, innings_to_float

# Playing-time floors. Loose thresholds buy sample size at the cost of noisier labels;
# the report script sweeps these rather than hard-coding one answer.
THRESHOLDS = {
    "hitting": {"strict": (200, 100), "moderate": (150, 75), "loose": (100, 50)},
    "pitching": {"strict": (50, 30), "moderate": (40, 20), "loose": (30, 15)},
}

PLAYING_TIME_FIELD = {"hitting": "pa", "pitching": "ip"}


@dataclass
class PlayerSeason:
    player_id: int
    name: str
    season: int
    group: str
    aaa_playing_time: float
    mlb_playing_time: float = 0.0
    reached_mlb: bool = False
    aaa_stats: dict = field(default_factory=dict)
    mlb_stats: dict = field(default_factory=dict)

    @property
    def outcome_year(self) -> int:
        return self.season + 1


@dataclass
class Cohort:
    group: str
    labeled: list[PlayerSeason]
    promoted_thin: list[PlayerSeason]
    never_promoted: list[PlayerSeason]

    @property
    def pool_size(self) -> int:
        return len(self.labeled) + len(self.promoted_thin) + len(self.never_promoted)

    @property
    def promotion_rate(self) -> float:
        """Share of the pool that reached MLB at all, thin samples included."""
        if not self.pool_size:
            return 0.0
        return (len(self.labeled) + len(self.promoted_thin)) / self.pool_size

    @property
    def label_rate(self) -> float:
        """Share of the pool that is actually usable for supervised training."""
        return len(self.labeled) / self.pool_size if self.pool_size else 0.0

    @property
    def censoring_rate(self) -> float:
        """Share with no usable outcome. This is the size of the selection problem."""
        return 1.0 - self.label_rate


def _playing_time(stat: dict, group: str) -> float:
    if group == "pitching":
        return innings_to_float(stat.get("inningsPitched"))
    return float(stat.get("plateAppearances") or 0)


def _index_by_player(splits: list[dict], group: str) -> dict[int, dict]:
    """
    Collapse a season's splits to one row per player.

    A player traded mid-season appears once per organization, so the same player id can
    show up several times. Summing playing time and keeping the largest split's rate
    stats is a deliberate simplification: it is right for "did they play enough" and
    approximate for the rate stats themselves.
    """
    indexed: dict[int, dict] = {}
    for split in splits:
        player = split.get("player") or {}
        stat = split.get("stat") or {}
        player_id = player.get("id")
        if player_id is None:
            continue

        playing_time = _playing_time(stat, group)
        existing = indexed.get(player_id)
        if existing is None:
            indexed[player_id] = {
                "name": player.get("fullName") or str(player_id),
                "playing_time": playing_time,
                "stat": stat,
            }
        else:
            existing["playing_time"] += playing_time
            if playing_time > _playing_time(existing["stat"], group):
                existing["stat"] = stat
    return indexed


def build_cohort(
    api: StatsAPI,
    seasons: list[int],
    group: str,
    threshold: str = "moderate",
) -> Cohort:
    """Pair AAA player-seasons in ``seasons`` with the following MLB season."""
    aaa_min, mlb_min = THRESHOLDS[group][threshold]

    labeled: list[PlayerSeason] = []
    promoted_thin: list[PlayerSeason] = []
    never_promoted: list[PlayerSeason] = []

    for season in seasons:
        aaa = _index_by_player(api.season_stats(season, "AAA", group), group)
        mlb = _index_by_player(api.season_stats(season + 1, "MLB", group), group)

        for player_id, aaa_row in aaa.items():
            if aaa_row["playing_time"] < aaa_min:
                continue

            mlb_row = mlb.get(player_id)
            mlb_playing_time = mlb_row["playing_time"] if mlb_row else 0.0
            record = PlayerSeason(
                player_id=player_id,
                name=aaa_row["name"],
                season=season,
                group=group,
                aaa_playing_time=aaa_row["playing_time"],
                mlb_playing_time=mlb_playing_time,
                reached_mlb=mlb_row is not None,
                aaa_stats=aaa_row["stat"],
                mlb_stats=mlb_row["stat"] if mlb_row else {},
            )

            if mlb_playing_time >= mlb_min:
                labeled.append(record)
            elif mlb_row is not None:
                promoted_thin.append(record)
            else:
                never_promoted.append(record)

    return Cohort(group, labeled, promoted_thin, never_promoted)

"""
Thin, cached client for the public MLB Stats API.

Two properties matter more than features here:

* **Cached on disk.** Cohort construction reruns constantly during analysis. Without a
  cache every rerun re-hits the API, which is slow and rude. With one, the second run is
  instant and works offline.
* **Polite.** A small delay between live calls, a real User-Agent, and bounded retries.
  This is a free public API run by someone else.

Level codes are MLB's own ``sportId`` values, not names we invented:
1 = MLB, 11 = Triple-A, 12 = Double-A, 13 = High-A, 14 = Single-A.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "callup-research/0.1 (+https://github.com/AnishAwasthi/callup)"

SPORT_IDS = {"MLB": 1, "AAA": 11, "AA": 12, "A+": 13, "A": 14}
LEVEL_BY_SPORT_ID = {v: k for k, v in SPORT_IDS.items()}

PAGE_SIZE = 1000
REQUEST_DELAY_S = 0.35
MAX_RETRIES = 4

DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "data" / "cache"


class StatsAPI:
    def __init__(self, cache_dir: Path | None = None, delay_s: float = REQUEST_DELAY_S):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_s = delay_s
        self.live_calls = 0
        self.cache_hits = 0

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    def get(self, path: str, **params) -> dict:
        """GET a Stats API path, memoized on disk by full URL."""
        url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
        cached = self._cache_path(url)
        if cached.exists():
            self.cache_hits += 1
            return json.loads(cached.read_text())

        payload = self._fetch(url)
        cached.write_text(json.dumps(payload))
        return payload

    def _fetch(self, url: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=90) as response:
                    payload = json.load(response)
                self.live_calls += 1
                time.sleep(self.delay_s)
                return payload
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(2**attempt)  # exponential backoff
        raise RuntimeError(f"Stats API failed after {MAX_RETRIES} attempts: {url}") from last_error

    def season_stats(self, season: int, level: str, group: str) -> list[dict]:
        """
        Every player's season line at one level, following pagination to the end.

        ``group`` is "hitting" or "pitching". ``playerPool=ALL`` matters: the default
        pool silently drops players who fell below a qualification threshold, which is
        exactly the population this project needs to see.
        """
        sport_id = SPORT_IDS[level]
        splits: list[dict] = []
        offset = 0
        while True:
            payload = self.get(
                "stats",
                stats="season",
                group=group,
                season=season,
                sportId=sport_id,
                limit=PAGE_SIZE,
                offset=offset,
                playerPool="ALL",
            )
            stats_blocks = payload.get("stats") or [{}]
            page = stats_blocks[0].get("splits", [])
            if not page:
                break
            splits.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return splits

    def teams(self, season: int, level: str) -> list[dict]:
        return self.get("teams", sportId=SPORT_IDS[level], season=season).get("teams", [])

    def team_level_map(self, season: int) -> dict[str, str]:
        """
        Map every team abbreviation to its level.

        Needed because the Baseball Savant minors CSV export carries ``home_team`` and
        ``away_team`` but **no level column** -- the feed mixes Triple-A and the Florida
        State League together, so team abbreviation is the only way to tell them apart.
        """
        mapping: dict[str, str] = {}
        for level in ("MLB", "AAA", "AA", "A+", "A"):
            for team in self.teams(season, level):
                for key in (team.get("abbreviation"), team.get("teamCode"), team.get("fileCode")):
                    if key:
                        mapping[str(key).upper()] = level
        return mapping


def innings_to_float(value) -> float:
    """
    Convert the Stats API innings-pitched string to a real number.

    Baseball writes thirds of an inning as a decimal that is not a decimal: "150.1"
    means 150 and 1/3, "150.2" means 150 and 2/3. Reading it as a float silently
    understates every pitcher's workload.
    """
    if value is None:
        return 0.0
    whole, _, fraction = str(value).partition(".")
    try:
        base = float(whole)
    except ValueError:
        return 0.0
    return base + {"": 0.0, "0": 0.0, "1": 1 / 3, "2": 2 / 3}.get(fraction, 0.0)

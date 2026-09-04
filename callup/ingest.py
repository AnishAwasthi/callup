"""
Pitch-level ingestion from Baseball Savant.

Three properties this layer must have, each earned the hard way:

**Cap-aware.** Savant's CSV export truncates at exactly 25,000 rows and returns HTTP 200
with no error, warning, or marker. A seven-day major-league query comes back with
precisely 25,000 rows and looks complete. Any ingester that does not check for this
silently loses data, and the loss is invisible downstream. We fetch one game-date at a
time (observed peak is ~4,300 rows) and raise if a response ever reaches the cap.

**Resumable.** A full three-season, two-level pull is several hundred requests over
multiple hours. It will be interrupted. Each game-date lands in its own file, so an
interrupted run resumes exactly where it stopped and a completed date is never
re-fetched.

**Raw-archiving.** The compressed CSV is stored exactly as served. Re-parsing, schema
changes, and bug fixes then never require re-downloading — which matters both for
iteration speed and for not hammering a free public service.

One more wrinkle: the minors export carries no level column and mixes Triple-A with the
Florida State League. Level is joined on afterwards from the Stats API team map, so
``level`` here refers to what we *requested*, and rows must still be filtered by team.
"""

from __future__ import annotations

import gzip
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from callup.statsapi import SPORT_IDS, USER_AGENT, StatsAPI

MLB_CSV = "https://baseballsavant.mlb.com/statcast_search/csv"
MINORS_CSV = "https://baseballsavant.mlb.com/statcast-search-minors/csv"

# Savant's hard export limit. Reaching it exactly means the response was truncated.
ROW_CAP = 25_000

# Savant is a free public service; a full ingest is hundreds of requests.
REQUEST_DELAY_S = 2.0
MAX_RETRIES = 4

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


class TruncatedResponse(RuntimeError):
    """A query hit the row cap, so its results are incomplete."""


def count_data_rows(payload: bytes) -> int:
    """
    Count CSV data rows (excluding the header) the same way for fresh and cached reads.

    Savant does not terminate its final line with a newline, so counting ``b"\n"``
    undercounts by one. That matters here beyond tidiness: this count guards the 25,000
    row cap, and an undercount means a response truncated at exactly the cap reads as
    24,999 and passes the check.
    """
    if not payload:
        return 0
    newlines = payload.count(b"\n")
    if not payload.endswith(b"\n"):
        newlines += 1
    return max(newlines - 1, 0)


@dataclass
class DayResult:
    level: str
    game_date: str
    rows: int
    path: Path
    from_cache: bool


def _csv_url(level: str, game_date: str) -> str:
    """Build the export URL for one level on one date."""
    params = {
        "all": "true",
        "hfGT": "R|",  # regular season only
        "game_date_gt": game_date,
        "game_date_lt": game_date,
        "player_type": "pitcher",
        "type": "details",
    }
    if level == "MLB":
        return MLB_CSV + "?" + urllib.parse.urlencode(params)

    # The minors endpoint ignores hfLevel and needs minors=true; without it the endpoint
    # quietly serves major-league rows instead, which is worse than an error.
    params["minors"] = "true"
    params["hfSea"] = f"{game_date[:4]}|"
    return MINORS_CSV + "?" + urllib.parse.urlencode(params)


def _fetch_bytes(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Savant request failed after {MAX_RETRIES} attempts: {url}") from last_error


def game_dates(api: StatsAPI, season: int, level: str) -> list[str]:
    """
    Dates with regular-season games at this level.

    Pulled from the schedule rather than iterating the calendar, so the ingester does not
    spend hundreds of requests discovering that Mondays in April were off-days.
    """
    payload = api.get(
        "schedule",
        sportId=SPORT_IDS[level],
        startDate=f"{season}-03-01",
        endDate=f"{season}-11-15",
        gameType="R",
    )
    return sorted(
        day["date"]
        for day in payload.get("dates", [])
        if day.get("totalGames", 0) > 0 and day.get("date")
    )


def fetch_day(level: str, game_date: str, raw_dir: Path, force: bool = False) -> DayResult:
    """Fetch and archive one level-date. Returns immediately if already stored."""
    out_dir = Path(raw_dir) / level
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{game_date}.csv.gz"

    if path.exists() and not force:
        with gzip.open(path, "rb") as handle:
            rows = count_data_rows(handle.read())
        return DayResult(level, game_date, rows, path, from_cache=True)

    body = _fetch_bytes(_csv_url(level, game_date))
    rows = count_data_rows(body)

    if rows >= ROW_CAP:
        raise TruncatedResponse(
            f"{level} {game_date} returned {rows} rows, at or above the {ROW_CAP} cap. "
            "The response is truncated and the date must be split further."
        )

    # Write to a temp file then rename, so an interrupted run never leaves a partial
    # archive that a later run would mistake for a completed fetch.
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wb") as handle:
        handle.write(body)
    tmp.replace(path)

    time.sleep(REQUEST_DELAY_S)
    return DayResult(level, game_date, rows, path, from_cache=False)


def ingest_season(
    api: StatsAPI,
    season: int,
    level: str,
    raw_dir: Path = DEFAULT_RAW_DIR,
    limit: int | None = None,
    progress=print,
) -> list[DayResult]:
    """Archive every game-date for one season at one level. Safe to re-run."""
    dates = game_dates(api, season, level)
    if limit:
        dates = dates[:limit]

    results: list[DayResult] = []
    fetched = 0
    for index, game_date in enumerate(dates, start=1):
        result = fetch_day(level, game_date, raw_dir)
        results.append(result)
        if not result.from_cache:
            fetched += 1
        if progress and (index % 10 == 0 or index == len(dates)):
            total = sum(r.rows for r in results)
            progress(
                f"  {level} {season}: {index}/{len(dates)} dates "
                f"({fetched} fetched, {index - fetched} cached) — {total:,} rows"
            )

    _write_manifest(raw_dir, level, season, results)
    return results


def _write_manifest(raw_dir: Path, level: str, season: int, results: list[DayResult]) -> None:
    manifest = Path(raw_dir) / level / f"_manifest_{season}.json"
    manifest.write_text(
        json.dumps(
            {
                "level": level,
                "season": season,
                "dates": len(results),
                "rows": sum(r.rows for r in results),
                "written_at": date.today().isoformat(),
            },
            indent=2,
        )
    )


def load_day(path: Path) -> pd.DataFrame:
    """Parse one archived day into a DataFrame."""
    with gzip.open(path, "rb") as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)


def load_days(paths, team_levels: dict[str, str] | None = None) -> pd.DataFrame:
    """
    Parse and concatenate archived days, tagging each row's true level.

    ``team_levels`` maps team abbreviation to level. It is required for minor-league
    files because the export mixes Triple-A and Florida State League rows with nothing
    to distinguish them but the team code.
    """
    frames = []
    for path in paths:
        frame = load_day(Path(path))
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    if team_levels is not None:
        combined["level"] = combined["home_team"].astype(str).str.upper().map(team_levels)
    return combined

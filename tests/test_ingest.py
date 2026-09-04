"""Ingestion tests. No network: fetching is monkeypatched."""

import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup import ingest  # noqa: E402
from callup.ingest import ROW_CAP, TruncatedResponse, count_data_rows, fetch_day  # noqa: E402


def csv_bytes(n_rows: int, trailing_newline: bool = False) -> bytes:
    body = "header_a,header_b\n" + "".join(f"{i},x\n" for i in range(n_rows))
    if not trailing_newline and body.endswith("\n"):
        body = body[:-1]
    return body.encode()


# --- row counting ----------------------------------------------------------------

def test_row_count_ignores_missing_trailing_newline():
    """
    Savant omits the final newline. Counting b"\\n" alone undercounts by one, and that
    count is what guards the truncation check.
    """
    assert count_data_rows(csv_bytes(3, trailing_newline=False)) == 3
    assert count_data_rows(csv_bytes(3, trailing_newline=True)) == 3


@pytest.mark.parametrize("payload,expected", [(b"", 0), (b"header", 0), (b"header\n", 0)])
def test_row_count_edge_cases(payload, expected):
    assert count_data_rows(payload) == expected


def test_row_count_matches_across_fresh_and_cached_paths(tmp_path, monkeypatch):
    """The two code paths must never disagree, or idempotency is a lie."""
    payload = csv_bytes(500)
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: payload)
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    fresh = fetch_day("MLB", "2024-06-14", tmp_path)
    cached = fetch_day("MLB", "2024-06-14", tmp_path)

    assert fresh.from_cache is False
    assert cached.from_cache is True
    assert fresh.rows == cached.rows == 500


# --- truncation guard ------------------------------------------------------------

def test_response_at_the_cap_raises(tmp_path, monkeypatch):
    """
    Savant returns HTTP 200 with exactly 25,000 rows when it truncates. Silently
    accepting that loses data invisibly, so it must be an error.
    """
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: csv_bytes(ROW_CAP))
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    with pytest.raises(TruncatedResponse, match="truncated"):
        fetch_day("MLB", "2024-06-14", tmp_path)


def test_truncated_response_is_not_archived(tmp_path, monkeypatch):
    """A truncated payload must not land on disk, or a rerun would trust it."""
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: csv_bytes(ROW_CAP))
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    with pytest.raises(TruncatedResponse):
        fetch_day("MLB", "2024-06-14", tmp_path)

    assert not (tmp_path / "MLB" / "2024-06-14.csv.gz").exists()
    assert not list((tmp_path / "MLB").glob("*.tmp"))


def test_response_just_below_the_cap_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: csv_bytes(ROW_CAP - 1))
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)
    assert fetch_day("MLB", "2024-06-14", tmp_path).rows == ROW_CAP - 1


# --- idempotency and resumability ------------------------------------------------

def test_cached_day_is_never_refetched(tmp_path, monkeypatch):
    calls = []

    def counting_fetch(url):
        calls.append(url)
        return csv_bytes(10)

    monkeypatch.setattr(ingest, "_fetch_bytes", counting_fetch)
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    fetch_day("MLB", "2024-06-14", tmp_path)
    fetch_day("MLB", "2024-06-14", tmp_path)
    fetch_day("MLB", "2024-06-14", tmp_path)

    assert len(calls) == 1, "a cached date was re-fetched"


def test_force_bypasses_the_cache(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: (calls.append(url), csv_bytes(10))[1])
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    fetch_day("MLB", "2024-06-14", tmp_path)
    fetch_day("MLB", "2024-06-14", tmp_path, force=True)
    assert len(calls) == 2


def test_archive_round_trips_the_exact_bytes(tmp_path, monkeypatch):
    payload = csv_bytes(25)
    monkeypatch.setattr(ingest, "_fetch_bytes", lambda url: payload)
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)

    result = fetch_day("AAA", "2024-06-28", tmp_path)
    assert gzip.open(result.path, "rb").read() == payload


# --- URL construction ------------------------------------------------------------

def test_minors_url_sets_the_flag_that_actually_works():
    """
    hfLevel is ignored by the minors endpoint; without minors=true it quietly serves
    major-league rows, which is worse than failing.
    """
    url = ingest._csv_url("AAA", "2024-06-28")
    assert "statcast-search-minors" in url
    assert "minors=true" in url
    assert "hfSea=2024" in url


def test_mlb_url_uses_the_major_league_endpoint():
    url = ingest._csv_url("MLB", "2024-06-14")
    assert "statcast_search/csv" in url
    assert "minors=true" not in url


def test_urls_are_pinned_to_a_single_date():
    url = ingest._csv_url("MLB", "2024-06-14")
    assert "game_date_gt=2024-06-14" in url
    assert "game_date_lt=2024-06-14" in url

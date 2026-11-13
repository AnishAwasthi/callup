"""Full-cohort diagnostics; references and internal event counts stay separate."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal

import pandas as pd

COUNT_FIELDS = {
    "ab": "AB", "pa": "PA", "single": "1B", "double": "2B", "triple": "3B",
    "home_run": "HR", "bb": "BB", "ibb": "IBB", "hbp": "HBP", "sf": "SF", "sh": "SH",
}
SCOPE = "MLB regular season; all teams; observed wOBA"


def leaderboard_url(year):
    return ("https://www.fangraphs.com/leaders/major-league?pos=all&stats=bat&lg=all"
            f"&qual=0&type=8&season={year}&season1={year}&ind=0&pageitems=2000&pagenum=1")


def parse_leaderboard(html, year):
    """Read original numeric tokens; reject incomplete or differently scoped captures."""
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("Missing embedded leaderboard data")
    document = json.loads(match[1], parse_float=Decimal)
    queries = document["props"]["pageProps"]["dehydratedState"]["queries"]
    matches = [q for q in queries if q["queryKey"][0] == "leaders/major-league/data"]
    if len(matches) != 1:
        raise ValueError("Ambiguous leaderboard query")
    query = matches[0]
    params = query["queryKey"][1]
    expected = {"season": year, "season1": year, "stats": "bat", "qual": "0",
                "team": 0, "ind": 0, "month": 0, "postseason": "", "level": "mlb"}
    if any(params.get(k) != v for k, v in expected.items()):
        raise ValueError("Unexpected leaderboard scope")
    result = query["state"]["data"]
    if len(result["data"]) != result["totalCount"]:
        raise ValueError("Incomplete leaderboard capture")
    if any(row["Season"] != year for row in result["data"]):
        raise ValueError("Wrong source season")
    return result["data"], {"query": params, "total_count": result["totalCount"],
                             "data_updated_at_ms": query["state"]["dataUpdatedAt"]}


def match_record(player_id, year, source_rows):
    """Join source-supplied MLBAM ID and year; never join names or sum team rows."""
    candidates = [r for r in source_rows if r.get("xMLBAMID") == player_id and r["Season"] == year]
    if not candidates:
        return "unmatched", None
    if len(candidates) != 1:
        return "ambiguous", None
    row = candidates[0]
    if not isinstance(row.get("playerid"), int) or row["playerid"] <= 0:
        return "ambiguous", None
    return "matched", row


def reference_record(prepared, source, retrieved_at, source_sha256):
    """Curate only cohort facts from an independently published source payload."""
    if datetime.fromisoformat(retrieved_at).utcoffset() is None:
        raise ValueError("Timezone required")
    counts = {}
    for key, source_key in COUNT_FIELDS.items():
        value = source[source_key]
        if not isinstance(value, int) or value < 0:
            raise ValueError("Missing or invalid independent count")
        counts[key] = value
    token = str(source["wOBA"])
    if not math.isfinite(float(token)) or not 0 <= float(token) <= 3:
        raise ValueError("Invalid published wOBA")
    return {
        "player_id": int(prepared.player_id), "season": int(prepared.season),
        "outcome_year": int(prepared.outcome_year), "name": prepared["name"],
        "source_name": source["PlayerName"], "source": "FanGraphs",
        "source_player_id": source["playerid"], "source_mlbam_id": source["xMLBAMID"],
        "source_team": source["TeamName"], "source_team_id": source["teamid"],
        "url": leaderboard_url(int(prepared.outcome_year)),
        "player_url": f'https://www.fangraphs.com/players/sa/{source["playerid"]}/stats/batting',
        "scope": SCOPE, "identity_verified": True,
        "identity_method": "Exact source-supplied xMLBAMID and Season; unique all-team row; source playerid retained",
        "retrieved_at": retrieved_at, "source_sha256": source_sha256,
        "retrieval_method": "curl HTTPS public page; embedded dehydrated leaderboard JSON; origin revision time unknown",
        "woba": token, "precision": max(0, -Decimal(token).as_tuple().exponent),
        "display_precision": 3, "counts": counts,
    }


def validate_references(document, cohort):
    """Fail closed on duplicate keys, conflicting ID mappings, or wrong provenance."""
    references = document["references"]
    keys = [(r["player_id"], r["season"]) for r in references]
    eligible = set(zip(cohort.player_id, cohort.season, strict=True))
    if len(keys) != len(set(keys)) or set(keys) - eligible:
        raise ValueError("Duplicate or out-of-cohort reference")
    mapping = {}
    reverse = {}
    for r in references:
        if (r["source"] != "FanGraphs" or r["scope"] != SCOPE
                or r["source_mlbam_id"] != r["player_id"] or not r["identity_verified"]
                or r["outcome_year"] != r["season"] + 1
                or r["url"] != leaderboard_url(r["outcome_year"])
                or datetime.fromisoformat(r["retrieved_at"]).utcoffset() is None
                or not re.fullmatch('[0-9a-f]{64}', r["source_sha256"])):
            raise ValueError("Invalid independent provenance")
        pid, fg = r["player_id"], r["source_player_id"]
        if mapping.get(pid, fg) != fg or reverse.get(fg, pid) != pid:
            raise ValueError("Conflicting player identifier mapping")
        mapping[pid], reverse[fg] = fg, pid
        if set(r["counts"]) != set(COUNT_FIELDS):
            raise ValueError("Incomplete independent counts")
        if any(not isinstance(v, int) or v < 0 for v in r["counts"].values()):
            raise ValueError("Invalid independent counts")
        if not math.isfinite(float(r["woba"])):
            raise ValueError("Invalid published wOBA")
    return {key: r for key, r in zip(keys, references, strict=True)}


def reconcile(prepared, reconstruction, reference):
    """Validate original reconstruction; report count and precision discrepancies."""
    r = reconstruction
    for key, field in [("served_n", "mlb_woba_numerator"), ("served_d", "mlb_woba_denom"),
                       ("terminal_rows", "mlb_observed_pa"), ("prepared_reconstruction", "mlb_woba")]:
        if not math.isclose(r[key], prepared[field], abs_tol=1e-9, rel_tol=0):
            raise ValueError("Archive does not reproduce frozen outcome")
    row = {k: prepared[k] for k in ["player_id", "name", "season", "outcome_year", "split", "mlb_pa", "mlb_woba"]}
    row.update(r)
    row.update(original_provisional_woba=float(prepared.mlb_woba),
               reconstructed_standard_woba=r["standard_diagnostic"],
               internal_pa_gap=r["archive_pa"] - int(prepared.mlb_pa),
               original_minus_standard=float(prepared.mlb_woba) - r["standard_diagnostic"],
               reference_woba=None, original_minus_published=None, standard_minus_published=None,
               component_mismatches=None, reconciliation_status="not_independently_verified")
    if reference is None:
        return row
    mismatches = {k: r["archive_pa" if k == "pa" else k] - v
                  for k, v in reference["counts"].items()
                  if r["archive_pa" if k == "pa" else k] != v}
    value = float(reference["woba"])
    residual = r["standard_diagnostic"] - value
    # Displayed coefficient rounding is a compatibility bound, not proof of cause.
    tolerance = .5 * 10 ** -reference["precision"]
    status = ("within_published_precision" if abs(residual) <= tolerance else
              "compatible_with_coefficient_precision" if abs(residual) <= tolerance + r["coefficient_rounding_bound"]
              else "unresolved_woba_residual")
    if mismatches:
        status = "unresolved_component_difference"
    if reference["counts"]["pa"] != prepared.mlb_pa:
        status = "unresolved_official_pa_difference"
    row.update(reference_woba=value, reference_woba_token=reference["woba"],
               reference_player_id=reference["source_player_id"], reference_name=reference["source_name"],
               reference_team=reference["source_team"], reference_url=reference["url"],
               reference_retrieved_at=reference["retrieved_at"], reference_precision=reference["precision"],
               reference_sha256=reference["source_sha256"],
               original_minus_published=float(prepared.mlb_woba) - value,
               standard_minus_published=residual, component_mismatches=json.dumps(mismatches, sort_keys=True),
               reconciliation_status=status,
               **{f"reference_{k}": v for k, v in reference["counts"].items()})
    return row


def difference_summary(values):
    values = pd.Series(values, dtype=float).dropna()
    if values.empty:
        return {"n": 0}
    return {"n": len(values), "mean_signed": float(values.mean()),
            "mean_absolute": float(values.abs().mean()), "median_signed": float(values.median()),
            "median_absolute": float(values.abs().median()), "min_signed": float(values.min()),
            "max_signed": float(values.max()), "max_absolute": float(values.abs().max()),
            "n_positive": int(values.gt(0).sum()), "n_negative": int(values.lt(0).sum())}


def summarize(rows):
    return {"n": len(rows), "unique_players": rows.player_id.nunique(),
            "matching": {status: int(rows.match_status.eq(status).sum()) for status in
                         ["matched", "ambiguous", "unmatched", "not_yet_verified"]},
            "reconciliation": dict(Counter(rows.reconciliation_status)),
            "differences": {c: difference_summary(rows[c]) for c in [
                "original_minus_standard", "original_minus_published", "standard_minus_published"]},
            "internal_pa_gap_rows": int(rows.internal_pa_gap.ne(0).sum()),
            "missing_required_denominators": int(rows.missing_required_denominators.sum()),
            "missing_out_denominators": int(rows.missing_out_denominators.sum()),
            "truncated_pa": int(rows.truncated_pa.sum())}

"""Compare frozen outcomes to manually verified independent season references."""
from __future__ import annotations

import json
import math
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse

# Fixed pilot; includes train, test, excluded-overlap, and PA-gap cases.
PILOT = {(664770, 2023): "Nathan Lukes", (687401, 2023): "Joey Ortiz",
         (676632, 2023): "Bligh Madris", (691406, 2024): "Junior Caminero",
         (695578, 2024): "James Wood"}


def load_references(path):
    """Load the fixed pilot and require its recorded provenance, without fetching."""
    document = json.loads(path.read_text())
    references = document.get("references")
    required = {"player_id", "name", "season", "outcome_year", "source",
                "source_player_id", "url", "retrieved_at", "retrieval_date_local",
                "retrieval_method", "precision", "woba", "pa", "team", "scope",
                "identity_verified", "identity_url", "identity_method", "evidence", "notes"}
    if not document.get("capture_note") or not isinstance(references, list):
        raise ValueError("Reference document requires capture_note and references")
    for reference in references:
        if not isinstance(reference, dict) or required - reference.keys():
            raise ValueError("Reference record is missing required provenance fields")
        for field in required - {"woba", "pa", "identity_verified", "precision"}:
            if reference[field] is None or reference[field] == "":
                raise ValueError(f"Missing reference provenance: {field}")
        timestamp = datetime.fromisoformat(reference["retrieved_at"])
        if timestamp.utcoffset() is None:
            raise ValueError("Reference retrieval timestamp must include timezone")
        datetime.strptime(reference["retrieval_date_local"], "%Y-%m-%d")
    keys = [(r["player_id"], r["season"]) for r in references]
    if len(keys) != 5 or set(keys) != set(PILOT):
        raise ValueError("References must contain exactly the five unique pilot player-seasons")
    return references


def compare_reference(row, reference):
    """Keep unmatched/unavailable references unresolved, without invented values."""
    fields = ["player_id", "name", "season", "outcome_year", "split", "mlb_woba",
              "mlb_woba_numerator", "mlb_woba_denom", "mlb_pa", "mlb_observed_pa",
              "mlb_first_date", "mlb_last_date"]
    result = {field: row[field] for field in fields}
    result.update(reference_source=reference.get("source"), reference_url=reference.get("url"),
                  retrieved_at=reference.get("retrieved_at"), reference_player_id=reference.get("source_player_id"),
                  reference_season=reference.get("outcome_year"), reported_precision=reference.get("precision"),
                  identity_url=reference.get("identity_url"), identity_method=reference.get("identity_method"),
                  reference_scope=reference.get("scope"), reference_woba=None, reference_pa=None,
                  difference=None, absolute_difference=None, reference_pa_difference=None,
                  rounding_tolerance=None, status="unresolved_reference", explanation=reference.get("notes", ""))
    matched = (reference.get("identity_verified") is True
               and reference.get("player_id") == row.player_id
               and reference.get("name") == row["name"]
               and reference.get("season") == row.season
               and reference.get("outcome_year") == row.outcome_year)
    if not matched or reference.get("woba") is None:
        return result
    required = ["source_player_id", "identity_url", "identity_method", "retrieved_at"]
    if (reference.get("source") not in {"FanGraphs", "Baseball Savant"}
            or reference.get("scope") != "MLB regular season; all teams; observed wOBA"
            or any(not reference.get(field) for field in required)):
        return result
    host = urlparse(reference.get("url", "")).hostname
    allowed_host = "www.fangraphs.com" if reference["source"] == "FanGraphs" else "baseballsavant.mlb.com"
    if host != allowed_host:
        return result
    datetime.fromisoformat(reference["retrieved_at"])  # Reject malformed provenance.
    value = float(reference["woba"])
    precision = reference["precision"]
    if not math.isfinite(value) or not isinstance(precision, int) or precision < 0:
        raise ValueError("Reference wOBA must be finite with nonnegative decimal precision")
    pa = reference["pa"]
    if not isinstance(pa, int) or pa < 0:
        raise ValueError("Reference PA must be a nonnegative integer")
    delta = Decimal(str(row.mlb_woba)) - Decimal(str(reference["woba"]))
    tolerance = Decimal("0.5") * Decimal(10) ** -precision
    status = "consistent_with_rounding" if abs(delta) <= tolerance else "unresolved_definition_difference"
    if pa != row.mlb_pa:
        status = "unresolved_coverage_difference"
    result.update(reference_woba=value, reference_pa=pa, difference=float(delta),
                  absolute_difference=float(abs(delta)), rounding_tolerance=float(tolerance),
                  reference_pa_difference=pa - int(row.mlb_pa), status=status)
    return result

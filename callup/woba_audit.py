"""Diagnostic reconstructions only; never replace frozen outcome labels."""
from __future__ import annotations

import math
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

HITS = {"single", "double", "triple", "home_run"}
AB_EVENTS = HITS | {"strikeout", "strikeout_double_play", "field_out", "force_out",
                    "grounded_into_double_play", "double_play", "triple_play",
                    "field_error", "fielders_choice", "fielders_choice_out"}
SF_EVENTS = {"sac_fly", "sac_fly_double_play"}
SH_EVENTS = {"sac_bunt", "sac_bunt_double_play"}
KNOWN_EVENTS = AB_EVENTS | SF_EVENTS | SH_EVENTS | {"walk", "intent_walk", "hit_by_pitch",
                                                    "catcher_interf", "truncated_pa"}


def reconstruct(pitches, seasonal_weights, basic_weights):
    """Sum served fields, then apply explicit standard and literal Basic conventions."""
    terminal = pitches.loc[pitches.events.notna()].copy()
    unknown = set(terminal.events) - KNOWN_EVENTS
    if unknown:
        raise ValueError(f"Unmapped events require investigation: {sorted(unknown)}")
    for column in ("woba_value", "woba_denom"):
        terminal[column] = pd.to_numeric(terminal[column], errors="raise")
        if not terminal[column].dropna().map(math.isfinite).all():
            raise ValueError("Nonfinite served values")
    counts = terminal.events.value_counts()
    def count(event):
        return int(counts.get(event, 0))
    ab = sum(count(event) for event in AB_EVENTS)
    sf = sum(count(event) for event in SF_EVENTS)
    sh = sum(count(event) for event in SH_EVENTS)
    pa = len(terminal) - count("truncated_pa")
    standard_d = ab + count("walk") + count("hit_by_pitch") + sf
    served_n = float(terminal.woba_value.sum())
    served_d = float(terminal.woba_denom.fillna(0).sum())
    if min(pa, standard_d, served_d) <= 0:
        raise ValueError("Positive PA and denominators required for reconstruction")
    canonical_n = math.fsum(count(event) * weight for event, weight in basic_weights.items())
    standard_n = math.fsum(count(event) * weight for event, weight in seasonal_weights.items())
    # The 2015 Basic formula explicitly uses BB and PA, including IBB in each.
    basic_n = canonical_n + basic_weights["walk"] * count("intent_walk")
    missing_positive = (terminal.woba_denom.fillna(0).gt(0) & terminal.woba_value.isna())
    missing_out = terminal.events.isin(AB_EVENTS - HITS) & terminal.woba_denom.isna()
    expected_d = terminal.events.isin(AB_EVENTS | SF_EVENTS | {"walk", "hit_by_pitch"}).astype(int)
    expected_fixed_n = terminal.events.map(basic_weights).fillna(0)
    unexpected_value = terminal.woba_value.fillna(0).sub(expected_fixed_n).abs().gt(1e-9)
    unexpected_d = terminal.woba_denom.fillna(0).ne(expected_d)
    output = {
        "served_n": served_n, "served_d": served_d, "prepared_reconstruction": served_n / served_d,
        "terminal_rows": len(terminal), "archive_pa": pa, "ab": ab,
        "bb": count("walk") + count("intent_walk"), "ibb": count("intent_walk"),
        "hbp": count("hit_by_pitch"), "sf": sf, "sh": sh,
        **{event: count(event) for event in sorted(HITS)},
        "standard_n": standard_n, "standard_d": standard_d, "standard_diagnostic": standard_n / standard_d,
        "basic_n": basic_n, "basic_d": pa, "basic_diagnostic": basic_n / pa,
        "canonical_n_fixed_weights": canonical_n,
        "nonstandard_numerator_effect": (served_n - canonical_n) / served_d,
        "denominator_effect": canonical_n / served_d - canonical_n / standard_d,
        "coefficient_effect": (canonical_n - standard_n) / standard_d,
        "missing_out_denominators": int(missing_out.sum()),
        "missing_required_denominators": int((terminal.woba_denom.isna() & expected_d.eq(1)).sum()),
        "missing_positive_denominator_values": int(missing_positive.sum()),
        "truncated_pa": count("truncated_pa"),
        "coefficient_rounding_bound": .0005 * sum(count(event) for event in seasonal_weights) / standard_d,
    }
    events = terminal.groupby("events").agg(
        n=("events", "size"), served_n=("woba_value", "sum"), served_d=("woba_denom", "sum"),
        missing_value=("woba_value", lambda x: int(x.isna().sum())),
        missing_denominator=("woba_denom", lambda x: int(x.isna().sum())),
    ).reset_index()
    anomalies = terminal.assign(expected_fixed_n=expected_fixed_n, expected_standard_d=expected_d).loc[
        unexpected_value | unexpected_d | missing_positive | terminal.events.eq("truncated_pa")].copy()
    return output, events, anomalies


def compare_audit(prepared, reference, component_reference, reconstruction):
    """Separate independent references from internal diagnostics and verify identity."""
    for record in (reference, component_reference):
        if (record["player_id"] != prepared.player_id or record["season"] != prepared.season
                or record["outcome_year"] != prepared.outcome_year or record["name"] != prepared["name"]):
            raise ValueError("Independent reference identity/season mismatch")
        if (record.get("source") != "FanGraphs"
                or urlparse(record.get("url", "")).hostname != "www.fangraphs.com"
                or datetime.fromisoformat(record["retrieved_at"]).utcoffset() is None):
            raise ValueError("Independent source URL/date required")
    if not prepared.label_available or reference.get("identity_verified") is not True:
        raise ValueError("Audit requires available labels and independently matched references")
    r = reconstruction
    for actual, expected in [(r["served_n"], prepared.mlb_woba_numerator),
                             (r["served_d"], prepared.mlb_woba_denom),
                             (r["terminal_rows"], prepared.mlb_observed_pa),
                             (r["prepared_reconstruction"], prepared.mlb_woba)]:
        if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9):
            raise ValueError("Archive does not reproduce frozen label/components")
    components = component_reference["counts"]
    if set(components) != {"ab", "pa", "single", "double", "triple", "home_run", "bb", "ibb", "hbp", "sf", "sh"}:
        raise ValueError("Incomplete independent season components")
    mismatches = {key: r[key] - value for key, value in components.items()
                  if key in r and r[key] != value}
    published = reference.get("woba")
    if published is None:
        discrepancy = residual = None
        status = "unresolved_reference"
    else:
        published = float(published)
        if not math.isfinite(published):
            raise ValueError("Nonfinite independent reference")
        discrepancy = float(prepared.mlb_woba) - published
        residual = r["standard_diagnostic"] - published
        tolerance = .5 * 10 ** -reference["precision"]
        status = ("within_reference_rounding" if abs(residual) <= tolerance else
                  "compatible_with_display_precision" if abs(residual) <= tolerance + r["coefficient_rounding_bound"]
                  else "unresolved_residual")
    if mismatches:
        status = "unresolved_component_difference"
    if reference["pa"] != prepared.mlb_pa:
        status = "unresolved_coverage_difference"
    row = {
        **{key: prepared[key] for key in ["player_id", "name", "season", "outcome_year", "split", "mlb_woba", "mlb_pa"]},
        **r, "reference_woba": published, "reference_url": reference["url"],
        "reference_player_id": reference["source_player_id"], "reference_source": reference["source"],
        "reference_retrieved_at": reference["retrieved_at"], "reference_precision": reference["precision"],
        "components_url": component_reference["url"], "components_retrieved_at": component_reference["retrieved_at"],
        "signed_discrepancy": discrepancy, "absolute_discrepancy": None if discrepancy is None else abs(discrepancy),
        "standard_residual": residual, "status": status,
        "basic_residual": None if published is None else r["basic_diagnostic"] - published,
        "reference_pa_gap": int(prepared.mlb_pa) - reference["pa"],
        "component_mismatches": str(mismatches), "preliminary": True,
    }
    return row


def discrepancy_summary(rows):
    """Descriptive summaries only, with explicit sample size and unique players."""
    if rows.empty:
        raise ValueError("Nonempty audit sample required")
    differences = rows.signed_discrepancy.dropna()
    return {
        "n_rows": len(rows), "n_references": len(differences), "n_players": rows.player_id.nunique(),
        "mean_signed": None if differences.empty else float(differences.mean()),
        "mean_absolute": None if differences.empty else float(differences.abs().mean()),
        "median_absolute": None if differences.empty else float(differences.abs().median()),
        "min_signed": None if differences.empty else float(differences.min()),
        "max_signed": None if differences.empty else float(differences.max()),
        "n_positive": int(differences.gt(0).sum()), "n_negative": int(differences.lt(0).sum()),
        "mean_absolute_standard_residual": None if differences.empty else float(rows.standard_residual.abs().mean()),
        "mean_signed_basic_residual": None if differences.empty else float(rows.basic_residual.mean()),
        "mean_absolute_basic_residual": None if differences.empty else float(rows.basic_residual.abs().mean()),
        "inference": "purposive nonrandom sample; no population significance claim",
    }

"""Shared safeguards for the Week 1 hitter-season table."""
from __future__ import annotations

import pandas as pd

FEATURE_INPUTS = ["aaa_pa", "aaa_hits", "aaa_ab", "aaa_bb", "aaa_k", "aaa_hr"]


def validate(frame: pd.DataFrame) -> None:
    required = ["player_id", "season", "outcome_year", "prediction_date", "split", "mlb_pa", "mlb_woba", "label_available", "outcome_eligible", "reached_mlb", "label_provisional", "outcome_status", "data_kind", *FEATURE_INPUTS]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing fields: {sorted(missing)}")
    if frame[["player_id", "season"]].isna().any().any() or frame.duplicated(["player_id", "season"]).any():
        raise ValueError("Missing or duplicate row key")
    for column in ["player_id", "season", "outcome_year", "mlb_pa", *FEATURE_INPUTS]:
        if frame[column].isna().any() or not pd.api.types.is_integer_dtype(frame[column]):
            raise ValueError(f"Expected nonmissing integer {column}")
    for column in ["label_available", "outcome_eligible", "reached_mlb", "label_provisional"]:
        if frame[column].isna().any() or not pd.api.types.is_bool_dtype(frame[column]):
            raise ValueError(f"Expected nonmissing boolean {column}")
    if not frame.outcome_year.eq(frame.season + 1).all():
        raise ValueError("Outcome must follow feature season")
    if not pd.to_datetime(frame.prediction_date).eq(pd.to_datetime(frame.outcome_year.astype(str) + "-01-01")).all():
        raise ValueError("Unexpected prediction date")
    if not frame.split.isin(["train", "test", "excluded_overlap"]).all():
        raise ValueError("Unknown split")
    if not frame.data_kind.isin(["real", "synthetic"]).all():
        raise ValueError("Unknown provenance")
    if set(frame.loc[frame.split.eq("train"), "player_id"]) & set(frame.loc[frame.split.eq("test"), "player_id"]):
        raise ValueError("Player overlap between train and test")
    available = frame.label_available.astype(bool)
    if not frame.mlb_woba.notna().eq(available).all():
        raise ValueError("Label missingness does not match availability")
    if (available & ~frame.outcome_eligible.astype(bool)).any() or (frame.outcome_eligible.astype(bool) & ~frame.reached_mlb.astype(bool)).any():
        raise ValueError("Inconsistent selection flags")
    if not frame.reached_mlb.eq(frame.mlb_pa.gt(0)).all() or not frame.outcome_eligible.eq(frame.mlb_pa.ge(75)).all():
        raise ValueError("Selection flags differ from observed playing time")
    expected_status = frame.mlb_pa.map(lambda pa: "eligible" if pa >= 75 else "thin" if pa > 0 else "not_observed")
    if not frame.outcome_status.eq(expected_status).all():
        raise ValueError("Outcome status differs from playing time")
    if (frame[FEATURE_INPUTS] < 0).any().any():
        raise ValueError("Negative feature count")
    if frame.aaa_pa.lt(150).any():
        raise ValueError("Below cohort eligibility floor")
    for prefix, year_column in [("aaa", "season"), ("mlb", "outcome_year")]:
        for suffix in ("first_date", "last_date"):
            column = f"{prefix}_{suffix}"
            if column in frame:
                dates = pd.to_datetime(frame[column])
                if (dates.notna() & dates.dt.year.ne(frame[year_column])).any():
                    raise ValueError(f"Unexpected event year in {column}")


def load(path):
    frame = pd.read_csv(path)
    validate(frame)
    return frame

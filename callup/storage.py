"""Lossless staging representation: nullable integer keys, all other source tokens as text."""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc

KEYS = ["game_pk", "at_bat_number", "pitch_number"]
IDS = ["batter", "pitcher", *KEYS, "on_1b", "on_2b", "on_3b", *[f"fielder_{i}" for i in range(2, 10)]]


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_source(path: Path) -> pd.DataFrame:
    # Only empty tokens are missing; names such as NA or NULL stay literal text.
    return pd.read_csv(path, dtype="string", keep_default_na=False, na_values=[""], encoding="utf-8-sig")


def source_table(frame: pd.DataFrame) -> pa.Table:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    for name in IDS:
        if name in table.column_names:
            index = table.column_names.index(name)
            original = table[name]
            typed = pc.cast(original, pa.int64(), safe=True)
            # Refuse noncanonical IDs rather than silently changing an input token.
            if not pc.cast(typed, pa.string()).equals(pc.cast(original, pa.string())):
                raise ValueError(f"Noncanonical integer token in {name}")
            table = table.set_column(index, name, typed)
    # pandas metadata still describes the pre-cast string dtype; drop it so readers
    # honor the actual Arrow int64 schema rather than recreating string IDs.
    return table.replace_schema_metadata(None)


def verify_roundtrip(frame: pd.DataFrame, table: pa.Table) -> None:
    if len(frame) != table.num_rows or list(frame.columns) != table.column_names:
        raise ValueError("Row count or column order changed")
    for name in frame.columns:
        expected = pa.array(frame[name], type=pa.string(), from_pandas=True)
        actual = pc.cast(table[name], pa.string())
        if not actual.combine_chunks().equals(expected):
            raise ValueError(f"Values/null positions changed in {name}")


def check_gzip(path: Path) -> None:
    with gzip.open(path, "rb") as handle:
        while handle.read(1024 * 1024):
            pass  # read through trailer/CRC, not just the header

# Compressed CSV versus Parquet: measured recommendation

**Keep the original gzip CSV archive and use the verified Parquet staging files for repeated downstream reads.** Small teammate tables can stay readable CSV as well as typed Parquet. No original source file was changed. The conversion script uses a lossless staging schema deliberately: integer ID/key columns, all other original decimal/date/text tokens retained as text. Analytical starter tables have numeric counts/outcomes and boolean selection flags; teammates explicitly parse assigned raw numeric columns.

Measured on all 1,009 source shards (4,754,688 rows), Python 3.13, pandas 3.0.6, pyarrow 25.0.1, Zstandard level 6:

| Consideration | gzip CSV | Parquet staging |
|---|---|---|
| Archive bytes | 1,019,835,496 (972.6 MiB) | 827,539,483 (789.2 MiB), 18.9% smaller |
| Six-shard full materialized load | 0.323 s median | 0.0355 s median, about 9.1× faster |
| Seven-column projected load | 0.116 s median | 0.00737 s median, about 15.7× faster |
| Types | No embedded schema; reader infers and can misparse IDs/NA tokens | Embedded nullable int64 IDs; explicit text tokens; numeric analysis table types |
| Dependencies | Python gzip/csv alone can read it; pandas convenient | pyarrow/pandas or DuckDB; already project requirements |
| Ease of use | Universal and inspectable after decompression; slow repeated parsing | One pandas.read_parquet call with selected columns; fast repeated scans |
| Source fidelity | Source response bytes inside gzip wrapper; canonical retained archive | Every parsed cell/null verified; original numeric token precision preserved |

The gzip size is on-disk compressed size, not expanded CSV. Both copies use under 2 GB before API cache, samples and derived tables. Avoid committing either full format to code Git.

Benchmark selects six evenly spaced shards across feed/year, reads into DataFrames, repeats three times, and reports medians. This uses a warm OS cache on the preparation machine; it does not establish cold-disk, network, cloud, or all-column numeric-workload speed. CSV projection still scans/decompresses the full stream, while Parquet can read selected columns. Six shards include wide schemas and typical daily sizes; full timings and paths are in `reports/storage.json`. Tiny per-day Parquet files have overhead, so later season compaction might improve reads further, but is not needed to start Week 1. Do not generalize this benchmark to every file or tool.

## Why this schema

Raw CSV has many sparse/deprecated columns and decimal strings. Pandas' defaults interpret several literal text tokens as missing and infer types differently in all-null shards. The converter reads all tokens as nullable text, treating **only empty tokens** as missing. It casts known canonical integer IDs to int64 and refuses ambiguous/noncanonical ID spellings. Other tokens remain text so trailing zeros and decimal spellings survive exactly. Stale pandas pre-cast metadata is removed so readers honor the Arrow ID schema. Use `pd.read_parquet(..., dtype_backend='pyarrow')` to retain nullable integer types in pandas. This prioritizes verifiable fidelity; it does not promise already-typed floating pitch measurements. Numeric analysis uses `pd.to_numeric(..., errors='raise')`, with explicit null handling. The derived hitter table is typed and independently roundtripped.

Conversion with `python scripts/prepare_storage.py` never writes into `data/raw`; it reads gzip through its CRC trailer, checks cap/keys/dates/manifests and classifies true minor-league levels. After writing a temp Parquet shard, it compares row and column order and every value/null position against the parsed source, then renames it and confirms the source SHA-256 is unchanged. It checks global key uniqueness and cohort-ID coverage. `reports/storage.json` includes each source/target hash and byte count; `reports/pitch_schema.json` describes all staging fields.

For a teammate, begin with `data/processed/hitter_seasons.csv` and `callup.contract.load`, then project only assigned pitch fields from Parquet. Retain original gzip for future re-parsing and audit. A later typed numeric pitch layer or compaction is optional work, requiring a new schema/version and equivalent validation, not a replacement of the original archive.

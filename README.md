# Callup

Callup studies how Triple-A hitter performance translates into **next-season MLB wOBA**, including selection into MLB participation and sufficient playing time. Week 1 covers features, park research, modeling infrastructure and promotion descriptions. Anish owns methodology, review and integration. Selection correction is later research and does not guarantee unbiased predictions.

Start with the [meeting reference](docs/first-meeting.md), [shared contract](docs/data-contract.md), [methodology](docs/methodology.md), [data dictionary](docs/data-dictionary.md), [Git guide](docs/git-workflow.md) and [five assignment briefs](docs/issues/).

## Clone, install and run offline

Use **Python 3.13** for the tested pinned environment. Install it from [python.org](https://www.python.org/downloads/) if needed. macOS/Linux Terminal:

```bash
git clone https://github.com/AnishAwasthi/callup.git
cd callup
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/offline_example.py
pytest
ruff check .
```

Windows PowerShell: `py -3.13 -m venv .venv` then `.venv\Scripts\Activate.ps1`; remaining commands are the same. If activation is restricted, use `.venv\Scripts\python.exe` directly. Installing needs internet once; demo/tests need no network, source archive or credentials. The original broad requirements target Python ≥3.11, but the frozen set is tested on 3.13, not every older version. Run from the repository root. For missing packages, activate the environment and use `python -m pip` with the same interpreter that runs scripts.

Expect **8 synthetic player-seasons and 96 toy pitches**, contract checks and class counts. These invented records verify setup and joins only; do not use them for baseball conclusions.

## Genuine starter data and access

The preparation machine has a genuine starter table in `data/processed/hitter_seasons.csv`/`.parquet`, plus a small real sample and full selected AAA pitch histories in `data/local_sample/`:

```bash
python scripts/offline_example.py --sample-dir data/local_sample
```

These files stay outside Git. **Teammate access to genuine data is pending source redistribution permission.** No applicable open-data license was established; the public code repository carries a synthetic fixture. [Data-access instructions](docs/data-access.md) document the prepared local release, free Hugging Face limits, required rights/account choices and complete download-to-analysis workflow.

Hugging Face publication is pending. `dataset-lock.json` explicitly has null fields; the downloader fails helpfully. After an approved release, commit the exact 40-character dataset commit SHA and manifest checksum, then teammates run:

```bash
python scripts/download_dataset.py --install
python scripts/offline_example.py --sample-dir data/local_sample
```

No paid services or subscriptions are used. Review the [dataset card](docs/dataset-card.md) and [storage comparison](docs/storage-comparison.md). Public endpoint access does not establish bulk-download/redistribution permission.

## Agreed provisional cohort

AAA hitters with **≥150 PA in 2023–2024**, prediction **January 1 of Y+1**, next regular-season MLB wOBA with **≥75 MLB PA**. Pool: **926 player-seasons; 239 workload-eligible outcomes**. Reconstruction from served Savant values is provisional and needs independent official reconciliation. Full 2024 pool is test; all 2023 players also in that pool are excluded from training. This gives 208 training pool rows (62 workload-eligible), 262 excluded overlap rows, and 456 test rows (125 eligible). Available provisional labels, coverage and PA discrepancies appear in the [generated report](reports/cohort_preparation.json).

The existing cohort already pairs Y with Y+1. Reproduced cached moderate counts for AAA 2023–2025:

| Group | Pool | MLB workload eligible | Thin MLB sample | No next-year row |
|---|---:|---:|---:|---:|
| Hitting (AAA ≥150 PA; MLB ≥75 PA) | 1,385 | 353 | 308 | 724 |
| Pitching (AAA ≥40 IP; MLB ≥20 IP) | 1,144 | 285 | 242 | 617 |
| Combined player-season-group rows | 2,529 | 638 | 550 | 1,341 |

Combined rows are not hitter counts or unique people. Legacy `labeled` means workload eligibility, not a verified wOBA value. The 2025→2026 outcomes were cached September 3, 2026 and are incomplete; exclude them initially. Legacy `never_promoted` means no next-year row, not never in a career. Our `reached_mlb` means next-season batting PA>0, including returning MLB players; it differs from outcome eligibility and label availability.

```bash
python scripts/cohort_report.py --offline --all-thresholds
python scripts/cohort_report.py --offline --seasons 2023 2024 --json
```

These commands need the frozen cache from a permitted release. Offline mode refuses cache misses. Do not force counts to match old results after changing the snapshot or definitions.

## Preserved archive and reproducibility

457 requested AAA/mixed-minors plus 552 MLB gzip CSV shards, six manifests, **4,754,688 rows**: MLB 2,145,111; requested minors 2,609,577. True AAA is 2,038,255 rows, with 571,322 Single-A rows in the minors feed. Derive true levels using both opponents' season-specific candidates. `COL` identifies AAA Columbus and Single-A Columbia; preparation fixes the old single-code mapping bug. All cohort IDs join after correction.

The full audit reads every gzip through its CRC, checks cap/keys/date/game type/schedules/manifests/true levels/ID coverage, and verifies every parsed cell/null survives conversion. Source hashes remain unchanged; global pitch keys are unique. One 2023 MLB empty resume-date export is explained by its game under the official earlier date. Date/ID coverage does not prove every upstream PA exists; PA/measurement discrepancies remain explicit. See [storage report](reports/storage.json).

**Use Parquet for repeated analysis; retain gzip CSV as the source archive.** Verified staging Parquet is 18.9% smaller: 827.5 MB versus 1,019.8 MB. Six-shard warm-cache reads were about 9× faster for all columns and 16× for seven selected columns. ID/key columns are nullable int64; other source tokens remain text to preserve decimal spelling exactly. Parse analytical numerics explicitly. Prepared player-season Parquet has typed counts, booleans and numeric outcomes. The [format memo](docs/storage-comparison.md) explains tradeoffs and benchmark limits.

On the preparation machine or after a permitted full-data download:

```bash
python scripts/prepare_storage.py
python scripts/prepare_analysis.py
python scripts/package_dataset.py --output data/release-new
```

Preparation uses local/cached data and never overwrites raw pitch files. Commit reviewed preparation code before packaging: the package requires a clean worktree and records its exact code revision. Use a new release path to avoid stale files. Published checksum metadata in `reports/release_checksums.json` describes a local package; no Hub revision is claimed until upload.

## Layout and assignments

```text
callup/       Existing ingestion/cohort/API code; storage/contract safeguards
scripts/      Audit/conversion, starter preparation, download, packaging, offline demo
tests/        Network-free tests
docs/         Methodology, contract, dictionary, guides, dataset card, issue briefs
reports/      Aggregate audit/counts/benchmark/checksum metadata; no source records
data/sample/  Small synthetic fixture committed to code Git
data/raw/, cache/, parquet/, processed/, local_sample/, release/  Ignored genuine data
```

Person 1: basic hitting features; Person 2: batted-ball features; Person 3: park research/one prototype; Person 4: mean baseline/Ridge infrastructure; Person 5: promotion descriptions/2–4 plots. [Published assignments](docs/assignments.md) and [issue briefs](docs/issues/) specify inputs, schemas, dependencies and validation. Final models/features/selection correction/park system/Streamlit remain future work. Follow the [Git guide](docs/git-workflow.md): fork if you lack push access, task branch, focused commits, PR linked to Issue, Anish review. CI runs lint, tests, the synthetic demo and tracked-data guard.

## Existing ingestion tools

Ingestion uses urllib and daily Savant CSV exports, **not pybaseball**, with resume and 25,000-row cap detection. Avoid repeating the full download. Existing commands remain for authorized use:

```bash
python scripts/ingest_statcast.py --estimate
python scripts/validate_archive.py
```

The original validator checks schedules plus sampled 2024 AAA rows; `prepare_storage.py` performs full-record checks. Legacy live commands may fetch uncached metadata; do not call them guaranteed offline. Preserve original files; do not force-overwrite them.

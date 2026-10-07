# Data access and reproducible workflow

## Hosting decision, checked October 6, 2026

Use Parquet for repeated analysis, preserve gzip CSV as the source archive, and keep all full data outside the code repository. The prepared local package is `data/release/`; its published metadata/checksums are `reports/release_checksums.json` and `reports/release_summary.json`. It is not uploaded.

[Hugging Face's current storage policy](https://huggingface.co/docs/hub/storage-limits) lists free-account private storage as **100 GB account-wide** and public storage as **best effort**, not a guaranteed unlimited quota. Existing stored data consumes that allowance. Paid tiers can charge for extra storage. Our approximately 2 GB bundle is small relative to the free allowance, but account capacity must be checked before upload. Do not subscribe, enable add-ons, pay-as-you-go or compute Spaces. A plain dataset repository needs no training/inference service.

Source suitability is unresolved. [Savant links to MLB terms](https://baseballsavant.mlb.com/); those terms require permission for redistribution. The [MLB data notice](https://gdx.mlb.com/components/copyright.txt) permits individual, noncommercial, nonbulk use and requires prior written authorization for other uses. I found no source-specific open redistribution license. This is evidence to request clearance, not a legal determination about every statistical fact. Public availability and a private repository do not establish permission to share the archive. Do not assign CC0/MIT to third-party data, upload the raw/converted archive, or commit a real sample until the applicable rights are established. The code repository therefore carries a synthetic sample; the genuine sample and trace remain local.

## What Anish should do for Hugging Face

1. Obtain a written source permission or identify a specific applicable license that covers this archive, derived tables and teammate access. Keep the evidence and approved scope. If unavailable, use a permitted independently acquired source; don't publish this bundle. Source download commands here are for authorized users, not a claim that bulk fetching is permitted.
2. Log into the existing Hugging Face account. Choose a namespace/name, for example `<your-account>/callup-statcast-2023-2025`, and **private** for a controlled team workflow or **public** only if the cleared rights allow it. For controlled sharing, a free organization with each teammate as a `read` member is a practical option under the [current organization access rules](https://huggingface.co/docs/hub/organizations-security); check access before the meeting. Fine-grained resource groups require paid plans and are unnecessary here. Never share one token among teammates.
3. In account/organization settings, confirm it is a free plan, current storage usage and at least the bundle's total remaining free capacity. Confirm permission for all recipients. Stop if the interface proposes an upgrade or charge. Free storage is account-wide and version history can retain old files.
4. Review `docs/dataset-card.md`, resolve the rights status and license metadata honestly, regenerate a reviewed release, then create a **Dataset** repository on the Hub's New Dataset page. No Space is needed. Use a scoped write token only on the publishing machine (interactive `hf auth login`); do not paste it into this chat or commit it. Upload the reviewed tree with `hf upload <namespace/name> data/release-new . --repo-type dataset`. The explicit `.` installs it at repository root so the downloader finds `checksums.json`. This command must wait for clearance and the account choices above.
5. Obtain the full 40-character commit SHA from the uploaded dataset's commit history. Open `checksums.json` at that revision. Its SHA-256 must match the local release summary. Set `dataset-lock.json` to the real repo ID, that exact SHA and `manifest_sha256`; commit the lock to the code repository. Never use `main` or a floating tag as the download pin.
6. Have a teammate with their own read access run the downloader and offline example. Download from the pinned commit, verify hashes and test access before declaring the data handoff ready.

The preparation does not create a Hugging Face repo because the user asked for an evaluation first and no redistribution permission/repo choice was supplied. The lock is explicitly unconfigured and the downloader fails with an actionable message; it does not quietly fetch latest data. A true pinned download is pending publication, not claimed completed.

## Full workflow once a permitted release exists

From a fresh clone, install the tested Python 3.13 environment using the README. With a populated lock:

```bash
# Public data requires no login. Private data: each teammate uses their own read token.
hf auth login
python scripts/download_dataset.py --install
python scripts/offline_example.py --sample-dir data/local_sample
python scripts/cohort_report.py --offline --all-thresholds
python scripts/prepare_storage.py
python scripts/prepare_analysis.py
```

The download resolves every file at the locked commit, verifies the pinned manifest SHA plus each file's size/hash, and only then installs. It refuses to overwrite different existing inputs. Downloads land in ignored `data/incoming/`; verified source files go into `data/raw/`, API responses into `data/cache/`, staging files into `data/parquet/`, and the hitter table into `data/processed/`. Regenerating Parquet is optional if the verified release already includes it. The checksum comparison locks exact supplied bytes; reproducing byte-identical Parquet in another library version is not guaranteed, so conversion correctness also uses cell-by-cell comparison and the tested dependency lock.

For a permitted non-Hub handoff, copy the same release tree through an approved team storage channel. Compare `checksums.json` to the trusted SHA in `reports/release_summary.json`, verify every entry, and copy its `raw`, `cache`, `parquet`, `processed`, `local_sample` directories into `data/`. Preserve relative paths. A transfer destination and access policy still need approval; this is not authorization to redistribute.

## Local reproducibility on the preparation machine

```bash
python scripts/cohort_report.py --offline --all-thresholds --json
python scripts/prepare_storage.py       # all shards; offline metadata cache; no source writes
python scripts/prepare_analysis.py      # 2023–2024 hitters; provisional labels; no final features
python scripts/offline_example.py --sample-dir data/local_sample
git status  # Commit reviewed preparation code before packaging its exact code revision.
python scripts/package_dataset.py --output data/release-new
```

The original cache had only 2024 team metadata. Preparation fetched ten missing season-level team responses for 2023/2025; no pitch files were redownloaded. To reproduce from a fresh raw archive without the release cache, an authorized metadata refresh is `StatsAPI().team_level_candidates(year)` for each year; this does not fix incomplete outcomes automatically. Record any refresh separately and rerun reports.

Week 1 feature readers can select a small set of columns:

```python
from pathlib import Path
import pandas as pd
from callup.ingest import derive_levels
from callup.statsapi import StatsAPI
from callup.contract import load

cohort = load('data/processed/hitter_seasons.csv')
api = StatsAPI(offline=True)
paths = sorted(Path('data/parquet/AAA').glob('2023-*.parquet'))
for path in paths:  # stream shards; avoid loading all 4.75M rows into RAM
    day = pd.read_parquet(path, columns=['batter', 'game_date', 'home_team', 'away_team', 'events', 'launch_speed'])
    day = day.loc[derive_levels(day, api.team_level_candidates(2023)).eq('AAA')]
    day['launch_speed'] = pd.to_numeric(day.launch_speed, errors='raise')
    # Accumulate your assigned features by batter and season here.
```

The `COL` abbreviation is ambiguous between AAA Columbus and Single-A Columbia. Candidate intersection across both opponents resolves real archive rows; unresolved pairs are null and must be investigated. A single-code map is unsafe.

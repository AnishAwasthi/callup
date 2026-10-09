---
pretty_name: Callup MLB and mixed minor-league Statcast archive 2023–2025
language:
  - en
task_categories:
  - tabular-regression
  - tabular-classification
size_categories:
  - 1M<n<10M
license: other
license_name: MLB source terms; redistribution clearance pending
license_link: https://www.mlb.com/official-information/terms-of-use
---

# Callup dataset card

## Provenance and intended use

Callup studies hitter performance translation from Triple-A to MLB and selection into observed next-season MLB batting outcomes. Source: MLB Advanced Media's Baseball Savant daily CSV export and MLB Stats API season statistics, schedules and team metadata. Prepared by Anish Awasthi's Callup project; project code: https://github.com/AnishAwasthi/callup. Original archive manifests were written September 3–4, 2026; precise HTTP response timestamps and original checksums were not recorded at ingestion. Checksums now fingerprint the preserved archive, not a independently captured pre-ingestion source. Cache filenames are SHA-256-derived URL keys; parameter construction is in `callup/statsapi.py`. The original Stats API caches are a September 3 snapshot; added 2023/2025 team metadata was fetched during October 6 preparation.

Source endpoints: `https://baseballsavant.mlb.com/statcast_search/csv` (MLB), `https://baseballsavant.mlb.com/statcast-search-minors/csv` (mixed minors), `https://statsapi.mlb.com/api/v1/`. Regular-season requests use `hfGT=R|`, one date at a time; the minors request also uses `minors=true` and season filter. The 25,000-row cap is checked; raw CSV response bytes are preserved inside gzip wrappers. No pybaseball dependency is used.

## Rights and access status

**Storage:** Anish reports that the prepared package is uploaded to the shared Google Drive folder linked in the README. There is no Hugging Face dataset repository. **Source redistribution clearance remains unresolved.** Source records do not inherit any license applied to project code. The [MLB data notice](https://gdx.mlb.com/components/copyright.txt) and [MLB terms](https://www.mlb.com/official-information/terms-of-use) must be reviewed against the intended use. Document actual permission, license scope and permitted recipients here before publishing. A private Hub repo is an access setting, not permission to redistribute. There is no established open-data license for this release.

## Coverage and contents

The preserved archive has 1,009 gzip CSV shards: 457 requested AAA/mixed-minors dates and 552 MLB dates, spanning 2023–2025, totaling 4,754,688 rows. **The requested AAA directory includes Single-A Florida State League records and is not a pure AAA dataset.** True levels are derived from both opponents using year-specific team metadata; `COL` is ambiguous and resolved by intersection of both teams' level candidates. `reports/storage.json` records exact true-level counts, coverage, linkage, warnings and audit results. MLB uses 2,145,111 rows; the requested minors feed has 2,609,577 rows. Scheduled export dates match the cached schedule. One 2023 MLB resumed-game date is header-only; the corresponding game is present under its official earlier date. Date coverage alone does not prove every pitch/PA is present upstream.

Directories in the prepared package:

| Directory | Contents / schema |
|---|---|
| raw/AAA, raw/MLB | original gzip CSV per requested feed/date; raw fields documented by Savant |
| cache | frozen Stats API JSON responses needed for offline reconstruction |
| parquet/AAA, parquet/MLB | one Zstandard-compressed Parquet per source shard; same row/column order, nullable int64 IDs, other tokens as text |
| processed | hitter_seasons.csv/parquet and preparation_report.json, 2023–2024 feature seasons |
| local_sample | small real hitter-season sample, full selected AAA pitch histories and a real player trace |
| checksums.json | versioned SHA-256/byte manifest of all payload files |

The player-season contract in the code repository defines every column, missing value and split. Numeric `player_id` is MLBAM ID; raw hitter linkage uses `batter`. The primary player-season key is `(player_id, season)`; the pitch key adds `game_pk, at_bat_number, pitch_number`. ID linkage and roundtrip cell/null equality are verified. A small **synthetic** demo is separately in the code repository; never mix it with this real dataset.

True-level audit counts: AAA 691,656 (2023), 675,342 (2024), 671,257 (2025), totaling 2,038,255; Single-A 571,322. Gzip CSV occupies 1,019,835,496 bytes; staging Parquet 827,539,483 bytes. Initial player-season table: 926 rows, 443 observed next-season MLB batting participants, 239 eligible/provisional outcomes, 204 thin participants and 483 without observed batting PA. Player-disjoint training has 208 pool rows/62 labels; test 456/125; excluded overlap 262/52. The real sample has 13 player-seasons and 14,067 observed AAA pitches. Exact release size and all hashes are in the manifest.

## Preparation and reproduction

Install the code repository's tested dependency lock on Python 3.13. `scripts/prepare_storage.py` validates gzip CRC, date/game type, row caps, per-shard pitch keys, schedules/manifests, season-specific true levels and cohort-ID presence. It writes staging Parquet atomically and compares every cell/null position plus original archive hashes. Non-ID tokens remain text to avoid silently changing floating decimal representations. Numeric analytical fields are explicitly parsed downstream. `reports/pitch_schema.json` documents staging types.

`scripts/prepare_analysis.py` selects hitters with AAA PA ≥150 in 2023–2024, uses Jan 1 of Y+1 as prediction date, and joins next regular-season MLB via ID. MLB PA ≥75 is outcome eligibility; participation (PA>0) and label availability are separate. It sums cached preliminary AAA counts and reconstructs **provisional** MLB wOBA from served terminal-event values/denominators. Future-looking fields are excluded. The 2024 feature-season pool is test; any 2023 player also present in it is excluded from training. Full models and Week 1 feature sets are not part of this release.

`scripts/package_dataset.py` creates the local distribution tree and checksum manifest. After approved upload, pin the dataset's full commit SHA and manifest digest in the code repository's `dataset-lock.json`. Teammates run `scripts/download_dataset.py --install` to retrieve exactly that revision and verify all checksums before analysis. No pinned Hub revision exists until publication; the current lock explicitly refuses downloads.

## Limitations and appropriate interpretation

Selection into MLB and into sufficient playing time is informative; unmeasured scouting, health and organizational decisions remain. Selection correction does not guarantee unbiased predictions. This cohort includes repeat MLB participants, not just first-ever promotions; nonparticipation is window-specific, not permanent career failure. Two fully observed outcome seasons provide limited temporal validation, and excluding overlapping players changes the test estimand.

Raw tracking, terminal-event and official PA counts can disagree, and missing tracking is not a zero measurement. Provisional wOBA requires independent reconciliation to official season outcomes; source event weights may differ from season-specific published weights. Cached API lines may differ from later corrected data. 2025 AAA →2026 outcomes are excluded because the cached 2026 lines are incomplete and no 2026 pitches were archived. Feature eligibility is not the same as an outcome value being verified. Park effects, team/venue mapping, age/experience controls and fair subgroup evaluation remain unfinished.

No medical, financial or professional personnel decisions should be based on this research starter. No guarantee is made of source completeness or prospective availability of retrospectively computed fields. Retain the frozen revision, checksums, exact code revision and environment version in every experiment.

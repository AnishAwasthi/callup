# Full archive audit summary

Checked October 6, 2026. Every source shard was parsed and roundtripped, not sampled.

| Feed / year | Shards | Source rows | True AAA rows | Single-A rows |
|---|---:|---:|---:|---:|
| Mixed minors 2023 | 151 | 884,503 | 691,656 | 192,847 |
| Mixed minors 2024 | 154 | 863,869 | 675,342 | 188,527 |
| Mixed minors 2025 | 152 | 861,205 | 671,257 | 189,948 |
| MLB 2023 | 183 | 720,684 | — | — |
| MLB 2024 | 185 | 711,899 | — | — |
| MLB 2025 | 184 | 712,528 | — | — |

All gzip CRCs, cap checks, date/regular-season checks, per-shard keys, scheduled dates and manifest counts pass. All 4,754,688 global pitch keys are unique. All moderate hitter and pitcher cohort IDs are present in true AAA for each year. `COL` is resolved via both teams' level candidates; the original code's single-code map was wrong. No unknown/mismatched true levels remain.

One warning: the scheduled MLB 2023-10-02 export is header-only. The cached schedule gives a resumed game's official date as 2023-09-28, and its game ID is present in that archived official-date file. Preserve the empty response rather than replacing it or inventing pitches. This verifies representation of that scheduled game ID, not independent completeness of every source pitch.

AAA nonmissing tracking coverage:

| Year | release_speed | release_spin_rate | pfx_x / pfx_z | launch_speed / launch_angle |
|---|---:|---:|---:|---:|
| 2023 | 99.54% | 98.34% | 99.53% / 99.53% | 30.89% / 30.93% |
| 2024 | 99.75% | 98.71% | 99.75% / 99.75% | 31.47% / 31.51% |
| 2025 | 99.70% | 98.55% | 99.70% / 99.70% | 31.02% / 31.06% |

Exit-velocity/angle sparsity over all pitches is expected; report valid-measurement coverage over eligible batted balls in Person 2's assignment. These all-pitch percentages do not establish complete BBE measurement coverage.

Every row, column order, ID value, text/decimal token and null position survived conversion. Source SHA-256 stayed unchanged. The final staging writer removes stale pandas dtype metadata so numeric IDs load correctly. `reports/storage.json` includes all source/target hashes, exact bytes, detailed coverage and benchmark timings. Original CSV gzip stays preserved; source coverage limitations and provisional labels are documented in methodology and the cohort report.

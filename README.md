# callup

> Translating Triple-A performance into major-league expectations — using real linked
> data, and taking the selection problem seriously.

A **call-up** is the moment a player is promoted from Triple-A to the majors. This
project asks the question that precedes it: *given what a player did at AAA, what should
we expect in MLB?*

---

## Why this is a real problem and not a toy

Everyone who has looked at minor-league translation hits the same wall, and most projects
walk straight past it.

**You only observe major-league outcomes for players who got promoted.** Teams promote
players they already believe will succeed — using scouting information, medicals, and
organizational context that never appears in a box score. So the labeled sample is not a
random draw from Triple-A. It is the part of the distribution a front office already
selected.

Fit a plain regression on that sample and apply it to everyone, and you have implicitly
assumed the promotion decision carried no information. It carried a great deal. This is
the same structural problem as estimating the wage return to a college degree using only
people who are currently employed.

**In this dataset, roughly 75% of qualifying AAA player-seasons have no usable
major-league outcome.** That is not a footnote. It is the modeling problem.

## Is there enough data? (yes — this was checked first)

Before writing any model, [`scripts/cohort_report.py`](scripts/cohort_report.py) answers
the only question that matters at the start: does a real labeled cohort exist?

```
AAA -> MLB cohort  ·  seasons [2023, 2024, 2025]  ·  moderate thresholds

HITTING   (AAA >= 150 PA, MLB >= 75 PA)
  labeled  (usable for training)    353
  promoted but thin sample          308
  never reached MLB                 724
  pool                             1385
  no usable outcome (censored)    74.5%

PITCHING  (AAA >= 40 IP, MLB >= 20 IP)
  labeled  (usable for training)    285
  promoted but thin sample          242
  never reached MLB                 617
  pool                             1144
  no usable outcome (censored)    75.1%

TOTAL labeled training rows: 638
TOTAL AAA player-seasons:    2529
```

638 real labeled examples, with a censored majority large enough that ignoring it would
be indefensible. Run it yourself:

```bash
pip install -r requirements.txt
python scripts/cohort_report.py --all-thresholds
```

Responses are cached to `data/cache/`, so the first run takes a minute and every run
after is instant.

## Why AAA and not college

An earlier version of this idea tried to translate **amateur** (NCAA / Cape Cod)
performance to MLB. That cannot be validated with public data: amateur tracking data is
proprietary, and there is no public mapping from an amateur player to their eventual
major-league career. Any "accuracy" reported against such a dataset is fabricated by
construction.

Triple-A is different, and that difference is the entire reason this project exists:

- **Statcast tracking has been public for all of Triple-A since 2023**, via Baseball
  Savant's [minor-league search](https://baseballsavant.mlb.com/statcast-search-minors).
- Players carry the **same MLBAM player id** across levels, so the AAA season and the
  MLB season are linked by construction rather than by guesswork.
- Promotions happen constantly, giving hundreds of genuinely matched pairs per year.

The translation question is the same. The difference is that here it can actually be
answered.

## Data sources

| Source | What it provides | Notes |
|---|---|---|
| [MLB Stats API](https://statsapi.mlb.com/api/v1/) | Season lines, rosters, teams, levels | Public, no key. `sportId` 1=MLB, 11=AAA |
| [Baseball Savant](https://baseballsavant.mlb.com/statcast-search-minors) | Pitch-level tracking, MLB and AAA | CSV export; **hard 25,000-row cap per query** |

Two traps found while probing these, both of which silently corrupt results:

1. **Savant truncates at exactly 25,000 rows with no error.** A seven-day MLB query
   returns precisely 25,000 rows and looks fine. Ingestion must chunk by date and detect
   when a chunk hits the cap.
2. **The minors CSV has no level column.** The feed mixes Triple-A with the Florida State
   League, and the only way to tell them apart is the team abbreviation — so the level
   has to be joined on from the Stats API.

## Layout

```
callup/
  statsapi.py     Cached, polite Stats API client; level codes; innings parsing
  cohort.py       AAA player-seasons partitioned into labeled / thin / censored
scripts/
  cohort_report.py  Viability check — run this first
tests/            No network; the API is faked
```

## Status

- [x] Viability confirmed — 638 labeled rows across three seasons
- [ ] Pitch-level ingestion (chunked, resumable, cap-aware)
- [ ] Park factors across AAA venues (several at real altitude — Albuquerque 5,100 ft,
      Reno 4,500 ft, Salt Lake 4,200 ft)
- [ ] Baseline translation model on labeled rows only, with its bias measured
- [ ] Selection-corrected model, compared against that baseline
- [ ] Held-out evaluation on the most recent promotion window

The fourth and fifth items are the point of the project. The deliverable is the
*difference* between them.

## Testing

```bash
pytest
```

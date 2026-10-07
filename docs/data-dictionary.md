# Initial data dictionary

Canonical upstream field reference: [Savant CSV documentation](https://baseballsavant.mlb.com/csv-docs). `reports/pitch_schema.json` records every observed pitch column's staging type. `docs/data-contract.md` defines every player-season field.

| Source field | Meaning / unit | Preparation use and caution |
|---|---|---|
| batter, pitcher | MLBAM player IDs | typed nullable int64; batter joins hitter cohort |
| game_pk | unique game ID | pitch/PA grouping; not a feature |
| at_bat_number, pitch_number | game PA number, pitch within PA | PA key=(game_pk, at_bat_number); pitch key adds pitch_number |
| game_date, game_year, game_type | date/year; R=regular season | feature Y vs outcome Y+1; audit checks R and date |
| home_team, away_team | team abbreviations | season-specific true-level filtering, preliminary park proxy |
| events | terminal PA outcome token | PA/event counting; sparse on intermediate pitches; do not count every pitch as PA |
| description, type | pitch result token; B/S/X | teammates define swing/contact treatment, including bunts and foul tips |
| launch_speed | exit velocity, mph | may include upstream estimates; missing ≠0 |
| launch_angle | batted-ball angle, degrees | separate measured/nonmissing denominator |
| release_speed | pitch velocity, mph | tracking coverage diagnostic |
| release_spin_rate | spin, rpm | tracking coverage diagnostic |
| pfx_x, pfx_z | movement, feet, catcher perspective | tracking coverage diagnostic |
| woba_value, woba_denom | source event weight and denominator | reconstruct observed provisional wOBA; not xwOBA |
| estimated_woba_using_speedangle | estimated event value | not the agreed outcome |
| player_name | name tied to pitch search perspective | not a batter join key |
| *_days_until_next_game | retrospectively known future interval | exclude from predictors |
| deprecated / all-null fields | upstream compatibility fields | preserve in conversion, do not impute into features |

Basic hitting assignment: PA means plate appearances; K%=strikeouts/PA; BB%=walks/PA (document intentional-walk convention). Swing rate denominator is eligible pitches; contact rate denominator is eligible swings. Decide treatment of foul bunts, missed bunts, foul tips and pitchouts with Anish; document exact description-token sets. Batted-ball assignment: hard-hit threshold is EV ≥95 mph, denominator is batted balls with valid EV; report EV coverage independently. Report launch-angle coverage separately and avoid reducing all missing EV to zero.

## Trace one real player

The generated local file `data/local_sample/player_trace.json` traces Nathan Lukes (MLBAM 664770), AAA 2023 to MLB 2024, including cached official PA/counts, observed AAA pitch and PA counts/dates, MLB numerator/denominator/date bounds, eligibility and provisional outcome. `data/local_sample/pitches.csv` contains his complete observed AAA pitch history with other small-sample players. Use:

```python
import pandas as pd
from callup.contract import load
rows = load('data/local_sample/hitter_seasons.csv')
row = rows.query('player_id == 664770 and season == 2023').iloc[0]
pitches = pd.read_csv('data/local_sample/pitches.csv')
aaa = pitches[pitches.batter.eq(664770) & pitches.game_date.str.startswith('2023')]
assert len(aaa) == row.aaa_observed_pitches
assert aaa.events.notna().sum() == row.aaa_observed_pa
assert aaa.game_date.max() < row.prediction_date
assert row.outcome_year == 2024
print(row[['aaa_pa', 'aaa_observed_pa', 'mlb_pa', 'mlb_observed_pa', 'mlb_woba']])
```

Recreate the outcome from MLB 2024 Parquet shards selecting `batter==664770` and nonmissing events, sum numeric served weights/denominators, and compare to the trace within floating roundoff. The preparation script performs that aggregation over all shards and retains sums. A mismatch between observed PA and cached official PA is a documented measurement limitation, not patched to force equality. The trace is local pending redistribution clearance; no source records are published in the public code repository.

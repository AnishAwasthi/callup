import pandas as pd

# Load the full 2023 and 2024 Triple-A pitch datasets
pitches_2023 = pd.read_csv("callup-csv/data/pitches/aaa_2023.csv")
pitches_2024 = pd.read_csv("callup-csv/data/pitches/aaa_2024.csv")

# Combine both seasons into one dataset
pitches = pd.concat(
    [pitches_2023, pitches_2024],
    ignore_index=True
)

# Keep only pitches from players in our study
pitches = pitches[pitches["in_cohort"]]

# Show the first five rows
print(pitches.head())

# Show how many pitches we have
print("Total pitches:", len(pitches))
# Exclude incomplete plate appearances
completed = pitches[
    pitches["events"].notna()
    & (pitches["events"] != "truncated_pa")
].copy()

# Count each completed batting turn only once
completed = completed.drop_duplicates(
    subset=["season", "game_pk", "at_bat_number", "batter"]
)

# Calculate plate appearances for each player-season
pa_counts = (
    completed.groupby(["season", "batter"])
    .size()
    .reset_index(name="PA")
)

print(pa_counts.head())
print("Total completed plate appearances:", pa_counts["PA"].sum())
# Count strikeouts for each player-season
strikeouts = (
    completed.assign(
        is_strikeout=completed["events"].isin(
            ["strikeout", "strikeout_double_play"]
        )
    )
    .groupby(["season", "batter"])["is_strikeout"]
    .sum()
    .reset_index(name="strikeouts")
)

# Count walks, including intentional walks
walks = (
    completed.assign(
        is_walk=completed["events"].isin(["walk", "intent_walk"])
    )
    .groupby(["season", "batter"])["is_walk"]
    .sum()
    .reset_index(name="walks")
)

# Combine counts with plate appearances
stats = pa_counts.merge(strikeouts, on=["season", "batter"])
stats = stats.merge(walks, on=["season", "batter"])

# Calculate rates
stats["K_rate"] = stats["strikeouts"] / stats["PA"]
stats["BB_rate"] = stats["walks"] / stats["PA"]

print(stats)
# Define pitch descriptions that count as swings
swing_events = [
    "foul",
    "hit_into_play",
    "swinging_strike",
    "swinging_strike_blocked",
    "foul_tip",
    "foul_bunt",
    "missed_bunt",
]

# Define swings where the batter made contact
contact_events = [
    "foul",
    "hit_into_play",
    "foul_tip",
    "foul_bunt",
]

# Identify swings and contact
pitches["is_swing"] = pitches["description"].isin(swing_events)
pitches["is_contact"] = pitches["description"].isin(contact_events)

# Calculate counts for each player-season
swing_stats = (
    pitches.groupby(["season", "batter"])
    .agg(
        total_pitches=("description", "count"),
        swings=("is_swing", "sum"),
        contacts=("is_contact", "sum"),
    )
    .reset_index()
)

# Combine with the existing statistics
stats = stats.merge(swing_stats, on=["season", "batter"], how="left")

# Calculate swing rate and contact rate
stats["swing_rate"] = stats["swings"] / stats["total_pitches"]
stats["contact_rate"] = stats["contacts"] / stats["swings"].replace(0, float("nan"))

# Display the results
print(stats.to_string(index=False))
# Load the study roster
roster = pd.read_csv(
    "callup-csv/data/processed/hitter_seasons.csv"
)

# Match calculated statistics to each player and season
features = roster.merge(
    stats,
    left_on=["player_id", "season"],
    right_on=["batter", "season"],
    how="left",
    validate="one_to_one"
)

# Check that all study rows are preserved
assert len(features) == 926

# Show the results
print("\nTotal player-season rows:", len(features))
print("Players with calculated statistics:", features["PA"].notna().sum())

print(
    features[
        ["name", "season", "PA", "K_rate", "BB_rate",
         "swing_rate", "contact_rate"]
    ].head(10).to_string(index=False)
)
from pathlib import Path

output_path = Path("data/processed/features_basic.csv")
output_path.parent.mkdir(parents=True, exist_ok=True)

features.to_csv(output_path, index=False)

print("Saved results to:", output_path)
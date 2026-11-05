
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ----------------------------------
# 1. SET UP FILE PATHS
# ----------------------------------

data_dir = Path("data/shared/pitches")
output_dir = Path("data/processed")
report_dir = Path("reports")

output_dir.mkdir(parents=True, exist_ok=True)
report_dir.mkdir(parents=True, exist_ok=True)

columns = [
    "pitch_type",
    "release_speed",
    "release_spin_rate",
    "pfx_x",
    "pfx_z"
]

# ----------------------------------
# 2. LOAD DATA
# ----------------------------------

def load_data(league, year):
    path = data_dir / f"{league}_{year}.csv.gz"
    df = pd.read_csv(path, usecols=columns)
    df["league"] = league.upper()
    df["year"] = year
    return df

print("Loading baseball data...")

datasets = [
    load_data(league, year)
    for year in [2023, 2024]
    for league in ["aaa", "mlb"]
]

data = pd.concat(datasets, ignore_index=True)

print("Total pitch records:", len(data))

# ----------------------------------
# 3. CALCULATE STATISTICS
# ----------------------------------

summary = (
    data.groupby(["year", "league", "pitch_type"])
    .agg(
        pitch_count=("pitch_type", "size"),
        avg_speed=("release_speed", "mean"),
        avg_spin=("release_spin_rate", "mean"),
        avg_horizontal_movement=("pfx_x", "mean"),
        avg_vertical_movement=("pfx_z", "mean")
    )
    .reset_index()
)

summary = summary.round(2)

summary.to_csv(
    output_dir / "pitch_summary_2023_2024.csv",
    index=False
)

print("\nPitch summary created!")

# ----------------------------------
# 4. COMPARE AAA AND MLB
# ----------------------------------

comparison = summary.pivot(
    index=["year", "pitch_type"],
    columns="league",
    values=[
        "pitch_count",
        "avg_speed",
        "avg_spin",
        "avg_horizontal_movement",
        "avg_vertical_movement"
    ]
)

comparison.columns = [
    f"{stat}_{league}"
    for stat, league in comparison.columns
]

comparison = comparison.reset_index()

for stat in [
    "avg_speed",
    "avg_spin",
    "avg_horizontal_movement",
    "avg_vertical_movement"
]:
    comparison[f"{stat}_difference"] = (
        comparison[f"{stat}_MLB"]
        - comparison[f"{stat}_AAA"]
    )

comparison = comparison.round(2)

comparison.to_csv(
    output_dir / "aaa_mlb_pitch_comparison.csv",
    index=False
)

print("AAA vs MLB comparison created!")

# ----------------------------------
# 5. FOCUS ON COMMON PITCH TYPES
# ----------------------------------

common_pitches = ["FF", "SL", "CH", "SI", "FC", "CU"]

filtered = comparison[
    comparison["pitch_type"].isin(common_pitches)
].copy()

filtered.to_csv(
    output_dir / "common_pitch_comparison.csv",
    index=False
)

print("Common pitch comparison created!")

# ----------------------------------
# 6. CREATE GRAPHS
# ----------------------------------

for year in [2023, 2024]:

    year_data = filtered[
        filtered["year"] == year
    ].copy()

    year_data = year_data.set_index("pitch_type")

    # Pitch speed graph
    year_data[
        ["avg_speed_AAA", "avg_speed_MLB"]
    ].plot(kind="bar", figsize=(10, 6))

    plt.title(f"AAA vs MLB Pitch Speed ({year})")
    plt.xlabel("Pitch Type")
    plt.ylabel("Average Speed (mph)")
    plt.xticks(rotation=0)
    plt.tight_layout()

    plt.savefig(
        report_dir / f"pitch_speed_{year}.png"
    )
    plt.close()

    # Spin rate graph
    year_data[
        ["avg_spin_AAA", "avg_spin_MLB"]
    ].plot(kind="bar", figsize=(10, 6))

    plt.title(f"AAA vs MLB Spin Rate ({year})")
    plt.xlabel("Pitch Type")
    plt.ylabel("Average Spin Rate (RPM)")
    plt.xticks(rotation=0)
    plt.tight_layout()

    plt.savefig(
        report_dir / f"pitch_spin_{year}.png"
    )
    plt.close()

# ----------------------------------
# 7. PRINT RESULTS
# ----------------------------------

print("\n2023 and 2024 AAA vs MLB Comparison:")
print(
    filtered[
        [
            "year",
            "pitch_type",
            "avg_speed_difference",
            "avg_spin_difference"
        ]
    ].to_string(index=False)
)

print("\nAnalysis complete!")
print("CSV files saved in data/processed/")
print("Graphs saved in reports/")

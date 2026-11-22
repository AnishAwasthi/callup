
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from player_display_settings import STAT_GROUPS

DEFAULT_DATA_PATH = Path("data/shared/processed/hitter_seasons.csv")
DEFAULT_FEATURES_PATH = Path("data/processed/features_basic.csv")

def load_data():
    """Load player seasons and optional future features."""
    data_path = Path(os.getenv("CALLUP_DATA_PATH", str(DEFAULT_DATA_PATH)))
    features_path = Path(
        os.getenv("CALLUP_FEATURES_PATH", str(DEFAULT_FEATURES_PATH))
    )

    df = pd.read_csv(data_path)

    required = {"player_id", "name", "season"}
    if not required.issubset(df.columns):
        raise ValueError("Player data must contain player_id, name, and season.")

    if df.duplicated(["player_id", "season"]).any():
        raise ValueError("Duplicate player ID and season combinations found.")

    # Optional features from Issue #8
    if features_path.is_file() and features_path.resolve() != data_path.resolve():
        features = pd.read_csv(features_path)

        if {"player_id", "season"}.issubset(features.columns):
            if features.duplicated(["player_id", "season"]).any():
                raise ValueError("Duplicate player-season rows in features file.")

            new_columns = [
                col
                for col in features.columns
                if col not in df.columns
                and col not in {"player_id", "season"}
            ]

            df = df.merge(
                features[["player_id", "season"] + new_columns],
                on=["player_id", "season"],
                how="left",
                validate="one_to_one",
            )

    return df


def format_stat(value, settings):
    """Format a statistic without turning missing values into zero."""
    if pd.isna(value):
        return "Unavailable"

    unit = settings.get("unit", "count")
    decimals = settings.get("decimals", 0)

    if unit == "boolean":
        return "Yes" if bool(value) else "No"

    if unit == "percentage":
        return f"{float(value) * 100:.{decimals}f}%"

    if unit == "decimal":
        return f"{float(value):.{decimals}f}"

    if unit == "count":
        return f"{float(value):,.0f}"

    return str(value)


def show_stat_group(title, stats, record):
    """Display all approved statistics in a group."""
    available_stats = [
        (column, settings)
        for column, settings in stats.items()
        if column in record.index
    ]

    if not available_stats:
        return

    st.subheader(title)

    for column, settings in available_stats:
        value = format_stat(record[column], settings)

        st.metric(
            label=settings["label"],
            value=value,
            help=settings.get("description", ""),
        )


def main():
    st.set_page_config(
        page_title="Callup Player Profile",
        page_icon="⚾",
        layout="wide",
    )

    st.title("⚾ Callup Player Profile")
    st.write(
        "Explore Triple-A hitters and their season statistics."
    )

    try:
        df = load_data()
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
        st.error(f"Could not load player data: {error}")
        st.stop()

    if df.empty:
        st.warning("No player records are available.")
        st.stop()

    # Select player using unique ID
    players = (
        df[["player_id", "name"]]
        .drop_duplicates()
        .sort_values(["name", "player_id"])
    )

    player_options = {
        f"{row['name']} (ID: {row['player_id']})": row["player_id"]
        for _, row in players.iterrows()
    }

    selected_player = st.selectbox(
        "Select a player",
        options=list(player_options.keys()),
    )

    player_id = player_options[selected_player]

    # Select season for that player
    player_data = df[df["player_id"] == player_id]

    selected_season = st.selectbox(
        "Select a season",
        options=sorted(player_data["season"].unique(), reverse=True),
    )

    # Find exact player-season record
    record = player_data.loc[
        player_data["season"] == selected_season
    ].iloc[0]

    st.divider()
    st.header(f"{record['name']} — {selected_season}")
    st.caption(f"Player ID: {player_id}")

    # Triple-A statistics
    for group_name, stats in STAT_GROUPS.items():
        if group_name == "Historical MLB Outcomes":
            continue

        show_stat_group(group_name, stats, record)

    # MLB outcomes stay separate from Triple-A features
    if "Historical MLB Outcomes" in STAT_GROUPS:
        st.divider()
        show_stat_group(
            "Historical MLB Outcomes",
            STAT_GROUPS["Historical MLB Outcomes"],
            record,
        )
        st.caption(
            "Historical MLB results are separate from Triple-A "
            "statistics and are not model predictions."
        )

    # Future prediction feature from Issue #9
    st.divider()
    st.subheader("Future MLB Prediction")
    st.info("Prediction not available yet")

    st.caption(
        "Callup is a research project exploring how Triple-A "
        "hitting performance relates to future MLB performance."
    )


if __name__ == "__main__":
    main()

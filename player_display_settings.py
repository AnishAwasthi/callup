
# Player Profile Display Settings
# Controls which statistics appear on the Streamlit webpage.

STAT_GROUPS = {
    "Triple-A Hitting Statistics": {
        "aaa_pa": {
            "label": "Plate Appearances",
            "unit": "count",
            "description": "Total completed batting turns.",
        },
        "aaa_ab": {
            "label": "At-Bats",
            "unit": "count",
            "description": "Official at-bats, excluding walks and certain other outcomes.",
        },
        "aaa_hits": {
            "label": "Hits",
            "unit": "count",
            "description": "Times the batter reached base with a hit.",
        },
        "aaa_hr": {
            "label": "Home Runs",
            "unit": "count",
            "description": "Hits that resulted in a home run.",
        },
        "aaa_bb": {
            "label": "Walks",
            "unit": "count",
            "description": "Times the batter reached base on balls.",
        },
        "aaa_k": {
            "label": "Strikeouts",
            "unit": "count",
            "description": "Times the batter struck out.",
        },
    },

    # Additional statistics from Issue #1
    "Triple-A Hitting Rates": {
        "K_rate": {
            "label": "Strikeout Rate",
            "unit": "percentage",
            "decimals": 1,
            "description": "Percentage of plate appearances ending in a strikeout.",
        },
        "BB_rate": {
            "label": "Walk Rate",
            "unit": "percentage",
            "decimals": 1,
            "description": "Percentage of plate appearances ending in a walk.",
        },
        "swing_rate": {
            "label": "Swing Rate",
            "unit": "percentage",
            "decimals": 1,
            "description": "Percentage of observed pitches the batter swung at.",
        },
        "contact_rate": {
            "label": "Contact Rate",
            "unit": "percentage",
            "decimals": 1,
            "description": "Percentage of swings resulting in contact.",
        },
    },

    "Triple-A Observed Data": {
        "aaa_observed_pitches": {
            "label": "Observed Pitches",
            "unit": "count",
            "description": "Pitches recorded in the available dataset.",
        },
        "aaa_observed_pa": {
            "label": "Observed Plate Appearances",
            "unit": "count",
            "description": "Plate appearances found in the pitch records.",
        },
    },

    "Historical MLB Outcomes": {
        "reached_mlb": {
            "label": "Reached MLB",
            "unit": "boolean",
            "description": "Whether the player appeared in MLB during the outcome year.",
        },
        "mlb_pa": {
            "label": "MLB Plate Appearances",
            "unit": "count",
            "description": "Recorded MLB plate appearances in the outcome year.",
        },
        "mlb_woba": {
            "label": "MLB Weighted On-Base Average",
            "unit": "decimal",
            "decimals": 3,
            "description": "A batting statistic that weights different offensive outcomes.",
        },
    },
}

# Basic Hitting Statistics — Validation Notes

The script calculates plate appearances (PA), strikeout rate (K%), walk rate (BB%), swing rate, and contact rate using the 2023 and 2024 Triple-A pitch datasets.

**Validation performed:**
- Confirmed that all 926 player-season rows are included.
- Verified that all calculated statistics have no missing values.
- Confirmed that all rates fall between 0 and 1, contacts do not exceed swings, and player-season combinations are unique.
- Verified percentage calculations for Abraham Almonte, Matt Adams, Daniel Murphy, and Bo Naylor.
- Confirmed that Bo Naylor batted for the Columbus Clippers in 2023.
- Walk and total pitch counts match the reference roster for all 926 rows.

**Known discrepancies:**

The calculated PA and strikeout counts differ from the reference `aaa_pa` and `aaa_k` columns for 12 player-seasons, with a net difference of two. These discrepancies remain unresolved.

The reference `aaa_observed_pa` includes 683 truncated plate appearances. The script excludes these incomplete appearances from PA calculations, as required.

**Output:** `data/processed/features_basic.csv` (generated locally and excluded from Git).
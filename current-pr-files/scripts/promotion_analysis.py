"""Reproduce issue #5's descriptive participation tables and four plots."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from callup.contract import FEATURE_INPUTS, load

FLAGS = ["reached_mlb", "outcome_eligible", "label_available"]
STATUSES = ["not_observed", "thin", "eligible"]
LABELS = ["No MLB batting PA", "1–74 MLB PA", "75+ MLB PA"]
COLORS = ["#74869b", "#e9a23b", "#137f83"]
RATES = {"aaa_batting_average": ("aaa_hits", "aaa_ab"),
         "aaa_bb_rate": ("aaa_bb", "aaa_pa"),
         "aaa_k_rate": ("aaa_k", "aaa_pa"),
         "aaa_hr_rate": ("aaa_hr", "aaa_pa")}


def add_rates(frame):
    frame = frame.copy()
    for name, (numerator, denominator) in RATES.items():
        frame[name] = frame[numerator] / frame[denominator].where(frame[denominator].gt(0))
    return frame


def groups(frame):
    """Include empty categories; overall unique-person counts are recomputed."""
    for season, yearly in [(None, frame), *frame.groupby("season", sort=True)]:
        yield season, "all", "all", yearly
        for status in STATUSES:
            yield season, "outcome_status", status, yearly.loc[yearly.outcome_status.eq(status)]
        for flag in FLAGS:
            for value in (False, True):
                yield season, flag, str(value).lower(), yearly.loc[yearly[flag].eq(value)]


def summarize(frame):
    counts, missing, statistics = [], [], []
    numeric = [*FEATURE_INPUTS, "aaa_observed_pa", "aaa_observed_pitches", *RATES]
    fields = [c for c in frame.columns if c not in ["player_id", "season"]]
    for season, group_by, group, subset in groups(frame):
        key = {"season": season, "group_by": group_by, "group": group}
        n = len(subset)
        row = {**key, "outcome_status": group if group_by == "outcome_status" else "all",
               "n_rows": n, "n_players": subset.player_id.nunique(),
               "n_reached": int(subset.reached_mlb.sum()),
               "n_eligible": int(subset.outcome_eligible.sum()),
               "n_label_available": int(subset.label_available.sum())}
        for rate, count in [("participation_rate", "n_reached"),
                            ("eligibility_rate", "n_eligible"),
                            ("label_rate", "n_label_available")]:
            row[rate] = row[count] / n if n else None
        counts.append(row)
        for field in fields:
            n_missing = int(subset[field].isna().sum())
            missing.append({**key, "field": field, "n_missing": n_missing,
                            "n_total": n, "missing_rate": n_missing / n if n else None})
        for field in numeric:
            values = subset[field].dropna()
            statistics.append({**key, "field": field, "n_total": n,
                               "n_observed": len(values), "n_missing": n - len(values),
                               "mean": values.mean(), "median": values.median(),
                               "q25": values.quantile(.25), "q75": values.quantile(.75)})
    tables = {"participation_summary": pd.DataFrame(counts),
              "missing_values": pd.DataFrame(missing),
              "aaa_comparisons": pd.DataFrame(statistics)}
    for table in tables.values():
        table["season"] = table.season.astype("Int64")
    return tables


def check_totals(frame, report):
    actual = {"pool": len(frame), "reached": int(frame.reached_mlb.sum()),
              "eligible": int(frame.outcome_eligible.sum()),
              "labels_available_provisional": int(frame.label_available.sum()),
              "thin": int(frame.outcome_status.eq("thin").sum()),
              "not_observed": int(frame.outcome_status.eq("not_observed").sum())}
    for key, value in actual.items():
        if report[key] != value:
            raise ValueError(f"Cohort report mismatch for {key}: {value} != {report[key]}")
    if sorted(frame.season.unique().tolist()) != report["seasons"]:
        raise ValueError("Cohort seasons differ from preparation report")
    return actual


def plot(frame, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white"})
    seasons = sorted(frame.season.unique())

    def save(fig, name):
        fig.savefig(output / f"{name}.png", dpi=170, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(1, len(seasons), figsize=(12, 4.8), layout="constrained", squeeze=False, sharey=True)
    for ax, season in zip(axes[0], seasons, strict=True):
        subset = frame.loc[frame.season.eq(season)]
        values = [len(subset), *(int(subset[f].sum()) for f in FLAGS)]
        bars = ax.bar(["All AAA", "Any MLB PA", "75+ MLB PA", "Usable label"], values,
                      color=["#74869b", "#4275aa", "#137f83", "#895e9c"])
        ax.bar_label(bars, padding=4)
        ax.set_ylim(0, frame.groupby("season").size().max() * 1.18)
        ax.set_title(f"{season} AAA → {season + 1} MLB")
        ax.set_ylabel("Player-season rows")
        ax.tick_params(axis="x", labelsize=9)
    fig.suptitle("Participation, eligibility and preliminary labels\nNested groups; bars must not be added")
    save(fig, "participation_counts")

    fig, axes = plt.subplots(1, len(seasons), figsize=(12, 4.8), layout="constrained", squeeze=False, sharey=True)
    for ax, season in zip(axes[0], seasons, strict=True):
        subset = frame.loc[frame.season.eq(season)]
        samples = [subset.loc[subset.outcome_status.eq(s), "aaa_pa"] for s in STATUSES]
        boxes = ax.boxplot(samples, patch_artist=True,
                           tick_labels=[f"{label}\n(n={len(s)})" for label, s in zip(LABELS, samples, strict=True)])
        for box, color in zip(boxes["boxes"], COLORS, strict=True):
            box.set_facecolor(color)
        ax.set_title(f"{season} AAA → {season + 1} MLB")
        ax.set_ylabel("Triple-A plate appearances")
        ax.tick_params(axis="x", labelsize=9)
    fig.suptitle("Triple-A playing time by next-season MLB participation")
    save(fig, "aaa_playing_time")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    titles = ["Batting average (H / AB)", "Walk rate (BB / PA)",
              "Strikeout rate (K / PA)", "Home-run rate (HR / PA)"]
    for ax, field, title in zip(axes.flat, RATES, titles, strict=True):
        for index, (status, label, color) in enumerate(zip(STATUSES, LABELS, COLORS, strict=True)):
            values = [frame.loc[frame.season.eq(s) & frame.outcome_status.eq(status), field].median()
                      for s in seasons]
            positions = [i + (index - 1) * .24 for i in range(len(seasons))]
            ax.bar(positions, values, width=.23, color=color, label=label)
        ax.set_xticks(range(len(seasons)), seasons)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(title)
        ax.set_ylabel("Median player-season rate")
    axes[0, 0].set_ylim(0, .40)
    axes[0, 0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Triple-A hitting by next-season MLB participation\nDescriptive comparisons; no causal interpretation")
    save(fig, "aaa_hitting_rates")

    fields = [*FEATURE_INPUTS, "aaa_first_date", "aaa_last_date", "mlb_woba",
              "mlb_first_date", "mlb_last_date"]
    fig, ax = plt.subplots(figsize=(12, 7), layout="constrained")
    columns, labels = [], []
    for season in seasons:
        for status, label in zip(STATUSES, LABELS, strict=True):
            subset = frame.loc[frame.season.eq(season) & frame.outcome_status.eq(status)]
            columns.append(subset[fields].isna().mean())
            labels.append(f"{season}\n{label}\n(n={len(subset)})")
    matrix = pd.concat(columns, axis=1).to_numpy()
    heat = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(labels)), labels, fontsize=9)
    ax.set_yticks(range(len(fields)), fields)
    for i in range(len(fields)):
        for j in range(len(labels)):
            if pd.notna(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:.0%}", ha="center", va="center",
                        color="white" if matrix[i, j] > .5 else "#182737")
    fig.colorbar(heat, ax=ax, format=PercentFormatter(1), label="Missing fraction")
    ax.set_title("Missing data in the prepared hitter-season table\nOutcome absence is expected for many rows; pitch measurements are not in this table")
    save(fig, "missingness")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/shared/processed/hitter_seasons.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/cohort_preparation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/promotion")
    args = parser.parse_args()
    frame = load(args.input)
    if not frame.data_kind.eq("real").all():
        raise ValueError("Final analysis requires real study rows only")
    totals = check_totals(frame, json.loads(args.report.read_text()))
    manifest = json.loads((ROOT / "data/shared/manifest.json").read_text())
    expected_hash = manifest["files"]["processed/hitter_seasons.csv"]["sha256"]
    if sha256(args.input) != expected_hash:
        raise ValueError("Input differs from the frozen shared manifest")
    frame = add_rates(frame)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, table in summarize(frame).items():
        table.to_csv(args.output / f"{name}.csv", index=False, na_rep="")
    plot(frame, args.output)
    metadata = {"data_version": manifest["version"], "input_sha256": sha256(args.input),
                "report_sha256": sha256(args.report), "script_sha256": sha256(Path(__file__)),
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
                "python": sys.version.split()[0],
                "packages": {p: importlib.metadata.version(p) for p in ["pandas", "matplotlib", "numpy"]},
                "counts": totals, "n_unique_players": int(frame.player_id.nunique()),
                "rate_denominator": "n_rows within the indicated season/group; blank season means all seasons",
                "labels": "All wOBA labels are provisional; no independent reconciliation claimed."}
    (args.output / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

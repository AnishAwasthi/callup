"""Presentation diagnostics for the existing preliminary models; no new tuning."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from callup.contract import FEATURE_INPUTS
from callup.modeling import fit_ridge, labeled_partitions, select_features

MODEL_LABELS = {"training_average": "Training average", "ridge": "Ridge"}
DISCLAIMER = "PRELIMINARY • Frozen provisional outcomes; independent validation unresolved"


def ridge_details(frame, predictions):
    """Extract coefficients via the unchanged fitter and verify identical predictions."""
    train, test = labeled_partitions(frame)
    fitted = fit_ridge(train).best_estimator_
    ridge = predictions.loc[predictions.model.eq("ridge")].copy()
    baseline = predictions.loc[predictions.model.eq("training_average")]
    keys = ["player_id", "season", "outcome_year", "y_true"]
    expected = test[["player_id", "season", "outcome_year", "mlb_woba"]].rename(columns={"mlb_woba": "y_true"})
    for rows in (ridge, baseline):
        pd.testing.assert_frame_equal(rows[keys].reset_index(drop=True), expected.reset_index(drop=True))
    np.testing.assert_allclose(ridge.y_pred, fitted.predict(select_features(test)), rtol=0, atol=1e-12)
    ridge = ridge.merge(frame[["player_id", "season", "name"]], on=["player_id", "season"], validate="one_to_one")
    ridge["residual"] = ridge.y_true - ridge.y_pred
    coefficients = pd.DataFrame({
        "predictor": FEATURE_INPUTS,
        "standardized_coefficient": fitted.named_steps["ridge"].coef_,
        "training_mean": fitted.named_steps["scaler"].mean_,
        "training_scale": fitted.named_steps["scaler"].scale_,
        "intercept": fitted.named_steps["ridge"].intercept_,
        "alpha": fitted.named_steps["ridge"].alpha,
        "preliminary": True,
    })
    return coefficients, ridge


def residual_extremes(residuals, n=3):
    """Negative actual-minus-predicted errors are overpredictions; positive are under."""
    ordered = residuals.sort_values(["residual", "player_id", "season"])
    over = ordered.loc[ordered.residual.lt(0)].head(n).assign(direction="overprediction")
    under = ordered.loc[ordered.residual.gt(0)].tail(n).iloc[::-1].assign(direction="underprediction")
    return pd.concat([over, under], ignore_index=True)


def metric_table(metrics):
    return pd.DataFrame([
        {"model": name, **{key: entry[key] for key in ("mae", "rmse", "r2")}, "preliminary": True}
        for name, entry in metrics["models"].items()
    ])


def plot_diagnostics(predictions, residuals, coefficients, metrics, output):
    """Write meeting-ready PNG and SVG figures with explicit provisional labeling."""
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    figures = {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    low = min(predictions.y_true.min(), predictions.y_pred.min()) - .01
    high = max(predictions.y_true.max(), predictions.y_pred.max()) + .01
    for ax, (name, label), color in zip(axes, MODEL_LABELS.items(), ["#2867a0", "#d56a22"], strict=True):
        rows = predictions.loc[predictions.model.eq(name)]
        ax.scatter(rows.y_true, rows.y_pred, s=28, alpha=.65, color=color, label=f"{label} (n={len(rows)})")
        ax.plot([low, high], [low, high], "--", color="#555555", linewidth=1, label="y = x")
        ax.set(xlim=(low, high), ylim=(low, high), xlabel="Observed provisional MLB wOBA", ylabel="Predicted MLB wOBA", title=label)
        ax.set_aspect("equal", adjustable="box")
        ax.legend(fontsize=9, loc="upper left")
    fig.suptitle("PRELIMINARY — Observed versus predicted MLB wOBA")
    figures["observed_vs_predicted"] = fig

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(residuals.y_pred, residuals.residual, color="#2867a0", alpha=.65, s=30)
    ax.axhline(0, linestyle="--", color="#555555", linewidth=1)
    for direction, color in [("overprediction", "#ad3d30"), ("underprediction", "#17775b")]:
        selected = residual_extremes(residuals).query("direction == @direction")
        ax.scatter(selected.y_pred, selected.residual, color=color, s=45, label=f"Largest {direction}s")
        for offset, row in enumerate(selected.itertuples()):
            ax.annotate(str(row.player_id), (row.y_pred, row.residual),
                        xytext=(8, (-1 if direction == "overprediction" else 1) * (12 + offset * 8)),
                        textcoords="offset points", fontsize=9,
                        arrowprops={"arrowstyle": "-", "color": color})
    ax.set(xlabel="Ridge prediction (provisional MLB wOBA)",
           ylabel="Residual = observed − predicted wOBA",
           title=f"PRELIMINARY — Ridge residuals (n={len(residuals)})")
    ax.margins(x=.2, y=.3)
    ax.legend(loc="lower left", fontsize=9)
    figures["ridge_residuals"] = fig

    fig, ax = plt.subplots(figsize=(9, 5))
    values = coefficients.standardized_coefficient
    ax.barh(coefficients.predictor, values, color=["#2867a0" if v >= 0 else "#d56a22" for v in values])
    ax.axvline(0, color="#555555", linewidth=1)
    ax.invert_yaxis()
    ax.set(xlabel="Predicted wOBA change per training standard deviation",
           title=f"PRELIMINARY — Ridge standardized coefficients (alpha={coefficients.alpha.iloc[0]:g})")
    figures["ridge_coefficients"] = fig

    fig, ax = plt.subplots(figsize=(9, 3))
    ax.axis("off")
    rows = metric_table(metrics)
    cells = [[MODEL_LABELS[r.model], f"{r.mae:.8f}", f"{r.rmse:.8f}", "undefined" if pd.isna(r.r2) else f"{r.r2:.8f}"] for r in rows.itertuples()]
    table = ax.table(cellText=cells, colLabels=["Model", "MAE ↓", "RMSE ↓", "R² ↑"], loc="center", cellLoc="center")
    table.scale(1, 1.8)
    ax.set_title("PRELIMINARY — Frozen test-set comparison")
    figures["model_comparison"] = fig

    for name, fig in figures.items():
        footnote = DISCLAIMER
        if name == "ridge_coefficients":
            footnote += "\nCorrelated predictors: coefficients are conditional associations, not causal effects."
        fig.text(.5, .015, footnote, ha="center", fontsize=9, color="#555555")
        fig.tight_layout(rect=(0, .09, 1, .95))
        fig.savefig(output / f"{name}.png", dpi=180)
        fig.savefig(output / f"{name}.svg", metadata={"Date": None})
        plt.close(fig)

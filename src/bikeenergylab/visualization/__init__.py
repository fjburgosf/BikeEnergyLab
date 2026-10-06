"""Headless publication exports with SI/display units and explicit labels."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save_figure(figure: Any, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    for extension in ["png", "svg", "pdf"]:
        figure.savefig(base.with_suffix(f".{extension}"), dpi=300, bbox_inches="tight")
    plt.close(figure)


def simulation_figures(result: Any, output: Path) -> None:
    frame = result.trace
    if frame.empty:
        return
    x = frame.distance_m / 1000
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, layout="constrained")
    for axis, field, label in zip(
        axes,
        ["elevation_m", "grade", "speed_mps"],
        ["Elevation [m]", "Grade [rise/run]", "Speed [m/s]"],
    ):
        axis.plot(x, frame[field], label=label.split(" [")[0])
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
        axis.legend()
    axes[-1].set_xlabel("Distance [km]")
    fig.suptitle("Prescribed route profile")
    save_figure(fig, output / "route")
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True, layout="constrained")
    for field, label in [
        ("power_wheel_w", "Wheel demand"),
        ("power_motor_w", "Motor at wheel"),
        ("power_human_w", "Rider at wheel"),
        ("power_battery_w", "Battery"),
        ("power_unmet_w", "Unmet demand"),
    ]:
        axes[0].plot(x, frame[field], label=label)
    axes[0].set_ylabel("Power [W]")
    axes[0].legend(ncol=2)
    axes[1].plot(x, frame.soc, label="SOC")
    axes[1].axhline(result.config.battery.soc_min, color="red", linestyle="--", label="Reserve")
    axes[1].set_ylabel("SOC [fraction]")
    axes[1].legend()
    axes[2].plot(x, frame.cumulative_energy_wh, label="Net electrical energy")
    axes[2].set_ylabel("Energy [Wh]")
    axes[2].set_xlabel("Distance [km]")
    axes[2].legend()
    fig.suptitle("Energy and battery state")
    save_figure(fig, output / "simulation")
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    ax.plot(x[x > 0], (frame.cumulative_energy_wh / x)[x > 0])
    ax.set(xlabel="Distance [km]", ylabel="Cumulative electrical demand [Wh/km]")
    save_figure(fig, output / "specific_energy")
    if "CGPRA" in result.summary:
        prediction = result.summary["CGPRA"]
        fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
        center = prediction["full_route_energy_wh"]
        interval = prediction["prediction_interval_wh"]
        if interval is not None:
            ax.errorbar(
                [0],
                [center],
                yerr=[[center - interval[0]], [interval[1] - center]],
                fmt="o",
                capsize=8,
                label="CGPRA calibrated energy interval",
            )
        else:
            ax.scatter([0], [center], label="CGPRA point only")
        ax.scatter([1], [prediction["physical_full_route_demand_wh"]], label="Physical demand")
        ax.set_xticks([0, 1], ["CGPRA", "Physics"])
        ax.set_ylabel("Full-route energy [Wh]")
        ax.set_title(f"Gate α={prediction['alpha']:.3f}; OOD score={prediction['ood_score']:.3g}")
        ax.legend(fontsize=8)
        save_figure(fig, output / "hybrid_prediction")
    parts = result.summary["decomposition"]
    keys = [
        "rolling",
        "grade",
        "aero",
        "acceleration",
        "human",
        "braking",
        "drivetrain_loss",
        "motor_loss",
        "regen_loss",
        "aux",
        "unmet",
    ]
    values = [parts[f"{k}_wh"] * (-1 if k in {"human", "unmet"} else 1) for k in keys]
    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    ax.bar(keys, values, color=["#297d91" if v >= 0 else "#d68a38" for v in values])
    ax.axhline(0, color="black", linewidth=0.5)
    ax.tick_params(axis="x", rotation=35)
    ax.set_ylabel("Signed contribution [Wh]")
    ax.set_title("Electrical balance including losses and braking")
    save_figure(fig, output / "energy_balance")


def uncertainty_figures(samples: Any, output: Path, bands: Any = None) -> None:
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.hist(samples.range_km, bins=25, color="#297d91", label="Monte Carlo samples")
    ax.set_xlabel("Range on repeated route [km]")
    ax.set_ylabel("Samples [count]")
    ax.set_title("Assumption-conditional range distribution (see censoring)")
    ax.legend()
    save_figure(fig, output / "range_distribution")
    if "predictive_energy_wh" in samples:
        fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
        ax.hist(
            samples.full_route_demand_wh, bins=25, alpha=0.6, label="Physical full-route demand"
        )
        ax.hist(
            samples.predictive_energy_wh,
            bins=25,
            alpha=0.6,
            label="Hybrid + held-out signed errors",
        )
        ax.set_xlabel("Full-route electrical energy [Wh]")
        ax.set_ylabel("Samples [count]")
        ax.set_title("Conditional energy samples; not a dynamic mission guarantee")
        ax.legend()
        save_figure(fig, output / "predictive_energy")
    if bands is not None:
        fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True, layout="constrained")
        x = bands.route_fraction
        for ax, key, label in zip(
            axes[:2], ["soc", "energy_wh"], ["SOC [fraction]", "Energy [Wh]"]
        ):
            ax.plot(x, bands[f"{key}_median"], label="Median")
            ax.fill_between(
                x,
                bands[f"{key}_low95"],
                bands[f"{key}_high95"],
                alpha=0.25,
                label="Central 95%, conditional on reaching point",
            )
            ax.set_ylabel(label)
            ax.legend(fontsize=7)
        axes[2].plot(x, bands.n_reached)
        axes[2].set(
            xlabel="Normalized route progress [fraction]", ylabel="Reaching samples [count]"
        )
        save_figure(fig, output / "trajectory_bands")


def benchmark_figures(metrics: Any, predictions: Any, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    pivot = metrics[metrics.model.isin(["M1", "M2", "M3", "M4"])].pivot(
        index="scenario", columns="model", values="energy_mae_wh"
    )
    pivot.plot.bar(ax=ax)
    ax.set_ylabel("Energy MAE [Wh]")
    ax.set_xlabel("Held-out scenario")
    ax.set_title("Synthetic validation: M1–M4")
    save_figure(fig, output / "benchmark")
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    for scenario, block in predictions[predictions.model == "M4"].groupby("scenario"):
        ax.scatter(block.ood_score, block.alpha, s=10, label=scenario)
    ax.set_xlabel("Normalized support distance [unitless]")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_ylabel("Residual gate alpha [fraction]")
    ax.set_title("CGPRA support and confidence")
    ax.legend(fontsize=7, ncol=2)
    save_figure(fig, output / "confidence")


def sensitivity_figures(indices: Any, method: str, output: Path) -> None:
    column = {"sobol": "ST", "morris": "mu_star", "spearman": "spearman_rho", "oat": "elasticity"}[
        method
    ]
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    ax.barh(indices.parameter, indices[column])
    ax.set(xlabel=column, title=f"{method}: conditional sensitivity")
    save_figure(fig, output / "sensitivity")


def prequential_figures(predictions: Any, output: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, layout="constrained")
    for strategy, block in predictions[predictions.model == "M4"].groupby("strategy"):
        axes[0].plot(block.step, (block.predicted_wh - block.observed_wh).abs(), label=strategy)
        axes[1].plot(block.step, block.crr_before_update, label=strategy)
    block = predictions[predictions.model == "M4"].drop_duplicates("step")
    axes[1].plot(block.step, block.truth_crr, "k--", label="Declared synthetic truth")
    axes[0].set_ylabel("Pre-update absolute error [Wh]")
    axes[1].set(xlabel="Chronological stream step", ylabel="Crr [unitless]")
    for axis in axes:
        axis.legend()
    save_figure(fig, output / "prequential")

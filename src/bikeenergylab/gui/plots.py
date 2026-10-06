"""Translated desktop figures built from the same public result tables."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

LABELS = {
    "en": {
        "route": "Route",
        "power": "Power",
        "battery": "Battery",
        "balance": "Balance",
        "range": "Range",
        "energy": "Energy",
        "confidence": "Confidence",
        "fit": "Calibration",
        "distance": "Distance [km]",
        "elevation": "Elevation [m]",
        "grade": "Grade [rise/run]",
        "speed": "Speed [m/s]",
        "surface": "Surface",
        "wheel": "Wheel demand",
        "motor": "Motor",
        "human": "Rider",
        "electrical": "Battery",
        "unmet": "Unmet demand",
        "reserve": "Reserve",
        "cumulative": "Cumulative energy [Wh]",
        "specific": "Cumulative energy [Wh/km]",
        "count": "Samples",
        "range_axis": "Repeated-route range [km]",
        "energy_axis": "Energy [Wh]",
        "physical": "Physical",
        "predictive": "Hybrid predictive",
        "observed": "Observed [Wh]",
        "predicted": "Predicted [Wh]",
        "residual": "Observed − predicted [Wh]",
        "score": "Support distance",
        "alpha": "Residual gate α",
        "sample": "Route index",
        "rolling": "Rolling",
        "aero": "Aerodynamic",
        "acceleration": "Acceleration",
        "braking": "Braking",
        "drivetrain_loss": "Drivetrain losses",
        "motor_loss": "Motor losses",
        "regen_loss": "Regeneration losses",
        "aux": "Auxiliaries",
        "grade_part": "Slope",
        "interval": "Central 95% sample interval",
        "bands": "Uncertainty bands",
        "progress": "Normalized route progress",
        "reaching": "Reaching samples",
    },
    "es": {
        "route": "Ruta",
        "power": "Potencias",
        "battery": "Batería",
        "balance": "Balance",
        "range": "Autonomía",
        "energy": "Energía",
        "confidence": "Confianza",
        "fit": "Calibración",
        "distance": "Distancia [km]",
        "elevation": "Elevación [m]",
        "grade": "Pendiente [rise/run]",
        "speed": "Velocidad [m/s]",
        "surface": "Superficie",
        "wheel": "Demanda en rueda",
        "motor": "Motor",
        "human": "Ciclista",
        "electrical": "Batería",
        "unmet": "Demanda no cubierta",
        "reserve": "Reserva",
        "cumulative": "Energía acumulada [Wh]",
        "specific": "Energía acumulada [Wh/km]",
        "count": "Muestras",
        "range_axis": "Autonomía repitiendo ruta [km]",
        "energy_axis": "Energía [Wh]",
        "physical": "Física",
        "predictive": "Predictiva híbrida",
        "observed": "Observada [Wh]",
        "predicted": "Predicha [Wh]",
        "residual": "Observada − predicha [Wh]",
        "score": "Distancia al soporte",
        "alpha": "Compuerta residual α",
        "sample": "Índice de ruta",
        "rolling": "Rodadura",
        "aero": "Aerodinámica",
        "acceleration": "Aceleración",
        "braking": "Frenado",
        "drivetrain_loss": "Pérdidas transmisión",
        "motor_loss": "Pérdidas motor",
        "regen_loss": "Pérdidas regeneración",
        "aux": "Auxiliares",
        "grade_part": "Pendiente",
        "interval": "Intervalo central del 95% de las muestras",
        "bands": "Bandas de incertidumbre",
        "progress": "Progreso normalizado de ruta",
        "reaching": "Muestras que alcanzan el punto",
    },
}


def route_figure(route, language="es") -> Figure:
    labels, frame = LABELS[language], route.frame
    figure = Figure(figsize=(7, 6), layout="constrained")
    axes = figure.subplots(4, 1, sharex=True)
    for axis, key, label in zip(
        axes[:3], ["elevation_m", "grade", "speed_mps"], ["elevation", "grade", "speed"]
    ):
        axis.plot(frame.distance_m / 1000, frame[key])
        axis.set_ylabel(labels[label])
        axis.grid(alpha=0.2)
    surfaces = list(dict.fromkeys(frame.surface))
    axes[3].step(frame.distance_m / 1000, [surfaces.index(s) for s in frame.surface], where="post")
    axes[3].set_yticks(range(len(surfaces)), surfaces)
    axes[3].set_ylabel(labels["surface"])
    axes[3].set_xlabel(labels["distance"])
    return figure


def result_figures(result, language="es") -> list[tuple[str, Figure]]:
    labels, figures = LABELS[language], []
    if hasattr(result, "trace") and len(result.trace):
        frame = result.trace
        x = frame.distance_m / 1000
        figures.append((labels["route"], route_figure(result.route, language)))
        figure = Figure(figsize=(7, 4), layout="constrained")
        axis = figure.subplots()
        for field, key in [
            ("power_wheel_w", "wheel"),
            ("power_motor_w", "motor"),
            ("power_human_w", "human"),
            ("power_battery_w", "electrical"),
            ("power_unmet_w", "unmet"),
        ]:
            axis.plot(x, frame[field], label=labels[key])
        axis.set(xlabel=labels["distance"], ylabel="W")
        axis.legend(ncol=2)
        figures.append((labels["power"], figure))
        figure = Figure(figsize=(7, 6), layout="constrained")
        axes = figure.subplots(3, 1, sharex=True)
        axes[0].plot(x, frame.soc)
        axes[0].axhline(
            result.config.battery.soc_min, color="red", linestyle="--", label=labels["reserve"]
        )
        axes[0].set_ylabel("SOC")
        axes[0].legend()
        axes[1].plot(x, frame.cumulative_energy_wh)
        axes[1].set_ylabel(labels["cumulative"])
        axes[2].plot(
            x, np.divide(frame.cumulative_energy_wh, x, out=np.full(len(x), np.nan), where=x > 0)
        )
        axes[2].set(xlabel=labels["distance"], ylabel=labels["specific"])
        figures.append((labels["battery"], figure))
        figure = Figure(figsize=(7, 5), layout="constrained")
        axis = figure.subplots()
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
        parts = result.summary["decomposition"]
        values = [parts[f"{k}_wh"] * (-1 if k in {"human", "unmet"} else 1) for k in keys]
        axis.barh([labels["grade_part" if k == "grade" else k] for k in keys], values)
        axis.axvline(0, color="black", linewidth=0.5)
        axis.set_xlabel("Wh")
        figures.append((labels["balance"], figure))
        if "CGPRA" in result.summary:
            prediction = result.summary["CGPRA"]
            figure = Figure(figsize=(7, 4), layout="constrained")
            axis = figure.subplots()
            center, interval = (
                prediction["full_route_energy_wh"],
                prediction["prediction_interval_wh"],
            )
            axis.scatter([0, 1], [prediction["physical_full_route_demand_wh"], center])
            if interval is not None:
                axis.errorbar(
                    [1],
                    [center],
                    yerr=[[center - interval[0]], [interval[1] - center]],
                    fmt="none",
                    capsize=8,
                )
            axis.set_xticks([0, 1], [labels["physical"], "CGPRA"])
            axis.set_ylabel(labels["energy_axis"])
            axis.set_title(f"α={prediction['alpha']:.3f}; OOD={prediction['ood_score']:.3g}")
            figures.append((labels["confidence"], figure))
    if hasattr(result, "samples"):
        samples = result.samples
        for title, column in [("range", "range_km"), ("energy", "full_route_demand_wh")]:
            figure = Figure(figsize=(7, 4), layout="constrained")
            axis = figure.subplots()
            axis.hist(samples[column], bins=20, alpha=0.6, label=labels["physical"])
            if title == "energy" and "predictive_energy_wh" in samples:
                axis.hist(
                    samples.predictive_energy_wh, bins=20, alpha=0.6, label=labels["predictive"]
                )
            lo, hi = np.quantile(samples[column], [0.025, 0.975])
            axis.axvspan(lo, hi, alpha=0.1, color="green", label=labels["interval"])
            axis.set(
                xlabel=labels["range_axis" if title == "range" else "energy_axis"],
                ylabel=labels["count"],
            )
            axis.legend(fontsize=8)
            figures.append((labels[title], figure))
        if "alpha" in samples:
            figure = Figure(figsize=(7, 4), layout="constrained")
            axis = figure.subplots()
            axis.scatter(samples.ood_score, samples.alpha, s=12)
            axis.set(xlabel=labels["score"], ylabel=labels["alpha"], xscale="symlog")
            figures.append((labels["confidence"], figure))
    if getattr(result, "trajectory_bands", None) is not None:
        bands = result.trajectory_bands
        figure = Figure(figsize=(7, 6), layout="constrained")
        axes = figure.subplots(3, 1, sharex=True)
        for axis, key, label in zip(axes[:2], ["soc", "energy_wh"], ["SOC", labels["energy_axis"]]):
            axis.plot(bands.route_fraction, bands[f"{key}_median"])
            axis.fill_between(
                bands.route_fraction, bands[f"{key}_low95"], bands[f"{key}_high95"], alpha=0.25
            )
            axis.set_ylabel(label)
        axes[2].plot(bands.route_fraction, bands.n_reached)
        axes[2].set(xlabel=labels["progress"], ylabel=labels["reaching"])
        figures.append((labels["bands"], figure))
    summary = result.summary if hasattr(result, "summary") else result
    if isinstance(summary, dict) and "observed_energy_wh" in summary:
        observed = np.asarray(summary["observed_energy_wh"])
        predicted = np.asarray(summary["fitted_energy_wh"])
        figure = Figure(figsize=(7, 5), layout="constrained")
        axes = figure.subplots(1, 2)
        axes[0].scatter(observed, predicted, s=12)
        limits = [min(observed.min(), predicted.min()), max(observed.max(), predicted.max())]
        axes[0].plot(limits, limits, "k--")
        axes[0].set(xlabel=labels["observed"], ylabel=labels["predicted"])
        axes[1].scatter(predicted, observed - predicted, s=12)
        axes[1].axhline(0, color="black")
        axes[1].set(xlabel=labels["predicted"], ylabel=labels["residual"])
        figures.append((labels["fit"], figure))
    if isinstance(summary, dict) and "diagnostic_alpha" in summary:
        figure = Figure(figsize=(7, 4), layout="constrained")
        axis = figure.subplots()
        axis.scatter(summary["diagnostic_ood_score"], summary["diagnostic_alpha"], s=15)
        axis.set(xlabel=labels["score"], ylabel=labels["alpha"], xscale="symlog")
        figures.append((labels["confidence"], figure))
    if hasattr(result, "tables") and "sensitivity" in result.tables:
        indices = result.tables["sensitivity"]
        column = {
            "sobol": "ST",
            "morris": "mu_star",
            "spearman": "spearman_rho",
            "oat": "elasticity",
        }[summary["method"]]
        figure = Figure(figsize=(7, 5), layout="constrained")
        axis = figure.subplots()
        axis.barh(indices.parameter, indices[column])
        axis.set_xlabel(column)
        figures.append((summary["method"], figure))
    if isinstance(summary, dict) and "benchmark_directory" in summary:
        from pathlib import Path

        directory = Path(summary["benchmark_directory"])
        metrics = pd.read_csv(directory / "metrics.csv")
        predictions = pd.read_csv(directory / "predictions.csv")
        pivot = metrics[metrics.model.isin(["M1", "M2", "M3", "M4"])].pivot(
            index="scenario", columns="model", values="energy_mae_wh"
        )
        figure = Figure(figsize=(8, 5), layout="constrained")
        axis = figure.subplots()
        positions = np.arange(len(pivot))
        for index, model in enumerate(pivot):
            axis.bar(positions + (index - 1.5) * 0.2, pivot[model], width=0.2, label=model)
        axis.set_xticks(positions, pivot.index, rotation=30)
        axis.set_ylabel("MAE [Wh]")
        axis.legend()
        figures.append(("M1–M4", figure))
        figure = Figure(figsize=(7, 4), layout="constrained")
        axis = figure.subplots()
        for scenario, block in predictions[predictions.model == "M4"].groupby("scenario"):
            axis.scatter(block.ood_score, block.alpha, s=10, label=scenario)
        axis.set(xlabel=labels["score"], ylabel=labels["alpha"], xscale="symlog")
        axis.legend(fontsize=7)
        figures.append((labels["confidence"], figure))
    return figures

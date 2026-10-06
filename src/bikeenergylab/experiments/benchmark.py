"""Leakage-free ID/OOD baselines, gate comparison, ablations and interval calibration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bikeenergylab import Config
from bikeenergylab.io import create_run, write_json
from bikeenergylab.metrics import interval_metrics, point_metrics
from bikeenergylab.residual import CGPRAModel

from .synthetic import SCENARIOS, generate_observations, serialize_observations


def run_benchmark(
    config: Config | None = None,
    output: str | Path = "results",
    n_train: int = 100,
    n_calibration: int = 40,
    n_test: int = 25,
    figures: bool = True,
) -> Path:
    cfg = config or Config()
    seed = int(cfg.experiment.get("seed", 42))
    cfg = Config.from_dict(cfg.to_dict())
    cfg.experiment.update(n_train=n_train, n_calibration=n_calibration, n_test=n_test)
    train = generate_observations(n_train, seed, prefix="train")
    heldout = generate_observations(n_calibration, seed + 1, prefix="interval")
    fitted = CGPRAModel(cfg, seed).fit(train)
    fitted.calibrate_intervals(heldout)
    simple = CGPRAModel(cfg, seed, gate_strategy="simple").fit(train)
    no_calibration = CGPRAModel(cfg, seed, calibrate_physics=False).fit(train)
    simple.calibrate_intervals(heldout)
    no_calibration.calibrate_intervals(heldout)
    variants = {
        "M1": (fitted, "M1", True),
        "M2": (fitted, "M2", True),
        "M3": (fitted, "M3", True),
        "M4": (fitted, "M4", True),
        "M4-simple": (simple, "M4", True),
        "without-calibration": (no_calibration, "M4", True),
        "without-uncertainty-gate": (fitted, "M4", False),
    }
    metrics, predictions, curves = [], [], []
    inputs = {
        "training": serialize_observations(train),
        "interval_calibration": serialize_observations(heldout),
    }
    for scenario_index, scenario in enumerate(SCENARIOS):
        test = generate_observations(
            n_test, seed + 100 + scenario_index, scenario=scenario, prefix="test"
        )
        if {o.group for o in test} & (fitted.training_groups | fitted.interval_groups):
            raise RuntimeError("Train/calibration/test route group overlap")
        inputs[f"test_{scenario}"] = serialize_observations(test)
        observed = np.array([o.energy_wh for o in test])
        km = np.array([o.route.distance_m / 1000 for o in test])
        for label, (model, baseline, uncertainty_gate) in variants.items():
            # The no-uncertainty variant needs its own held-out quantile.
            if not uncertainty_gate:
                held_prediction = model.predict(heldout, baseline, use_uncertainty_gate=False)
                held_km = np.array([o.route.distance_m / 1000 for o in heldout])
                scores = np.sort(
                    np.abs(np.array([o.energy_wh for o in heldout]) - held_prediction.energy_wh)
                    / held_km
                )
                rank = int(np.ceil((len(scores) + 1) * 0.95))
                if rank > len(scores):
                    raise ValueError("Insufficient interval calibration routes")
                pred = model.predict(test, baseline, use_uncertainty_gate=False)
                pred.lower_wh, pred.upper_wh = (
                    pred.energy_wh - scores[rank - 1] * km,
                    pred.energy_wh + scores[rank - 1] * km,
                )
            else:
                pred = model.predict(test, baseline, coverage=0.95)
            point = point_metrics(observed, pred.energy_wh)
            intervals = interval_metrics(observed, pred.lower_wh, pred.upper_wh)
            capacity = cfg.battery.nominal_energy_wh * cfg.battery.usable_fraction
            rate = pred.energy_wh / km
            true_rate = observed / km
            available = capacity * (cfg.battery.initial_soc - cfg.battery.soc_min)
            admissible = (rate > 1e-6) & (true_rate > 1e-6)
            range_errors = np.abs(available / rate[admissible] - available / true_rate[admissible])
            metrics.append(
                {
                    "scenario": scenario,
                    "model": label,
                    "n": len(test),
                    "energy_mae_wh": point["mae"],
                    "energy_rmse_wh": point["rmse"],
                    "energy_r2": point["r2"],
                    "wh_per_km_mae": float(np.abs(rate - true_rate).mean()),
                    "soc_mae": float(np.abs(pred.energy_wh - observed).mean() / capacity),
                    "stationary_range_mae_km": float(range_errors.mean())
                    if len(range_errors)
                    else None,
                    "stationary_range_relative_error": float(
                        np.mean(range_errors / (available / true_rate[admissible]))
                    )
                    if len(range_errors)
                    else None,
                    "coverage95": intervals["coverage"],
                    "interval_width_wh": intervals["interval_width"],
                    "mean_alpha": float(pred.alpha.mean()),
                    "mean_ood_score": float(pred.ood_score.mean()),
                }
            )
            for i, obs in enumerate(test):
                predictions.append(
                    {
                        "route_id": obs.group,
                        "scenario": scenario,
                        "model": label,
                        "observed_energy_wh": obs.energy_wh,
                        "predicted_energy_wh": pred.energy_wh[i],
                        "residual_wh": obs.energy_wh - pred.energy_wh[i],
                        "alpha": pred.alpha[i],
                        "ood_score": pred.ood_score[i],
                        "lower95_wh": pred.lower_wh[i],
                        "upper95_wh": pred.upper_wh[i],
                    }
                )
            if uncertainty_gate:
                for nominal in (0.8, 0.95):
                    interval = model.predict(test, baseline, coverage=nominal)
                    empirical = interval_metrics(observed, interval.lower_wh, interval.upper_wh)
                    curves.append(
                        {
                            "scenario": scenario,
                            "model": label,
                            "nominal_coverage": nominal,
                            **empirical,
                        }
                    )
    destination = create_run(output, cfg, inputs)
    metrics_frame, predictions_frame = pd.DataFrame(metrics), pd.DataFrame(predictions)
    metrics_frame.to_csv(destination / "metrics.csv", index=False)
    predictions_frame.to_csv(destination / "predictions.csv", index=False)
    pd.DataFrame(curves).to_csv(destination / "calibration_curves.csv", index=False)
    write_json(destination / "calibration.json", fitted.calibration_result.to_dict())
    write_json(
        destination / "protocol.json",
        {
            "training_seed": seed,
            "interval_seed": seed + 1,
            "test_seeds": list(range(seed + 100, seed + 108)),
            "train_routes": n_train,
            "interval_routes": n_calibration,
            "test_routes_per_scenario": n_test,
            "synthetic_truth": {"bike.crr": 0.008, "bike.cda_m2": 0.48},
            "structural_residual_wh_per_km": "0.7+0.10*(speed-5)+0.015*(temperature-20)^2",
            "sensor_noise_sd_wh_per_km": 0.12,
            "gates": ["simple kNN", "advanced kNN+shrinkage Mahalanobis+tree spread"],
            "ablations": {
                "without_gating": "M3",
                "without_residual": "M1",
                "without_calibration": "without-calibration",
                "without_predictive_uncertainty_in_gate": "without-uncertainty-gate",
            },
            "range_metric": "stationary-equivalent range from Wh/km, not route depletion distance",
            "caution": "Synthetic only; single-seed default; OOD interval coverage is empirical and not guaranteed",
        },
    )
    # Honest per-scenario report, including negative findings.
    pivot = metrics_frame[metrics_frame.model.isin(["M1", "M2", "M3", "M4"])].pivot(
        index="scenario", columns="model", values="energy_mae_wh"
    )
    lines = [
        "# Synthetic benchmark",
        "",
        "Results conditional on declared generator; no real-world validation.",
        "",
    ]
    for scenario, row in pivot.iterrows():
        best = row.idxmin()
        lines.append(
            f"- {scenario}: lowest Energy MAE = {best} ({row[best]:.3f} Wh); M4 = {row['M4']:.3f} Wh."
        )
    lines.extend(
        [
            "",
            "CGPRA superiority is not assumed. Consult metrics.csv for all ablations and interval coverage.",
        ]
    )
    (destination / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (destination / "logs" / "run.log").write_text(
        "Independent route groups; train and interval calibration precede test evaluation.\n",
        encoding="utf-8",
    )
    if figures:
        from bikeenergylab.visualization import benchmark_figures

        benchmark_figures(metrics_frame, predictions_frame, destination / "figures")
    return destination

"""EXP-01–15 controlled sweeps and scientific workflows."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.calibration import calibrate
from bikeenergylab.io import create_run, write_json
from bikeenergylab.uncertainty import monte_carlo

from .benchmark import run_benchmark
from .synthetic import generate_observations


def run_suite(config: Config, output: str | Path = "results") -> Path:
    seed = int(config.experiment.get("seed", 42))
    base = config.changed("rider.human_power_w", 40)
    route = Route.synthetic(5000, 6, segments=20)
    rows = []
    sweeps = [
        ("EXP-01", "route.speed_mps", np.linspace(3, 9, 13)),
        ("EXP-02", "route.grade", np.linspace(-0.06, 0.06, 13)),
        ("EXP-03", "rider.mass_kg", np.linspace(50, 110, 13)),
        ("EXP-04", "environment.wind_mps", np.linspace(-5, 5, 13)),
        ("EXP-05", "rider.human_power_w", np.linspace(0, 200, 13)),
        ("EXP-06", "motor.assist_level", np.linspace(0, 1, 11)),
        ("EXP-07", "environment.temperature_c", np.linspace(-5, 40, 10)),
    ]
    for experiment, parameter, values in sweeps:
        for value in values:
            cfg, sample_route = base, route
            if parameter == "route.speed_mps":
                sample_route = Route.synthetic(5000, float(value), segments=20)
            elif parameter == "route.grade":
                sample_route = Route.synthetic(5000, 6, grade=float(value), segments=20)
            else:
                cfg = cfg.changed(parameter, float(value))
            cfg = cfg.changed("simulation.timestep_s", 30)
            result = BikeModel(cfg).simulate(sample_route)
            rows.append(
                {
                    "experiment": experiment,
                    "parameter": parameter,
                    "value": value,
                    "energy_wh": result.summary["energy_wh"],
                    "wh_per_km": result.summary["wh_per_km"],
                    "feasible": result.summary["feasible"],
                    "stationary_equivalent_range_km": result.summary[
                        "stationary_equivalent_range_km"
                    ],
                }
            )
    destination = create_run(output, config, {"route": route.frame})
    frame = pd.DataFrame(rows)
    frame.to_csv(destination / "sweeps.csv", index=False)
    from bikeenergylab.uncertainty.sensitivity import one_at_a_time

    one_at_a_time(base, route).to_csv(destination / "local_sensitivity.csv", index=False)
    truth_data = generate_observations(
        40, seed, discrepancy=False, noise_std_wh_per_km=0, prefix="identification"
    )
    fit = calibrate(config, truth_data)
    write_json(destination / "EXP-08-calibration.json", fit.to_dict())
    benchmark = run_benchmark(config, destination / "model_comparisons")
    uncertainty = monte_carlo(
        base,
        route,
        n_samples=40,
        seed=seed,
        distributions={"environment.wind_mps": {"distribution": "normal", "mean": 0, "std": 1}},
        reserve_soc=0.15,
        max_distance_km=200,
    )
    uncertainty_path = uncertainty.export(destination / "probabilistic")
    write_json(
        destination / "experiment_index.json",
        {
            "EXP-01–07": "sweeps.csv",
            "EXP-07-scope": "air density only unless empirical battery/motor temperature coefficients are supplied",
            "EXP-08": "EXP-08-calibration.json",
            "EXP-09": str(benchmark.relative_to(destination)) + "/metrics.csv (M1/M2)",
            "EXP-10": str(benchmark.relative_to(destination)) + "/metrics.csv (M1/M3)",
            "EXP-11": str(benchmark.relative_to(destination)) + "/metrics.csv (M4)",
            "EXP-12": str(benchmark.relative_to(destination)) + "/metrics.csv (OOD-Route)",
            "EXP-13": str(benchmark.relative_to(destination)) + "/metrics.csv (OOD-Combined)",
            "EXP-14": str(uncertainty_path.relative_to(destination)) + "/distributions.csv",
            "EXP-15": str(uncertainty_path.relative_to(destination)) + "/summary.json",
        },
    )
    import matplotlib.pyplot as plt

    from bikeenergylab.visualization import save_figure

    for experiment, block in frame.groupby("experiment", sort=False):
        fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
        ax.plot(block.value, block.wh_per_km, marker="o", label="Prescribed-profile consumption")
        failed = block[~block.feasible]
        if len(failed):
            ax.scatter(
                failed.value, failed.wh_per_km, color="red", marker="x", label="Profile infeasible"
            )
        ax.set_xlabel(block.parameter.iloc[0])
        ax.set_ylabel("Electrical consumption [Wh/km]")
        ax.set_title(experiment + " controlled sweep")
        ax.legend()
        save_figure(fig, destination / "figures" / experiment)
    return destination

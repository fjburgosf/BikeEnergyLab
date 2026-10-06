"""Execute all eleven examples: python examples/run_examples.py."""

from pathlib import Path

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.calibration import calibrate
from bikeenergylab.experiments import generate_observations, run_benchmark
from bikeenergylab.experiments.synthetic import serialize_observations
from bikeenergylab.io import create_run, write_json
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.uncertainty import monte_carlo


def run(output: str = "results/examples") -> dict[str, str]:
    base = Config().changed("rider.human_power_w", 50)
    route = Route.synthetic(3000, 6, segments=30)
    outputs = {}
    physical = [
        ("example_01_flat_route", base, route),
        ("example_02_hilly_route", base, Route.synthetic(3000, 5, grade=0.03, segments=30)),
        ("example_03_headwind", base.changed("environment.wind_mps", -3), route),
        ("example_04_rider_power", base.changed("rider.human_power_w", 120), route),
        ("example_05_temperature", base.changed("environment.temperature_c", 0), route),
    ]
    for name, cfg, sample in physical:
        outputs[name] = str(BikeModel(cfg).simulate(sample).export(Path(output) / name))
    data = generate_observations(
        40, seed=44, discrepancy=False, noise_std_wh_per_km=0, prefix="recovery"
    )
    fit = calibrate(Config(), data)
    fit.config.experiment["seed"] = 44
    target = create_run(
        Path(output) / "example_06_parameter_calibration",
        fit.config,
        {"dataset": serialize_observations(data)},
    )
    write_json(target / "recovered.json", fit.to_dict())
    outputs["example_06_parameter_calibration"] = str(target)
    mc = monte_carlo(
        base,
        route,
        n_samples=30,
        seed=42,
        distributions={"environment.wind_mps": {"distribution": "normal", "mean": 0, "std": 1}},
        max_distance_km=200,
    )
    outputs["example_07_uncertainty"] = str(mc.export(Path(output) / "example_07_uncertainty"))
    outputs["example_08_physics_vs_data"] = str(
        run_benchmark(
            Config(),
            Path(output) / "example_08_physics_vs_data",
            n_train=60,
            n_calibration=25,
            n_test=12,
        )
    )
    train = generate_observations(60, seed=45, prefix="hybrid-train")
    interval = generate_observations(25, seed=46, prefix="hybrid-interval")
    model = CGPRAModel(seed=45).fit(train)
    model.calibrate_intervals(interval)
    for name, scenario in [("example_09_cgpra", "ID"), ("example_10_unseen_route", "OOD-Route")]:
        test = generate_observations(12, seed=47, scenario=scenario, prefix=name)
        pred = model.predict(test, coverage=0.95)
        model.config.experiment = {"name": name, "seed": 45, "interval_seed": 46, "test_seed": 47}
        target = create_run(
            Path(output) / name,
            model.config,
            {
                "training": serialize_observations(train),
                "interval_calibration": serialize_observations(interval),
                "test": serialize_observations(test),
            },
        )
        write_json(
            target / "predictions.json",
            {
                "energy_wh": pred.energy_wh,
                "alpha": pred.alpha,
                "ood_score": pred.ood_score,
                "lower95_wh": pred.lower_wh,
                "upper95_wh": pred.upper_wh,
            },
        )
        outputs[name] = str(target)
    mission_config = base.changed("battery.initial_soc", 0.38)
    mission_route = Route.synthetic(26000, 6, segments=100)
    mission = monte_carlo(
        mission_config,
        mission_route,
        n_samples=30,
        seed=48,
        reserve_soc=0.15,
        distributions={"environment.wind_mps": {"distribution": "normal", "mean": 0, "std": 1}},
        max_distance_km=200,
    )
    outputs["example_11_mission_probability"] = str(
        mission.export(Path(output) / "example_11_mission_probability")
    )
    write_json(Path(output) / "index.json", outputs)
    return outputs


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("Examples completed: %s", run())

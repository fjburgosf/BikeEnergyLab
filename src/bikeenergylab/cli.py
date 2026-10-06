"""Offline scientific command line entrypoint."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from . import BikeModel, Config, __version__
from .io import quality_report, write_json
from .routes import route_from_config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bikeenergylab")
    parser.add_argument("--version", action="version", version=f"BikeEnergyLab {__version__}")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in [
        "simulate",
        "uncertainty",
        "benchmark",
        "experiments",
        "predict",
        "predictive-validation",
        "sensitivity",
        "prequential",
    ]:
        command = commands.add_parser(name)
        command.add_argument("config", type=Path)
        command.add_argument("--output", type=Path, default=Path("results"))
        command.add_argument("--no-figures", action="store_true")
        if name in {"simulate", "uncertainty", "predict"}:
            command.add_argument("--model", type=Path, required=name == "predict")
        if name == "predict":
            command.add_argument("--point-only", action="store_true")
        if name == "sensitivity":
            command.add_argument(
                "--method", choices=["oat", "spearman", "morris", "sobol"], default="sobol"
            )
            command.add_argument("--samples", type=int, default=256)
    adapt = commands.add_parser("adapt")
    adapt.add_argument("model", type=Path)
    adapt.add_argument("dataset", type=Path)
    adapt.add_argument("--calibration-dataset", type=Path)
    adapt.add_argument("--output", type=Path, default=Path("results"))
    telemetry = commands.add_parser("telemetry")
    telemetry.add_argument("dataset", type=Path)
    telemetry.add_argument("--config", type=Path)
    telemetry.add_argument("--smoothing-window", type=int, default=5)
    telemetry.add_argument("--output", type=Path, default=Path("results"))
    train = commands.add_parser("train")
    train.add_argument("dataset", type=Path)
    train.add_argument("--calibration-dataset", type=Path)
    train.add_argument("--holdout-routes", type=int, default=20)
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--config", type=Path)
    train.add_argument("--output", type=Path, default=Path("results"))
    fit = commands.add_parser("calibrate")
    fit.add_argument("dataset", type=Path)
    fit.add_argument("--config", type=Path)
    fit.add_argument("--output", type=Path, default=Path("results"))
    quality = commands.add_parser("quality")
    quality.add_argument("dataset", type=Path)
    quality.add_argument("--output", type=Path, default=Path("results/quality.json"))
    gui = commands.add_parser("gui")
    gui.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("bikeenergylab.cli")
    try:
        if args.command == "gui":
            from .gui.app import main as gui_main

            return gui_main(smoke_test=args.smoke_test)
        if args.command == "quality":
            import pandas as pd

            report = quality_report(pd.read_csv(args.dataset))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, report)
            logger.info("Quality report: %s", args.output)
            return 0 if report["valid"] else 2
        if args.command == "telemetry":
            from .experiments.synthetic import serialize_observations
            from .io.report import ReportResult
            from .io.telemetry import load_telemetry

            cfg = Config.from_yaml(args.config) if args.config else Config()
            observations, report = load_telemetry(args.dataset, cfg, args.smoothing_window)
            destination = ReportResult(
                report, cfg, {"observations": serialize_observations(observations)}
            ).export(args.output)
            logger.info("Converted telemetry: %s", destination)
            return 0
        if args.command == "adapt":
            from .experiments.synthetic import observations_from_csv, serialize_observations
            from .io.report import ReportResult
            from .residual import CGPRAModel

            model = CGPRAModel.load(args.model)
            observations = observations_from_csv(str(args.dataset), model.config)
            updates = [model.adapt(o) for o in observations]
            tables = {"adaptation": serialize_observations(observations)}
            if args.calibration_dataset:
                held = observations_from_csv(str(args.calibration_dataset), model.config)
                model.calibrate_intervals(held)
                tables["interval_calibration"] = serialize_observations(held)
            destination = ReportResult(
                {
                    "updates": updates,
                    "intervals_available": bool(model.quantiles),
                    "interval_routes": len(model.interval_groups),
                },
                model.config,
                tables,
                model,
            ).export(args.output)
            logger.info("Adapted reusable model: %s", destination / "model")
            return 0
        if args.command == "train":
            import numpy as np

            from .experiments.synthetic import observations_from_csv, serialize_observations
            from .io import create_run
            from .residual import CGPRAModel

            cfg = Config.from_yaml(args.config) if args.config else Config()
            cfg.experiment["seed"] = args.seed
            observations = observations_from_csv(str(args.dataset), cfg)
            if args.calibration_dataset:
                held_out = observations_from_csv(str(args.calibration_dataset), cfg)
            else:
                if args.holdout_routes < 19 or len(observations) - args.holdout_routes < 20:
                    raise ValueError("Automatic split needs >=20 training and >=19 held-out routes")
                order = np.random.default_rng(args.seed).permutation(len(observations))
                held_out = [observations[i] for i in order[-args.holdout_routes :]]
                observations = [observations[i] for i in order[: -args.holdout_routes]]
            model = CGPRAModel(cfg, seed=args.seed).fit(observations)
            model.calibrate_intervals(held_out)
            destination = create_run(
                args.output,
                model.config,
                {
                    "training": serialize_observations(observations),
                    "calibration": serialize_observations(held_out),
                },
            )
            artifact = model.save(destination / "model")
            write_json(
                destination / "training.json",
                {
                    "training_groups": sorted(model.training_groups),
                    "held_out_groups": sorted(model.interval_groups),
                    "seed": args.seed,
                    "split": "independent supplied files"
                    if args.calibration_dataset
                    else "seeded group permutation",
                    "calibration": model.calibration_result.to_dict(),
                },
            )
            logger.info("Reusable CGPRA model: %s", artifact)
            return 0
        if args.command == "calibrate":
            from .calibration import calibrate
            from .experiments.synthetic import observations_from_csv, serialize_observations
            from .io import create_run

            cfg = Config.from_yaml(args.config) if args.config else Config()
            observations = observations_from_csv(str(args.dataset), cfg)
            result = calibrate(cfg, observations)
            destination = create_run(
                args.output,
                result.config,
                {"calibration_dataset": serialize_observations(observations)},
            )
            write_json(destination / "calibration.json", result.to_dict())
            logger.info("Calibration: %s; output: %s", result.parameters, destination)
            return 0 if result.success else 2
        cfg = Config.from_yaml(args.config)
        hybrid = None
        if args.command in {"simulate", "uncertainty", "predict"}:
            from .calibration import transfer_parameters
            from .residual import CGPRAModel

            artifact = args.model or cfg.uncertainty.get("model_artifact")
            if artifact:
                artifact = Path(artifact)
                if args.model is None and not artifact.is_absolute():
                    artifact = args.config.resolve().parent / artifact
                hybrid = CGPRAModel.load(artifact)
                if args.model is not None:
                    cfg = transfer_parameters(cfg, hybrid.config, hybrid.parameter_names)
        if args.command == "sensitivity":
            from .io.report import ReportResult
            from .uncertainty.global_sensitivity import physical_sensitivity
            from .uncertainty.sensitivity import one_at_a_time

            route = route_from_config(cfg)
            if args.method == "oat":
                result = ReportResult(
                    {"method": "oat", "scope": "local full-route electrical demand"},
                    cfg,
                    {"route": route.frame, "sensitivity": one_at_a_time(cfg, route)},
                )
                destination = result.export(args.output, figures=not args.no_figures)
            else:
                options = dict(cfg.experiment.get("sensitivity", {}))
                result = physical_sensitivity(
                    cfg,
                    route,
                    args.method,
                    n=args.samples,
                    seed=cfg.experiment.get("seed", 42),
                    **options,
                )
                destination = result.export(cfg, route, args.output, figures=not args.no_figures)
        elif args.command == "prequential":
            from .experiments.adaptive import run_prequential

            destination = run_prequential(
                cfg,
                args.output,
                seed=cfg.experiment.get("seed", 42),
                n_train=cfg.experiment.get("n_train", 40),
                n_stream=cfg.experiment.get("n_stream", 32),
                figures=not args.no_figures,
            )
        elif args.command == "predictive-validation":
            from .experiments.predictive import run_predictive_validation

            options = cfg.experiment
            destination = run_predictive_validation(
                cfg,
                args.output,
                seeds=tuple(options.get("seeds", [42, 73, 109])),
                n_train=options.get("n_train", 60),
                n_calibration=options.get("n_calibration", 30),
                n_test=options.get("n_test", 15),
                figures=not args.no_figures,
            )
        elif args.command == "benchmark":
            from .experiments import run_benchmark

            options = cfg.experiment
            destination = run_benchmark(
                cfg,
                args.output,
                n_train=options.get("n_train", 100),
                n_calibration=options.get("n_calibration", 40),
                n_test=options.get("n_test", 25),
                figures=not args.no_figures,
            )
        elif args.command == "experiments":
            from .experiments.suite import run_suite

            destination = run_suite(cfg, args.output)
        else:
            route = route_from_config(cfg)
            if args.command == "simulate":
                result = BikeModel(cfg).simulate(route)
                if hybrid is not None:
                    hybrid.annotate_simulation(result)
                destination = result.export(args.output, figures=not args.no_figures)
                logger.info(
                    "Energy %.3f Wh; final SOC %.4f; feasible=%s",
                    result.summary["energy_wh"],
                    result.summary["final_soc"],
                    result.summary["feasible"],
                )
            elif args.command == "predict":
                import pandas as pd

                from .calibration import Observation
                from .io import create_run

                observation = Observation(route, 0, cfg, "prediction")
                rows = []
                for baseline in ["M1", "M2", "M3", "M4"]:
                    prediction = hybrid.predict(
                        [observation], baseline, coverage=None if args.point_only else 0.95
                    )
                    rows.append(
                        {
                            "model": baseline,
                            "full_route_energy_wh": prediction.energy_wh[0],
                            "alpha": prediction.alpha[0],
                            "ood_score": prediction.ood_score[0],
                            "lower95_wh": prediction.lower_wh[0]
                            if prediction.lower_wh is not None
                            else None,
                            "upper95_wh": prediction.upper_wh[0]
                            if prediction.upper_wh is not None
                            else None,
                        }
                    )
                destination = create_run(
                    args.output, cfg, {"route": route.frame, "predictions": pd.DataFrame(rows)}
                )
                hybrid.save(destination / "hybrid_model")
                write_json(
                    destination / "summary.json",
                    {
                        "predictions": rows,
                        "scope": "requested full-route electrical energy, before battery state constraints",
                        "interval_assumption": "Independent exchangeable calibration routes; no OOD coverage guarantee",
                    },
                )
            else:
                from .uncertainty import monte_carlo

                options = dict(cfg.uncertainty)
                options.pop("model_artifact", None)
                options.setdefault("seed", cfg.experiment.get("seed", 42))
                result = monte_carlo(cfg, route, hybrid_model=hybrid, **options)
                destination = result.export(args.output, figures=not args.no_figures)
                logger.info("Mission probability: %.3f", result.summary["mission_probability"])
        logger.info("Results: %s", destination)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        logger.error("%s", error)
        if args.log_level == "DEBUG":
            logger.exception("Diagnostic traceback")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

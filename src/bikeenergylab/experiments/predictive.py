"""Independent synthetic validation of empirical energy distributions and budgets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from bikeenergylab import Config
from bikeenergylab.io import create_run, write_json
from bikeenergylab.metrics import empirical_crps, interval_metrics, point_metrics
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.visualization import save_figure

from .synthetic import SCENARIOS, generate_observations, serialize_observations


def run_predictive_validation(
    config: Config | None = None,
    output: str | Path = "results",
    seeds: tuple[int, ...] = (42, 73, 109),
    n_train: int = 60,
    n_calibration: int = 30,
    n_test: int = 15,
    figures: bool = True,
) -> Path:
    """Use the entire equally weighted held-out error pool, not conformal bands.

    Budgets = (0.85, 1, 1.15)*M1 energy, declared before looking at test labels.
    Outcomes concern net electrical energy only. Neither battery/power trajectories
    nor uncertainty about observed synthetic labels are inferred by this test.
    """
    if not seeds or len(set(seeds)) != len(seeds) or n_test < 1:
        raise ValueError("Provide distinct seeds and a positive test size")
    cfg = Config.from_dict((config or Config()).to_dict())
    cfg.experiment.update(
        seed=seeds[0],
        seeds=list(seeds),
        n_train=n_train,
        n_calibration=n_calibration,
        n_test=n_test,
    )
    destination = create_run(output, cfg, {})
    metrics, predictions, budget_rows = [], [], []
    for seed in seeds:
        train = generate_observations(n_train, seed, prefix=f"train-{seed}")
        held = generate_observations(n_calibration, seed + 1, prefix=f"held-{seed}")
        model = CGPRAModel(cfg, seed=seed).fit(train)
        model.calibrate_intervals(held)
        seed_path = destination / f"seed-{seed}"
        seed_path.mkdir()
        model.save(seed_path / "model")
        for index, scenario in enumerate(SCENARIOS):
            test = generate_observations(
                n_test, seed + 100 + index, scenario=scenario, prefix=f"test-{seed}"
            )
            serialize_observations(test).to_csv(seed_path / f"test-{scenario}.csv", index=False)
            observed = np.array([o.energy_wh for o in test])
            km = np.array([o.route.distance_m / 1000 for o in test])
            physical = model.physical(test)
            for baseline in ["M1", "M2", "M3", "M4"]:
                prediction = model.predict(test, baseline)
                errors = model.signed_errors_wh_per_km[baseline]
                samples = prediction.energy_wh[:, None] + km[:, None] * errors[None, :]
                lower, upper = np.quantile(samples, [0.025, 0.975], axis=1)
                point = point_metrics(observed, prediction.energy_wh)
                intervals = interval_metrics(observed, lower, upper)
                crps = [empirical_crps(draws, truth) for draws, truth in zip(samples, observed)]
                auxiliary = np.array(
                    [
                        o.config.simulation.auxiliary_power_w * o.route.frame.dt_s.sum() / 3600
                        for o in test
                    ]
                )
                brier = []
                for i, observation in enumerate(test):
                    predictions.append(
                        {
                            "seed": seed,
                            "scenario": scenario,
                            "model": baseline,
                            "group": observation.group,
                            "observed_wh": observed[i],
                            "center_wh": prediction.energy_wh[i],
                            "lower95_wh": lower[i],
                            "upper95_wh": upper[i],
                            "crps_wh": crps[i],
                            "alpha": prediction.alpha[i],
                            "ood_score": prediction.ood_score[i],
                        }
                    )
                    for ratio in [0.85, 1.0, 1.15]:
                        budget = ratio * physical[i]
                        probability = float((samples[i] <= budget).mean())
                        outcome = bool(observed[i] <= budget)
                        score = (probability - outcome) ** 2
                        brier.append(score)
                        budget_rows.append(
                            {
                                "seed": seed,
                                "scenario": scenario,
                                "model": baseline,
                                "group": observation.group,
                                "budget_ratio": ratio,
                                "budget_wh": budget,
                                "probability": probability,
                                "observed_energy_budget_success": outcome,
                                "brier": score,
                            }
                        )
                metrics.append(
                    {
                        "seed": seed,
                        "scenario": scenario,
                        "model": baseline,
                        "mae_wh": point["mae"],
                        "rmse_wh": point["rmse"],
                        "crps_wh": float(np.mean(crps)),
                        "empirical_coverage95": intervals["coverage"],
                        "empirical_width95_wh": intervals["interval_width"],
                        "energy_budget_brier": float(np.mean(brier)),
                        "mean_alpha": float(prediction.alpha.mean()),
                        "outside_support_fraction": float((prediction.ood_score > 1).mean()),
                        "negative_energy_fraction": float((samples < 0).mean()),
                        "below_auxiliary_energy_fraction": float(
                            (samples < auxiliary[:, None]).mean()
                        ),
                    }
                )
    metric_frame = pd.DataFrame(metrics)
    prediction_frame = pd.DataFrame(predictions)
    budget_frame = pd.DataFrame(budget_rows)
    metric_frame.to_csv(destination / "metrics.csv", index=False)
    prediction_frame.to_csv(destination / "predictions.csv", index=False)
    budget_frame.to_csv(destination / "energy_budgets.csv", index=False)
    measures = ["mae_wh", "crps_wh", "empirical_coverage95", "energy_budget_brier"]
    aggregate = metric_frame.groupby(["scenario", "model"])[measures].agg(["mean", "std"])
    aggregate.columns = [f"{name}_{statistic}" for name, statistic in aggregate.columns]
    aggregate.reset_index().to_csv(destination / "aggregate.csv", index=False)
    reliability = []
    # Route-budget pairs are correlated within a route; these bins are descriptive,
    # and are never treated as independent replicates for significance testing.
    for (scenario, baseline), block in budget_frame.groupby(["scenario", "model"]):
        bins = np.minimum((block.probability.to_numpy() * 10).astype(int), 9)
        for bin_id in np.unique(bins):
            chosen = block.iloc[np.flatnonzero(bins == bin_id)]
            reliability.append(
                {
                    "scenario": scenario,
                    "model": baseline,
                    "bin": int(bin_id),
                    "n_route_budget_pairs": len(chosen),
                    "mean_probability": chosen.probability.mean(),
                    "observed_fraction": chosen.observed_energy_budget_success.mean(),
                }
            )
    pd.DataFrame(reliability).to_csv(destination / "reliability.csv", index=False)
    metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
    metadata["input_sha256"] = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.glob("seed-*/*/*.csv"))
        + sorted(destination.glob("seed-*/test-*.csv"))
    }
    write_json(destination / "metadata.json", metadata)
    write_json(
        destination / "protocol.json",
        {
            "kind": "synthetic empirical predictive-energy validation",
            "seeds": seeds,
            "n_train": n_train,
            "n_calibration": n_calibration,
            "n_test": n_test,
            "baselines": ["M1", "M2", "M3", "M4"],
            "scenarios": SCENARIOS,
            "energy_distribution": "Predicted route energy + entire uncentered held-out signed Wh/km error pool times test distance",
            "test_budgets": "0.85, 1.00, 1.15 times calibrated physical energy; fixed independently of observed test energy",
            "interpretation": "Conditional aggregate electrical energy; budget success is not dynamic mission completion",
            "coverage": "Empirical central 95% quantiles, distinct from split-conformal sets; no distribution-free guarantee",
            "limitations": "Synthetic mechanism only; transportable independent errors assumed; correlated budgets; no real-world probability validation",
            "discrepancy_wh_per_km": "0.7 + 0.10*(speed-5) + 0.015*(temperature-20)^2",
            "noise_sd_wh_per_km": 0.12,
        },
    )
    average = metric_frame.groupby(["scenario", "model"])[measures].mean().reset_index()
    report = [
        "# Synthetic predictive-energy validation",
        "",
        "Independent training/held-out/test routes. Equal-weight empirical signed-error distributions.",
        "Central 95% intervals have no guaranteed OOD coverage. Budgets concern aggregate electrical energy, not dynamic mission completion.",
        "",
        "| Scenario | Model | CRPS Wh | Coverage 95% | Budget Brier |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in average.itertuples():
        report.append(
            f"| {row.scenario} | {row.model} | {row.crps_wh:.3f} | {row.empirical_coverage95:.3f} | {row.energy_budget_brier:.3f} |"
        )
    report.extend(
        [
            "",
            "All values are means across the declared seeds. Per-seed metrics and standard deviations are retained.",
            "Raw energy samples are not clipped; negative/below-auxiliary fractions are reported in metrics.csv.",
            "Reliability route-budget pairs are correlated. No real-world calibration, statistical significance or universal superiority is established.",
        ]
    )
    (destination / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    if figures:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
        for axis, measure, label in zip(
            axes, ["crps_wh", "empirical_coverage95"], ["CRPS [Wh]", "Measured coverage [fraction]"]
        ):
            pivot = metric_frame.groupby(["scenario", "model"])[measure].mean().unstack()
            pivot.plot.bar(ax=axis)
            axis.set_ylabel(label)
            axis.set_xlabel("Synthetic held-out scenario")
            if measure == "empirical_coverage95":
                axis.axhline(0.95, linestyle="--", color="black", label="Nominal 95%")
                axis.set_ylim(0, 1.05)
                axis.legend(fontsize=8)
        fig.suptitle(
            "Empirical energy distributions: three independent seeds"
            if len(seeds) == 3
            else "Empirical energy distributions"
        )
        save_figure(fig, destination / "figures" / "predictive_validation")
    (destination / "logs" / "run.log").write_text(
        "Independent train/held-out/test predictive-energy validation completed\n", encoding="utf-8"
    )
    return destination

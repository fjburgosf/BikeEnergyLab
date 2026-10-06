"""Causal predict-then-update evaluation on explicitly synthetic physical drift."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from bikeenergylab import BikeModel, Config
from bikeenergylab.calibration import Observation
from bikeenergylab.io import create_run, write_json
from bikeenergylab.metrics import point_metrics
from bikeenergylab.residual import CGPRAModel

from .synthetic import generate_observations, serialize_observations


def prequential_evaluate(model: CGPRAModel, observations: list[Observation]):
    """Predict each complete route before admitting its target to adaptive training."""
    groups = {o.group for o in observations}
    if (
        not observations
        or len(groups) != len(observations)
        or groups
        & (model.training_groups | model.interval_groups | model.invalidated_interval_groups)
    ):
        raise ValueError("Prequential routes must be new independent groups in chronological order")
    adaptive, frozen = deepcopy(model), deepcopy(model)
    records = []
    for index, observation in enumerate(observations):
        for strategy, predictor in [("frozen", frozen), ("adaptive", adaptive)]:
            for baseline in ["M1", "M3", "M4"]:
                prediction = predictor.predict([observation], baseline)
                records.append(
                    {
                        "step": index,
                        "route_id": observation.group,
                        "strategy": strategy,
                        "model": baseline,
                        "observed_wh": observation.energy_wh,
                        "predicted_wh": float(prediction.energy_wh[0]),
                        "alpha": float(prediction.alpha[0]),
                        "ood_score": float(prediction.ood_score[0]),
                        "crr_before_update": predictor.config.bike.crr,
                        "cda_before_update_m2": predictor.config.bike.cda_m2,
                    }
                )
        adaptive.adapt(observation)
    return pd.DataFrame(records), adaptive


def run_prequential(
    config: Config | None = None,
    output: str | Path = "results",
    n_train: int = 40,
    n_stream: int = 32,
    seed: int = 42,
    figures: bool = True,
) -> Path:
    if n_train < 10 or n_stream < 2:
        raise ValueError("Prequential evaluation requires >=10 training and >=2 stream routes")
    cfg = Config.from_dict((config or Config()).to_dict())
    cfg.experiment.update(seed=seed, n_train=n_train, n_stream=n_stream)
    train = generate_observations(
        n_train, seed, discrepancy=False, noise_std_wh_per_km=0.06, prefix="drift-training"
    )
    stream = generate_observations(
        n_stream, seed + 1, discrepancy=False, noise_std_wh_per_km=0, prefix="drift-stream"
    )
    truth_crr = np.linspace(0.008, 0.011, n_stream)
    rng = np.random.default_rng(seed + 2)
    for observation, crr in zip(stream, truth_crr):
        truth = observation.config.changed("bike.crr", float(crr)).changed("bike.cda_m2", 0.48)
        observation.energy_wh = BikeModel(truth).predict_energy(observation.route) + (
            observation.route.distance_m / 1000 * rng.normal(0, 0.06)
        )
        observation.route.provenance.update(
            truth_crr=float(crr), truth_cda_m2=0.48, drift="linear Crr by stream order; synthetic"
        )
    model = CGPRAModel(cfg, seed=seed).fit(train)
    predictions, adaptive = prequential_evaluate(model, stream)
    predictions["truth_crr"] = predictions.step.map(dict(enumerate(truth_crr)))
    metrics = []
    for (strategy, baseline), block in predictions.groupby(["strategy", "model"]):
        metrics.append(
            {
                "strategy": strategy,
                "model": baseline,
                **point_metrics(block.observed_wh, block.predicted_wh),
            }
        )
    destination = create_run(
        output,
        cfg,
        {
            "training": serialize_observations(train),
            "stream": serialize_observations(stream),
            "predictions": predictions,
            "metrics": pd.DataFrame(metrics),
        },
    )
    model.save(destination / "initial_model")
    adaptive.save(destination / "adapted_model")
    write_json(
        destination / "protocol.json",
        {
            "source": "synthetic",
            "seed": seed,
            "training_seed": seed,
            "stream_seed": seed + 1,
            "noise_seed": seed + 2,
            "noise_std_wh_per_km": 0.06,
            "truth": {"crr_start": 0.008, "crr_end": 0.011, "cda_m2": 0.48},
            "order": "file group order; all predictions precede ingestion of that route target",
            "comparators": "identical initial model; frozen versus bounded RLS and residual retraining",
            "intervals": "point evaluation; fresh independent interval calibration needed after adaptation",
            "limitations": "controlled synthetic drift; no measured adaptation accuracy or superiority claim",
        },
    )
    if figures:
        from bikeenergylab.visualization import prequential_figures

        prequential_figures(predictions, destination / "figures")
    return destination

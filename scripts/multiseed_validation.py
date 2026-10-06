"""Repeat the synthetic protocol across independent seeds and aggregate paired errors."""

import logging
from pathlib import Path

import pandas as pd

from bikeenergylab import Config
from bikeenergylab.experiments import run_benchmark
from bikeenergylab.io import write_json


def run(output: Path = Path("results/multiseed")) -> None:
    paths, tables = [], []
    for seed in [42, 73, 109]:
        cfg = Config()
        cfg.experiment = {
            "name": "multiseed_synthetic",
            "seed": seed,
            "n_train": 60,
            "n_calibration": 30,
            "n_test": 15,
        }
        path = run_benchmark(cfg, output, n_train=60, n_calibration=30, n_test=15, figures=False)
        table = pd.read_csv(path / "metrics.csv")
        table["seed"] = seed
        tables.append(table)
        paths.append(path.name)
    combined = pd.concat(tables, ignore_index=True)
    combined.to_csv(output / "all_metrics.csv", index=False)
    combined.groupby(["scenario", "model"])[["energy_mae_wh", "energy_rmse_wh", "coverage95"]].agg(
        ["mean", "std"]
    ).to_csv(output / "aggregate.csv")
    write_json(
        output / "protocol.json",
        {
            "seeds": [42, 73, 109],
            "runs": paths,
            "scope": "Three synthetic repetitions; mean/SD over seeds, not statistical proof of superiority",
        },
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

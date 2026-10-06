"""Portable, inspectable model replay from CSV/JSON, without executable serialization."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from bikeenergylab import Config, __version__
from bikeenergylab.calibration import SequentialCalibrator
from bikeenergylab.experiments.synthetic import observations_from_csv, serialize_observations
from bikeenergylab.io import write_json

from . import FEATURE_NAMES, CGPRAModel

FORMAT = "bikeenergylab-cgpra-replay-v1"


def _inside(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Model artifact path must stay inside its directory")
    return path


def _reference(model: CGPRAModel) -> dict[str, Any]:
    observations = model.observations + model.interval_observations
    result = {}
    for baseline in ["M1", "M2", "M3", "M4"]:
        prediction = model.predict(observations, baseline)
        result[baseline] = np.column_stack(
            [
                prediction.energy_wh,
                prediction.alpha,
                prediction.ood_score,
                prediction.residual_std_wh,
            ]
        ).tolist()
    result["quantiles"] = [
        [name, coverage, value] for (name, coverage), value in sorted(model.quantiles.items())
    ]
    return result


def save_model(model: CGPRAModel, directory: str | Path) -> Path:
    if not model.fitted:
        raise ValueError("Fit before saving a model")
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)

    def portable(values: dict[str, Any]) -> dict[str, Any]:
        # Only the actual observation routes are model inputs. Configuration route
        # selectors and uncertainty settings belong to the inference request.
        values["route"], values["uncertainty"] = {}, {}
        asset = values["motor"].get("efficiency_map")
        if asset:
            content = Path(asset).read_bytes()
            name = f"assets/{hashlib.sha256(content).hexdigest()}.csv"
            target = root / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
            values["motor"]["efficiency_map"] = name
        return values

    def save_observations(observations: list[Any], name: str) -> None:
        frame = serialize_observations(observations)
        # Map files are retained for every known per-route configuration too.
        frame["known_config_json"] = frame.known_config_json.map(
            lambda value: json.dumps(portable(json.loads(value)), sort_keys=True)
        )
        frame.to_csv(root / name, index=False)

    save_observations(model.observations, "training.csv")
    if model.interval_observations:
        save_observations(model.interval_observations, "calibration.csv")
    values = portable(model.config.to_dict())
    write_json(root / "reference_predictions.json", _reference(model))
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    sequential = None
    if hasattr(model, "sequential"):
        sequential = {
            "forgetting_factor": model.sequential.forgetting,
            "observation_variance_wh2": model.sequential.noise,
            "covariance": model.sequential.covariance.tolist(),
            "updates": model.sequential.updates,
        }
    write_json(
        root / "manifest.json",
        {
            "format": FORMAT,
            "software_version": __version__,
            "dependencies": {
                name: importlib.metadata.version(name)
                for name in ["numpy", "scipy", "pandas", "scikit-learn"]
            },
            "feature_names": FEATURE_NAMES,
            "seed": model.seed,
            "gate_strategy": model.gate.strategy,
            "calibrate_physics": model.calibrate_physics,
            "parameter_names": model.parameter_names,
            "config": values,
            "coverages": sorted({coverage for _, coverage in model.quantiles}),
            "files_sha256": files,
            "sequential": sequential,
            "calibration_diagnostics": (
                model.calibration_result.to_dict()
                if model.calibration_result is not None
                else getattr(model, "calibration_diagnostics", None)
            ),
            "invalidated_interval_groups": sorted(model.invalidated_interval_groups),
            "interpretation": "Deterministic replay at saved physical parameters; predictions verified after load",
        },
    )
    return root


def load_model(directory: str | Path) -> CGPRAModel:
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format"] != FORMAT or manifest["feature_names"] != FEATURE_NAMES:
        raise ValueError("Unsupported model format or feature schema")
    files = manifest["files_sha256"]
    if not {"training.csv", "reference_predictions.json"}.issubset(files):
        raise ValueError("Model artifact is missing required replay inputs")
    for name, digest in files.items():
        if hashlib.sha256(_inside(root, name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Model artifact checksum mismatch: {name}")
    # Validate JSON paths before loading CSV configurations or invoking a model.
    configurations = [manifest["config"]]
    import pandas as pd

    for name in ["training.csv", "calibration.csv"]:
        if name in files:
            frame = pd.read_csv(root / name, usecols=["known_config_json"])
            configurations.extend(json.loads(value) for value in frame.known_config_json.unique())
    for values in configurations:
        asset = values["motor"].get("efficiency_map")
        if asset and (asset not in files or not _inside(root, asset).is_file()):
            raise ValueError("Motor map must be an included, checksummed model asset")
    values = manifest["config"]
    if values["motor"].get("efficiency_map"):
        values["motor"]["efficiency_map"] = str(_inside(root, values["motor"]["efficiency_map"]))
    model = CGPRAModel(
        Config.from_dict(values),
        manifest["seed"],
        manifest["gate_strategy"],
        calibrate_physics=False,
    )
    if manifest["parameter_names"] != model.parameter_names:
        raise ValueError("Unsupported physical calibration parameter schema")
    model.fit(observations_from_csv(str(root / "training.csv")))
    model.calibrate_physics = manifest["calibrate_physics"]
    model.calibration_diagnostics = manifest.get("calibration_diagnostics")
    model.invalidated_interval_groups = set(manifest["invalidated_interval_groups"])
    if "calibration.csv" in files:
        model.calibrate_intervals(
            observations_from_csv(str(root / "calibration.csv")), tuple(manifest["coverages"])
        )
    reference = json.loads((root / "reference_predictions.json").read_text(encoding="utf-8"))
    reconstructed = _reference(model)
    for baseline in ["M1", "M2", "M3", "M4"]:
        expected, actual = np.asarray(reference[baseline]), np.asarray(reconstructed[baseline])
        if expected.shape != actual.shape or not np.allclose(
            expected, actual, rtol=1e-8, atol=1e-8
        ):
            raise ValueError(
                "Model replay differs from reference predictions; use the recorded environment"
            )
    if reference["quantiles"] != reconstructed["quantiles"]:
        old = np.array([row[2] for row in reference["quantiles"]])
        new = np.array([row[2] for row in reconstructed["quantiles"]])
        if old.shape != new.shape or not np.allclose(old, new, rtol=1e-8, atol=1e-8):
            raise ValueError("Replayed interval calibration differs from model artifact")
    if manifest["sequential"]:
        controls = manifest["sequential"]
        model.sequential = SequentialCalibrator(
            model.config,
            model.parameter_names,
            controls["forgetting_factor"],
            controls["observation_variance_wh2"],
        )
        covariance = np.array(controls["covariance"], dtype=float)
        if (
            covariance.shape != (len(model.parameter_names), len(model.parameter_names))
            or not np.isfinite(covariance).all()
            or not np.allclose(covariance, covariance.T)
            or np.linalg.eigvalsh(covariance).min() < -1e-12
        ):
            raise ValueError("Invalid saved sequential covariance")
        model.sequential.covariance = covariance
        model.sequential.updates = int(controls["updates"])
    return model

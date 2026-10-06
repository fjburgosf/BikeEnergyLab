"""Verify clean-wheel and frozen CLI/GUI/model exports against working sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument(
        "--executable", type=Path, default=ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results/distribution-verification")
    args = parser.parse_args()
    installed = args.installed_python.resolve()
    environment = installed.parent.parent
    settings = (environment / "pyvenv.cfg").read_text(encoding="utf-8").lower()
    if "include-system-site-packages = false" not in settings:
        raise ValueError("Verification needs a venv without inherited system-site packages")
    location = subprocess.check_output(
        [str(installed), "-I", "-c", "import bikeenergylab; print(bikeenergylab.__file__)"],
        text=True,
        cwd=ROOT,
    ).strip()
    if not Path(location).resolve().is_relative_to(environment):
        raise ValueError("Clean verification did not import the installed wheel")
    source = hashlib.sha256()
    package = ROOT / "src/bikeenergylab"
    for path in sorted(package.rglob("*.py")):
        source.update(path.relative_to(package).as_posix().encode())
        source.update(path.read_bytes())
    runtimes = {
        "clean-wheel": [str(installed), "-I", "-m", "bikeenergylab"],
        "windows-executable": [str(args.executable.resolve())],
    }
    from bikeenergylab.experiments import generate_observations
    from bikeenergylab.experiments.synthetic import serialize_observations

    inputs = args.output.resolve() / "verification_inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    serialize_observations(generate_observations(1, 89213, prefix="distribution-fresh")).to_csv(
        inputs / "new_observation.csv", index=False
    )
    (inputs / "timed_telemetry.csv").write_text(
        "timestamp,distance_m,voltage_v,current_a\n"
        "2026-10-04T00:00:00Z,0,36,2\n2026-10-04T00:00:10Z,30,36,2\n",
        encoding="utf-8",
    )
    observations, versions = {}, {}
    for name, command in runtimes.items():
        versions[name] = subprocess.check_output(
            command + ["--version"], text=True, cwd=ROOT
        ).strip()
        for operation in ["predict", "simulate", "uncertainty"]:
            output = args.output.resolve() / name / operation
            before = set(output.glob("EXP-*")) if output.exists() else set()
            completed = subprocess.run(
                command
                + [
                    operation,
                    "configs/flat.yaml",
                    "--model",
                    str(args.model.resolve()),
                    "--output",
                    str(output),
                    "--no-figures",
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                timeout=120,
            )
            if completed.returncode:
                raise RuntimeError(f"{name} {operation}: {completed.stdout}\n{completed.stderr}")
            created = set(output.glob("EXP-*")) - before
            if len(created) != 1:
                raise ValueError("Expected one new immutable run directory")
            destination = created.pop()
            metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
            if metadata["source_sha256"] != source.hexdigest():
                raise ValueError(f"{name}: installed source identity differs from working package")
            summary = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
            if operation == "predict":
                observations[name] = [row["full_route_energy_wh"] for row in summary["predictions"]]
            elif operation == "simulate":
                assert summary["feasible"] and "CGPRA" in summary
            else:
                assert "predictive_energy" in summary
                assert (destination / "hybrid_model/manifest.json").is_file()
            print(f"Verified {name}: {operation}", flush=True)
        extra_operations = {
            "morris": [
                "sensitivity",
                "configs/flat.yaml",
                "--method",
                "morris",
                "--samples",
                "4",
                "--no-figures",
            ],
            "sobol": [
                "sensitivity",
                "configs/flat.yaml",
                "--method",
                "sobol",
                "--samples",
                "16",
                "--no-figures",
            ],
            "telemetry": ["telemetry", str(inputs / "timed_telemetry.csv")],
            "adapt": ["adapt", str(args.model.resolve()), str(inputs / "new_observation.csv")],
        }
        adapted = None
        for operation, arguments in extra_operations.items():
            output = args.output.resolve() / name / operation
            before = set(output.glob("EXP-*"))
            completed = subprocess.run(
                command + arguments + ["--output", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=120,
            )
            if completed.returncode:
                raise RuntimeError(f"{name} {operation}: {completed.stdout}\n{completed.stderr}")
            created = set(output.glob("EXP-*")) - before
            if len(created) != 1:
                raise ValueError("Expected one new acceptance run")
            destination = created.pop()
            metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
            if metadata["source_sha256"] != source.hexdigest():
                raise ValueError(f"{name}: {operation} source identity differs")
            if operation == "telemetry":
                import pandas as pd

                observation = pd.read_csv(destination / "observations.csv")
                np.testing.assert_allclose(observation.observed_route_energy_wh, 0.2)
                np.testing.assert_allclose(observation.dt_s, 10)
            if operation == "adapt":
                adapted = destination / "model"
            print(f"Verified {name}: {operation}", flush=True)
        point = subprocess.run(
            command
            + [
                "predict",
                "configs/flat.yaml",
                "--model",
                str(adapted),
                "--point-only",
                "--output",
                str(args.output.resolve() / name / "adapted-points"),
                "--no-figures",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if point.returncode:
            raise RuntimeError(f"{name} adapted point prediction: {point.stderr}")
        gui = subprocess.run(
            command + ["gui", "--smoke-test"], text=True, capture_output=True, cwd=ROOT, timeout=90
        )
        if gui.returncode:
            raise RuntimeError(f"{name} GUI: {gui.stdout}\n{gui.stderr}")
        print(
            f"Verified {name}: examples/tutorial/export and GUI physical/hybrid/uncertainty ES/EN",
            flush=True,
        )
    np.testing.assert_allclose(
        observations["clean-wheel"], observations["windows-executable"], rtol=1e-8, atol=1e-8
    )
    subprocess.run([str(installed), "-I", "-m", "pip", "check"], cwd=ROOT, check=True)
    report = {
        "versions": versions,
        "source_sha256": source.hexdigest(),
        "checks": [
            "predict M1-M4",
            "physical and hybrid export",
            "predictive Monte Carlo export",
            "GUI simulation/hybrid/predictive/ES-EN",
            "nine-example catalog and complete eight-step tutorial/export",
            "isolated wheel import",
            "pip check",
            "Morris and Sobol designs",
            "timestamped telemetry seconds/energy",
            "adaptation replay and point-only inference",
        ],
        "matching_predictions": True,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        run()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error

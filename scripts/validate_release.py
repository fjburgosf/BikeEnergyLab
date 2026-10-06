"""Execute the documented software/scientific acceptance protocols and retain logs."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bikeenergylab import __version__

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-core", action="store_true", help="Use only when unit/lint/GUI checks were just run"
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Run software checks without new scientific protocols",
    )
    args = parser.parse_args()
    if args.skip_core and args.core_only:
        parser.error("--skip-core and --core-only cannot be combined")
    output = ROOT / f"results/release-{__version__}"
    logs = ROOT / "results/build_logs"
    logs.mkdir(exist_ok=True)
    operations = []
    if not args.skip_core:
        operations += [
            ("lint", ["-m", "ruff", "check", "src", "tests", "scripts"]),
            ("format", ["-m", "ruff", "format", "--check", "src", "tests", "scripts"]),
            ("tests", ["-m", "pytest", "-q"]),
            ("gui", ["-m", "bikeenergylab", "gui", "--smoke-test"]),
        ]
    operations += [
        (
            "examples",
            ["-c", f"from examples.run_examples import run; run({str(output / 'examples')!r})"],
        ),
        (
            "suite",
            [
                "-m",
                "bikeenergylab",
                "experiments",
                "configs/benchmark.yaml",
                "--output",
                str(output / "suite"),
            ],
        ),
        (
            "predictive",
            [
                "-m",
                "bikeenergylab",
                "predictive-validation",
                "configs/predictive_validation.yaml",
                "--output",
                str(output / "predictive"),
            ],
        ),
        (
            "prequential",
            [
                "-m",
                "bikeenergylab",
                "prequential",
                "configs/adaptive_validation.yaml",
                "--output",
                str(output / "prequential"),
            ],
        ),
        (
            "telemetry",
            [
                "-m",
                "bikeenergylab",
                "telemetry",
                "datasets/telemetry_example.csv",
                "--output",
                str(output / "telemetry"),
            ],
        ),
    ]
    for method in ["oat", "spearman", "morris", "sobol"]:
        operations.append(
            (
                f"sensitivity-{method}",
                [
                    "-m",
                    "bikeenergylab",
                    "sensitivity",
                    "configs/flat.yaml",
                    "--method",
                    method,
                    "--samples",
                    "16" if method == "morris" else "256",
                    "--output",
                    str(output / "sensitivity" / method),
                ],
            )
        )
    if args.core_only:
        operations = [
            (name, command)
            for name, command in operations
            if name in {"lint", "format", "tests", "gui"}
        ]
    results = []
    for name, command in operations:
        print(f"Running {name}…", flush=True)
        log = logs / f"{name}-v{__version__}.log"
        with log.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(
                [sys.executable, *command], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT
            )
        results.append(
            {
                "check": name,
                "exit_code": completed.returncode,
                "log": log.relative_to(ROOT).as_posix(),
                "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            }
        )
        if completed.returncode:
            print(log.read_text(encoding="utf-8")[-5000:])
            raise RuntimeError(f"Acceptance check failed: {name}")
        print(f"Passed {name}", flush=True)
    digest = hashlib.sha256()
    package = ROOT / "src/bikeenergylab"
    for path in sorted(package.rglob("*.py")):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    output.mkdir(exist_ok=True)
    (output / "acceptance.json").write_text(
        json.dumps(
            {
                "version": __version__,
                "completed_utc": datetime.now(timezone.utc).isoformat(),
                "source_sha256": digest.hexdigest(),
                "checks": results,
                "scope": (
                    "software acceptance; historical scientific protocols retained"
                    if args.core_only
                    else "numerical and synthetic acceptance; no field performance claim"
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Acceptance record: {output / 'acceptance.json'}", flush=True)


if __name__ == "__main__":
    main()

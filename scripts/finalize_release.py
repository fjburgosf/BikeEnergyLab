"""Finalize the historical 1.0.0 full-science release; UI updates use record_ui_release.py."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-only", action="store_true")
    args = parser.parse_args()
    source = hashlib.sha256()
    package = ROOT / "src/bikeenergylab"
    for path in sorted(package.rglob("*.py")):
        source.update(path.relative_to(package).as_posix().encode())
        source.update(path.read_bytes())
    identity = source.hexdigest()
    acceptance = json.loads((ROOT / "results/release-1.0.0/acceptance.json").read_text())
    verification_path = ROOT / "results/distribution-verification-1.0.0/verification.json"
    verification = json.loads(verification_path.read_text())
    if acceptance["source_sha256"] != identity or any(c["exit_code"] for c in acceptance["checks"]):
        raise ValueError("Acceptance evidence does not match final working sources")
    if verification["source_sha256"] != identity or not verification["matching_predictions"]:
        raise ValueError("Distribution evidence does not match final working sources")
    tests = int(
        re.search(
            r"(\d+) passed", (ROOT / "results/build_logs/tests-v1.0.0.log").read_text()
        ).group(1)
    )

    def latest(kind):
        for path in reversed(sorted((ROOT / "results/release-1.0.0" / kind).glob("EXP-*"))):
            metadata = json.loads((path / "metadata.json").read_text())
            if metadata["source_sha256"] == identity:
                return path
        raise ValueError(f"Missing final-source {kind} evidence")

    predictive, prequential, suite = latest("predictive"), latest("prequential"), latest("suite")
    predictive_metadata = json.loads((predictive / "metadata.json").read_text())
    aggregate = pd.read_csv(predictive / "aggregate.csv")
    id_m4 = aggregate[(aggregate.scenario == "ID") & (aggregate.model == "M4")].iloc[0]
    drift = pd.read_csv(prequential / "metrics.csv")
    adaptive_mae = drift[(drift.strategy == "adaptive") & (drift.model == "M4")].mae.iloc[0]
    frozen_mae = drift[(drift.strategy == "frozen") & (drift.model == "M4")].mae.iloc[0]
    if not args.record_only:
        summary = f"""# Validation record — BikeEnergyLab 1.0.0 — 2026-10-04

The functional software release passed {tests} tests, Ruff lint/format, and GUI
workflows in ES/EN. The retained protocol executes eleven examples, EXP-01–15,
three-seed predictive ID/OOD validation, causal drift, telemetry conversion and
OAT/Spearman/Morris/Sobol sensitivity. The release source identity is
`{identity}`.

The installed wheel runs with isolated imports in a venv without inherited
system-site libraries, using different scientific dependency versions from the
development environment. It and the Windows executable passed M1–M4 replay,
physical/hybrid exports, predictive Monte Carlo, timestamped telemetry, Morris,
Sobol, adaptation/replay, point-only predictions and GUI checks. Predictions
matched to 1e-8; pip check passed. The portable ZIP includes program/dependencies,
manuals, configurations, examples, synthetic datasets, notices and file hashes.

Current predictive protocol: `{predictive.relative_to(ROOT).as_posix()}`.
Three seeds (42, 73, 109), each with 60 train, 30 independent calibration and
15 test routes per ID/seven OOD scenarios. All {len(predictive_metadata["input_sha256"])} input CSV hashes
are retained. M4 ID mean CRPS={id_m4.crps_wh_mean:.3f} Wh, central-95% coverage=
{id_m4.empirical_coverage95_mean:.4f}, budget Brier={id_m4.energy_budget_brier_mean:.4f}.
M4 temperature/combined OOD coverage remains zero; error transfer under those
shifts fails. No distribution was tuned using test labels. See the exported
report for every baseline and scenario, including unfavorable findings.

Current causal drift protocol: `{prequential.relative_to(ROOT).as_posix()}`.
For 32 predict-before-update synthetic routes, M4 adaptive MAE={adaptive_mae:.3f} Wh
and frozen MAE={frozen_mae:.3f} Wh under the declared Crr ramp. Adaptive physics
M1 had lower error than adaptive M4; this controlled result does not establish
universal residual/gating value or adaptation accuracy with real data.

Full suite: `{suite.relative_to(ROOT).as_posix()}`. Acceptance record:
`results/release-1.0.0/acceptance.json`; distribution record:
`results/distribution-verification-1.0.0/verification.json`; final artifact hashes:
`results/release_verification.json`. Previous runs retain their own source hashes.

Numerical verification includes analytical forces/balances, depletion/current/
voltage limits, ECM, maps, route conservation, known-truth recovery and
identifiability, fit/adaptation rollback, held-out group isolation, seed
repeatability, signed predictive errors and explicit unsupported energy budgets.
Morris matches linear effects; Sobol matches the Ishigami reference including
interactions. Timed GPX stops and telemetry time/energy are checked across
datetime resolutions. Physical trajectory bands have sample attrition and no
extrapolation after depletion. Static translated plots and trajectory bands were
visually inspected. Native GUI smoke checks forms, plots, jobs and language
rebuilds; a full manual review of every native UI state and another Windows
machine are additional distribution evidence.

One environment warning reports fallback from undetectable physical-core count
to logical cores; all checks passed. The forest remains configured for one job.

This closes functional software verification and synthetic validation. Field
accuracy, mission-probability calibration, observed physical drift and hardware
parameters require independent measurements. CGPRA academic originality requires
prior-art/peer review. Software uses inverse prescribed-speed dynamics and an
explicit battery model; route-level residuals do not identify learned dynamic
SOC/current/voltage. The project license retains the authors' rights.
"""
        (ROOT / "docs/validation.md").write_text(summary, encoding="utf-8")
        index = f"""# Results index — BikeEnergyLab 1.0.0

Current acceptance: `release-1.0.0/acceptance.json` and `release_verification.json`.
All entries refer to source SHA256 `{identity}`.

- Predictive ID/seven-OOD, three seeds: `{predictive.relative_to(ROOT / "results").as_posix()}`.
- Causal frozen/adaptive drift: `{prequential.relative_to(ROOT / "results").as_posix()}`.
- EXP-01–15: `{suite.relative_to(ROOT / "results").as_posix()}`.
- Eleven examples: `release-1.0.0/examples/index.json`.
- OAT/Spearman/Morris/Sobol: `release-1.0.0/sensitivity/` (choose final-source runs).
- Telemetry conversion: `release-1.0.0/telemetry/`.
- Wheel/executable verification: `distribution-verification-1.0.0/verification.json`.
- Logs: `build_logs/*-v1.0.0.log`.

Each scientific EXP retains protocol, configuration, input hashes, tables and
figures. Read all scenarios/models together. M4 ID coverage averages 95.56%,
while temperature/combined OOD coverage is zero. Synthetic adaptive M4 improves
over frozen M4 for the declared ramp, but adaptive M1 performs best. No measured
accuracy, probability calibration or universal CGPRA superiority is asserted.

The historical 0.2 predictive validation remains at
`predictive-validation/EXP-20261001-151847-7f343a36/`; its record is
`release_verification_0.2.0.json`. Earlier 0.1 benchmark, repeated seeds and
experiments remain an audit trail. Runs with different source hashes describe
their own implementations. Historical affected M2 runs are marked superseded.
All demonstration data are synthetic; no field measurements were manufactured.
"""
        (ROOT / "results/README.md").write_text(index, encoding="utf-8")
    destination = ROOT / "results/release_verification.json"
    if destination.exists():
        previous = json.loads(destination.read_text())
        if previous["version"] != "1.0.0":
            (ROOT / f"results/release_verification_{previous['version']}.json").write_bytes(
                destination.read_bytes()
            )
    artifacts = [
        ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe",
        ROOT / "dist/BikeEnergyLab-1.0.0-windows-x64.zip",
        ROOT / "dist/packages/bikeenergylab-1.0.0-py3-none-any.whl",
        ROOT / "dist/packages/bikeenergylab-1.0.0.tar.gz",
    ]
    record = {
        "version": "1.0.0",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "tests_passed": tests,
        "source_sha256": identity,
        "acceptance": acceptance,
        "distribution_verification": verification_path.relative_to(ROOT).as_posix(),
        "distribution_checks": verification["checks"],
        "predictive_validation_run": predictive.relative_to(ROOT).as_posix(),
        "prequential_run": prequential.relative_to(ROOT).as_posix(),
        "suite_run": suite.relative_to(ROOT).as_posix(),
        "hashed_predictive_inputs": len(predictive_metadata["input_sha256"]),
        "artifact_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in artifacts},
        "limitations": [
            "No real telemetry validation",
            "No academic novelty claim",
            "No cross-machine Windows/manual-all-states UI acceptance",
        ],
    }
    destination.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Final release evidence: {destination}")


if __name__ == "__main__":
    main()

"""Finalize a UI-only release while retaining its scientific baseline evidence."""

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from bikeenergylab import __version__

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-only", action="store_true")
    args = parser.parse_args()
    version = __version__
    package = ROOT / "src/bikeenergylab"
    source = hashlib.sha256()
    for path in sorted(package.rglob("*.py")):
        source.update(path.relative_to(package).as_posix().encode())
        source.update(path.read_bytes())
    identity = source.hexdigest()
    acceptance_path = ROOT / f"results/release-{version}/acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    verification_path = ROOT / f"results/distribution-verification-{version}/verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if acceptance["source_sha256"] != identity or any(c["exit_code"] for c in acceptance["checks"]):
        raise ValueError("Core acceptance does not match current sources")
    for check in acceptance["checks"]:
        if sha(ROOT / check["log"]) != check["log_sha256"]:
            raise ValueError("An accepted log was modified")
    if verification["source_sha256"] != identity or not verification["matching_predictions"]:
        raise ValueError("Distribution verification does not match current sources")
    if any(version not in value for value in verification["versions"].values()):
        raise ValueError("Distribution versions differ from this release")
    gui_acceptance = {}
    for runtime in ["source", "windows"]:
        report_path = (
            ROOT / f"results/gui-button-verification-{version}/{runtime}/verification.json"
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        log_path = ROOT / f"results/build_logs/gui-buttons-{runtime}-v{version}.log"
        log = log_path.read_text(encoding="utf-8")
        if (
            report["version"] != version
            or not report["passed"]
            or report["cases_passed"] != len(report["cases"])
            or not all(case["passed"] for case in report["cases"])
            or "GUI smoke passed:" not in log
        ):
            raise ValueError(f"Extended GUI acceptance did not pass: {runtime}")
        gui_acceptance[runtime] = {
            "report": report_path.relative_to(ROOT).as_posix(),
            "report_sha256": sha(report_path),
            "cases_passed": report["cases_passed"],
            "log_sha256": sha(log_path),
            "dialog_responses": report["dialog_responses"],
            "limits": report["limits"],
        }
    destination = ROOT / "results/release_verification.json"
    baseline_path = ROOT / "docs/validation_data/baseline/release_verification.json"
    if not baseline_path.exists():
        previous = json.loads(destination.read_text(encoding="utf-8"))
        if previous["version"] != "1.0.0":
            raise ValueError("Missing original scientific baseline release record")
        baseline_path.write_bytes(destination.read_bytes())
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_wheel_key = "dist/packages/bikeenergylab-1.0.0-py3-none-any.whl"
    wheel = ROOT / "docs/validation_data/baseline/bikeenergylab-1.0.0-py3-none-any.whl"
    if sha(wheel) != baseline["artifact_sha256"][baseline_wheel_key]:
        raise ValueError("Scientific baseline wheel identity differs")
    with zipfile.ZipFile(wheel) as archive:
        for path in package.rglob("*.py"):
            relative = path.relative_to(package).as_posix()
            if relative.startswith("gui/"):
                continue
            current, previous = path.read_bytes(), archive.read(f"bikeenergylab/{relative}")
            if relative == "__init__.py":
                current = re.sub(rb'__version__ = "[^"]+"', b"VERSION", current)
                previous = re.sub(rb'__version__ = "[^"]+"', b"VERSION", previous)
            if current != previous:
                raise ValueError(f"UI-only release changed core module: {relative}")
    tests = int(
        re.search(
            r"(\d+) passed",
            (ROOT / f"results/build_logs/tests-v{version}.log").read_text(encoding="utf-8"),
        ).group(1)
    )
    artifacts = [
        ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe",
        ROOT / f"dist/BikeEnergyLab-{version}-windows-x64.zip",
        ROOT / f"dist/packages/bikeenergylab-{version}-py3-none-any.whl",
        ROOT / f"dist/packages/bikeenergylab-{version}.tar.gz",
    ]
    documents_path = ROOT / f"results/documents-verification-{version}.json"
    if not documents_path.is_file():
        raise ValueError("Release requires the four reviewed Word documents")
    documents = None
    if documents_path.exists():
        documents = json.loads(documents_path.read_text(encoding="utf-8"))
        if documents["version"] != version or not documents["all_pages_visually_reviewed"]:
            raise ValueError("Document review does not match this release")
        if documents.get("source_sha256") != identity or len(documents["documents"]) != 4:
            raise ValueError("Reviewed manuals must match current software sources")
        for document in documents["documents"]:
            path = ROOT / document["path"]
            if sha(path) != document["sha256"]:
                raise ValueError(f"Reviewed document changed: {path.name}")
            artifacts.append(path)
    record = {
        "version": version,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": identity,
        "tests_passed": tests,
        "acceptance": acceptance,
        "distribution_verification": verification_path.relative_to(ROOT).as_posix(),
        "distribution_checks": verification["checks"],
        "scientific_baseline": baseline_path.relative_to(ROOT).as_posix(),
        "scientific_baseline_wheel": wheel.relative_to(ROOT).as_posix(),
        "core_modules_identical_to_baseline_except_version": True,
        "scope": "Four template-based Word documents, illustrated user guide and delivery packaging; scientific core and verified executable retained",
        "extended_gui_acceptance": gui_acceptance,
        "artifact_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in artifacts},
        "limitations": baseline["limitations"],
    }
    if documents:
        record["documents_verification"] = documents_path.relative_to(ROOT).as_posix()
        record["reviewed_document_pages"] = documents["total_pages"]
    if not args.record_only:
        historical = ROOT / "docs/validation_1.0.0.md"
        if not historical.exists():
            historical.write_text(
                (ROOT / "docs/validation.md")
                .read_text(encoding="utf-8")
                .replace(
                    "results/release_verification.json", "results/release_verification_1.0.0.json"
                ),
                encoding="utf-8",
            )
        (ROOT / "docs/validation.md").write_text(
            f"""# Validation record — BikeEnergyLab {version}

This UI release passed {tests} regression tests, Ruff lint/format and the complete
ES/EN GUI smoke workflow. Nine packaged examples cover physical comparisons,
known-truth calibration, uncertainty, independently calibrated CGPRA and mission
probability. The eight-step tutorial was exercised through route preview,
simulation, results, language rebuild, uncertainty, export, Back/Next and closing.

Both the Windows executable and isolated installed wheel passed these workflows,
M1–M4 replay, hybrid/predictive exports, sensitivity, telemetry, adaptation and
pip check. Their predictions matched to 1e-8. Source SHA256: `{identity}`.

Acceptance: `results/release-{version}/acceptance.json`.
Distribution: `results/distribution-verification-{version}/verification.json`.
Artifact hashes: `results/release_verification.json`.

All Python core modules outside the GUI match the 1.0.0 wheel byte-for-byte,
apart from the version declaration. The previous scientific protocols were not
rerun as new research results. Their identities, unfavorable findings and limits
are retained in [the 1.0.0 record](validation_1.0.0.md) and
`results/release_verification_1.0.0.json`. All practice data are synthetic.
Field accuracy, probability calibration and academic novelty remain unverified.
Manual acceptance of every native window state and another Windows machine are
additional evidence; automated GUI checks do not establish these.
""",
            encoding="utf-8",
        )
        index = ROOT / "results/README.md"
        history = index.read_text(encoding="utf-8")
        marker = "# Results index — BikeEnergyLab 1.0.0"
        history = history[history.index(marker) :].replace(
            "`release_verification.json`", "`release_verification_1.0.0.json`"
        )
        index.write_text(
            f"# Results index — BikeEnergyLab {version}\n\n"
            f"Current: `release-{version}/acceptance.json`, `release_verification.json`, "
            f"`distribution-verification-{version}/verification.json`.\n"
            f"Source SHA256 `{identity}`; {tests} regression tests and complete GUI tutorial/export checks.\n"
            "Scientific baseline: `release_verification_1.0.0.json`; core modules unchanged except version.\n\n"
            "The following entries retain the 1.0.0 source identity and historical results.\n\n"
            + history,
            encoding="utf-8",
        )
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"UI release record: {destination}")


if __name__ == "__main__":
    main()

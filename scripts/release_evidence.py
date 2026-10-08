"""Curated audit evidence distributed with BikeEnergyLab 1.0.0.

The complete raw protocol runs remain in the development workspace. This
inventory contains the original summary CSVs, protocol metadata and primary
acceptance logs needed to audit the claims made in the delivered manuals.
"""

from pathlib import Path

EVIDENCE_FILES = (
    "results/README.md",
    "results/evidence-inventory-1.0.0.json",
    "results/release_verification_1.0.0.json",
    "results/release-1.0.0/acceptance.json",
    "results/distribution-verification-1.0.0/verification.json",
    "results/documents-verification-1.0.0.json",
    "results/gui-button-verification-1.0.0/source/verification.json",
    "results/gui-button-verification-1.0.0/windows/verification.json",
    "results/build_logs/lint-v1.0.0.log",
    "results/build_logs/format-v1.0.0.log",
    "results/build_logs/tests-v1.0.0.log",
    "results/build_logs/tests-audit-v1.0.0.log",
    "results/build_logs/windows-audit-v1.0.0.log",
    "results/build_logs/gui-v1.0.0.log",
    "results/build_logs/gui-buttons-source-v1.0.0.log",
    "results/build_logs/gui-buttons-windows-v1.0.0.log",
    "results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83/aggregate.csv",
    "results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83/metadata.json",
    "results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83/protocol.json",
    "results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83/report.md",
    "results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc/metrics.csv",
    "results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc/metadata.json",
    "results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc/protocol.json",
    "results/release-1.0.0/suite/EXP-20261004-111632-2db2d0bc/experiment_index.json",
    "results/release-1.0.0/suite/EXP-20261004-111632-2db2d0bc/metadata.json",
    "results/release-1.0.0/examples/index.json",
)


def evidence_paths(root: Path):
    for relative in EVIDENCE_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing audit evidence: {relative}")
        yield relative, path

# Validation record — BikeEnergyLab 1.0.0

This unified 1.0.0 release passed 80 regression tests, Ruff lint/format and the complete
ES/EN GUI smoke workflow. Nine packaged examples cover physical comparisons,
known-truth calibration, uncertainty, independently calibrated CGPRA and mission
probability. The eight-step tutorial was exercised through route preview,
simulation, results, language rebuild, uncertainty, export, Back/Next and closing.

Both the Windows executable and isolated installed wheel passed these workflows,
M1–M4 replay, hybrid/predictive exports, sensitivity, telemetry, adaptation and
pip check. Their predictions matched to 1e-8. Source SHA256: `25a63aafb85d6936b886c5b15f9f5addc3086267861aad7702fe4b53fa98338f`.

Acceptance: `results/release-1.0.0/acceptance.json`.
Distribution: `results/distribution-verification-1.0.0/verification.json`.
Artifact hashes: `results/release_verification.json`.

All Python core modules outside the GUI match the archived scientific baseline
wheel byte-for-byte, apart from the version declaration. The current release
unifies the version as 1.0.0 and retains examples, tutorial and Word manuals. The previous scientific protocols were not
rerun as new research results. Their identities, unfavorable findings and limits
are retained in [the 1.0.0 record](validation_1.0.0.md) and
`results/release_verification_1.0.0.json`. All practice data are synthetic.
Field accuracy, probability calibration and academic novelty remain unverified.

Four Spanish DOCX documents accompany the 8 October 2026 audit correction.
The 31-page user manual contains 25 actual GUI captures, nine distinct executed
examples and an eight-step tutorial. The 17-page technical manual integrates
the complete scientific methodology, including 32 editable Word equation
objects, API, tests, historical evidence and limitations. The 17-page software
description and one-page title/functions document follow the supplied templates.
All 66 pages were rendered and reviewed after the final edits. Their exact
hashes, template checks, page images and source/executable capture provenance
are recorded in results/documents-verification-1.0.0.json.

The original 80-test suite passed again on 8 October 2026. The delivered
results/evidence-inventory-1.0.0.json identifies original summary tables,
protocol metadata, GUI acceptance reports and primary test logs by SHA256.
This is software and documentation evidence, not field accuracy validation.

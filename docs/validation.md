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

Five Spanish DOCX documents accompany this revision. The user manual contains
25 actual GUI captures and nine executed examples; the technical manual and
scientific methodology retain API, equations and historical evidence. Software
description and title/functions follow the supplied document organization.
Microsoft Word updated their contents fields and rendered 33, 14, 15, 17 and 1
pages respectively. All 80 final pages were visually reviewed at native 150 dpi.
The methodology retains 26 editable Word equations. Identities, source-template
style fidelity and review are recorded in documents-verification-1.0.0.json.
These documentation checks do not add physical validation results.
Manual acceptance of every native window state and another Windows machine are
additional evidence; automated GUI checks do not establish these.

Expanded GUI acceptance passed 114 checks in source and 114 in the Windows executable. It checks the nine Cargar ejemplo → Simular workflows, file/model buttons, all four sensitivity methods, benchmark, EXP 01–15, guide and PNG/SVG/PDF exports through actual Tk widget invocation with controlled dialog responses. Native Windows dialog rendering is not certified. Reports: results/gui-button-verification-1.0.0. Contact: fjburgosf@gmail.com.

# Validation record — BikeEnergyLab 1.0.0 — 2026-10-04

The functional software release passed 73 tests, Ruff lint/format, and GUI
workflows in ES/EN. The retained protocol executes eleven examples, EXP-01–15,
three-seed predictive ID/OOD validation, causal drift, telemetry conversion and
OAT/Spearman/Morris/Sobol sensitivity. The release source identity is
`673a01840921e82c8904babd11a4a3f9cda7174edbbd6f5c198076d6e0088344`.

The installed wheel runs with isolated imports in a venv without inherited
system-site libraries, using different scientific dependency versions from the
development environment. It and the Windows executable passed M1–M4 replay,
physical/hybrid exports, predictive Monte Carlo, timestamped telemetry, Morris,
Sobol, adaptation/replay, point-only predictions and GUI checks. Predictions
matched to 1e-8. Pip check passed. The portable ZIP includes program/dependencies,
manuals, configurations, examples, synthetic datasets, notices and file hashes.

Current predictive protocol: `results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83`.
Three seeds (42, 73, 109), each with 60 train, 30 independent calibration and
15 test routes per ID/seven OOD scenarios. All 30 input CSV hashes
are retained. M4 ID mean CRPS=0.347 Wh, central-95% coverage=
0.9556, budget Brier=0.0722.
M4 temperature/combined OOD coverage remains zero. Error transfer under those
shifts fails. No distribution was tuned using test labels. See the exported
report for every baseline and scenario, including unfavorable findings.

Current causal drift protocol: `results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc`.
For 32 predict-before-update synthetic routes, M4 adaptive MAE=1.377 Wh
and frozen MAE=2.023 Wh under the declared Crr ramp. Adaptive physics
M1 had lower error than adaptive M4. This controlled result does not establish
universal residual/gating value or adaptation accuracy with real data.

Full suite: `results/release-1.0.0/suite/EXP-20261004-111632-2db2d0bc`. Acceptance record:
`results/release-1.0.0/acceptance.json`. Distribution record:
`results/distribution-verification-1.0.0/verification.json`. Final artifact hashes:
`results/release_verification_1.0.0.json`. Previous runs retain their own source hashes.

Numerical verification includes analytical forces/balances, depletion/current/
voltage limits, ECM, maps, route conservation, known-truth recovery and
identifiability, fit/adaptation rollback, held-out group isolation, seed
repeatability, signed predictive errors and explicit unsupported energy budgets.
Morris matches linear effects. Sobol matches the Ishigami reference including
interactions. Timed GPX stops and telemetry time/energy are checked across
datetime resolutions. Physical trajectory bands have sample attrition and no
extrapolation after depletion. Static translated plots and trajectory bands were
visually inspected. Native GUI smoke checks forms, plots, jobs and language
rebuilds. A full manual review of every native UI state and another Windows
machine are additional distribution evidence.

One environment warning reports fallback from undetectable physical-core count
to logical cores. All checks passed. The forest remains configured for one job.

This closes functional software verification and synthetic validation. Field
accuracy, mission-probability calibration, observed physical drift and hardware
parameters require independent measurements. CGPRA academic originality requires
prior-art/peer review. Software uses inverse prescribed-speed dynamics and an
explicit battery model. Route-level residuals do not identify learned dynamic
SOC/current/voltage. The project license retains the authors' rights.

# Technical manual

## Architecture

The package keeps numerical work independent of GUI and visualization:

| Module | Responsibility |
| --- | --- |
| config.py | Dataclasses, strict YAML, domains and parameter copies |
| routes | Interval routes, CSV/GPX, recorded median smoothing, segmentation |
| physics | SI forces, signed wind and dry-air density |
| motor | Rectangular efficiency maps and illustrative map generation |
| battery | Stateful energy/SOC and one-RC Thevenin updates |
| model.py | Operating profile, physical demand, state integration and balances |
| calibration | Bounded least squares, practical identifiability, causal RLS |
| residual | Features, M1–M4, gates, conformal, adaptation, portable model replay |
| uncertainty | Physical priors/mission/range and optional empirical energy errors |
| metrics | MAE/RMSE/R², intervals, exact empirical CRPS |
| experiments | Synthetic truth, ID/OOD, ablations, EXP-01–15 |
| io | Quality reports, immutable input exports and run metadata |
| visualization | Headless Matplotlib PNG/SVG/PDF exports |
| gui | Tk adapter, bilingual help, worker thread and main-thread updates |
| cli.py | Validated offline command dispatcher and logging |

Rider/environment equations remain small and are composed in the operating-profile
method. Separate packages would add no useful abstraction at this fidelity.
Do not import GUI from the public numerical API.

## Public classes and workflow

`Config.from_yaml`, `Config.from_dict`, `Config.changed` and `validate`.
`Route.synthetic`, `from_csv`, `from_gpx`, `from_elevation`, `subdivide`, `uniform`, `adaptive`.
`BikeModel.operating_profile`, `predict_energy`, `simulate`, `calibrate`,
`predict_range`, `predict_mission_probability`. `SimulationResult.export`.
`Observation(route, energy_wh, config, group, weight)` explicitly couples known
operating conditions to a measured total. `CalibrationResult` returns parameters,
residuals, covariance and identifiability. `CGPRAModel.fit`, `predict`,
`calibrate_intervals`, `adapt`, `save`, `load`, `annotate_simulation`.
`ConfidenceGate.fit/evaluate`. Optional `predict(physical_energy_wh=...)` preserves
sampled physical parameters in uncertainty propagation. Invalid interval
recalibration does not damage previous valid state. Replay and predictive-energy
API/CLI usage are documented in [predictive_workflow.md](predictive_workflow.md).

Prescribed route → operating profile → requested battery power → battery state
constraints → realized contributions/SOC → physical feasibility → artifacts.
Scientific equations, gates and assumptions are in methodology.md.

## Example: inference and intervals

```python
from bikeenergylab import Config
from bikeenergylab.experiments import generate_observations
from bikeenergylab.residual import CGPRAModel

train = generate_observations(60, 42, prefix="train")
interval = generate_observations(30, 43, prefix="interval")
test = generate_observations(15, 44, scenario="OOD-Wind", prefix="test")
model = CGPRAModel(Config(), seed=42).fit(train)
model.calibrate_intervals(interval)
prediction = model.predict(test, model="M4", coverage=0.95)
```

For causal adaptation, `model.adapt(new_observation)` updates the physical model
and residual. Old intervals are invalid. Do not adapt with holdout/test labels
before reporting the original prediction. Fit new intervals on a fresh split.

## Input/output and reproducibility

YAML rejects unknown sections and misspelled dataclass attributes. CSV/GPX require
explicit units. Malformed data are rejected or reported. Quality checks do not
fix data. Exports produce a new EXP directory. Existing runs are not overwritten.
Metadata stores seed, Bogota timestamp, version, dependencies and SHA256 hashes.
`io.telemetry.load_telemetry` validates sample groups, derives interval speed from
distance/time and integrates measured terminal V*I with endpoint trapezoids,
retaining explicit conversion provenance and all quality warnings.
`uncertainty.sensitivity.one_at_a_time` covers Crr, CdA, mass, rider power, speed,
wind, temperature and motor efficiency. Spearman associations are also available.
`uncertainty.global_sensitivity.physical_sensitivity` adds seeded Morris, Sobol
and Latin-hypercube Spearman designs. `analyze_global` accepts arbitrary scalar
responses. Tests use linear effects and the Ishigami interaction benchmark.
`experiments.adaptive.prequential_evaluate` predicts complete routes before
each new target is ingested. Fit/adaptation commit state only after all steps
succeed. Adaptation invalidates conformal/error pools. Point-only inference
remains available until fresh independent interval calibration.
Source-mode hashes cover package .py files. The Windows build embeds the same
source identity, since bytecode archives cannot be hashed as source files.

Actual settings/profiles override defaults in the same order in API/CLI/GUI.
Motor maps and imported routes are copied into run artifacts to permit portable
reruns. The CLI catches input/IO errors and returns status 2. Unexpected failures
are exposed with tracebacks rather than silently manufacturing a successful run.

## Tests and builds

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m bikeenergylab gui --smoke-test
.\.venv\Scripts\python.exe -m build --no-isolation
.\scripts\build_windows.ps1
```

For the expanded distribution verification, install the wheel into a venv without
system-site packages and run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_distribution.py --installed-python build/verify-venv/Scripts/python.exe --model results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83/seed-42/model --output results/distribution-verification-1.0.0
```

This checks isolated imports, M1–M4 replay across dependency versions, hybrid
simulation and predictive uncertainty exports, source hash equality, GUI workflows
and pip check in both the installed wheel and Windows executable.
GUI checks use Tk's real event loop and fail on callback/unraisable errors.
They also exercise the packaged examples dropdown and the eight-step tutorial,
including ES/EN progress preservation, uncertain-wind practice and figure export.
SVG and PDF Matplotlib backends are explicitly included in the frozen build.
Obsolete Tk/Matplotlib cycles are collected on the UI thread, including shutdown.
The scientific worker receives configurations/routes/models rather than widgets.
`scripts/validate_release.ps1` executes unit checks, GUI, examples, EXP-01–15,
the three-seed predictive protocol, all sensitivity methods, causal drift and
package builds. `scripts/package_windows.py` includes documentation, examples,
configurations, synthetic datasets, dependency notices and file hashes in a ZIP.

Tests use a workspace-local temporary directory. Tests cover analytical forces,
signed wind, cubic aerodynamic power, energy/SOC, exact battery depletion,
auxiliary/motor feasibility, ECM, maps, route conservation, imports/exports,
synthetic recovery, identifiability, RLS, residual gates, heldout conformal,
adaptation interval invalidation, Monte Carlo and CLI.

PyInstaller uses onedir to reduce startup unpacking and preserve dependency files.
The folder includes numerical DLLs, Tk and Matplotlib resources, dependency
metadata and a source manifest. `build_windows.ps1` checks version, a numerical
simulation and a Tk simulation/ES–EN smoke test. No code signing or installer is
provided. A generated .spec is transient inside build/. The committed script is
the reproducible build description. The console-enabled executable supports
both CLI logging and GUI startup. Scientific dependency versions are pinned
by lock_environment.py. Bit-identical executable reproducibility is not claimed.

The `.venv` and build caches are development resources excluded from source
distribution. Source archives include examples/configs/docs/tests and clearly
synthetic datasets. No source-control remote is configured or published.

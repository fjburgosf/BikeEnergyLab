# Data contracts

No real measurements were present in the initial workspace. All shipped CSVs
are explicitly synthetic examples, not experimental observations.

## Route intervals

Required: `length_m`, `dt_s`, `speed_mps`, `grade` (rise/horizontal run, not percent).
Each row is a piecewise-constant interval. `length_m = speed_mps * dt_s`.
Zero speed with positive dt is a stationary interval and requires zero length.
Distance is along the road; cumulative endpoint distance/time are derived.

Optional: `elevation_m`, `acceleration_mps2`, `wind_mps`, `temperature_c`,
`surface`, `human_power_w`, `assist_level`, `auxiliary_power_w`, `cadence_rpm`,
`latitude`, `longitude`. Profile columns override scalar configuration.
Surface `default` uses fitted `bike.crr`; named surfaces use the editable lookup.
Wind is positive in the direction of travel and negative headwind. Crosswind
is not modeled. Elevation and speed observations are never silently imputed.

## Calibration observations

Same route intervals plus `route_id` and `observed_route_energy_wh`, one total
measured route energy repeated on every interval of that group. Do not split
these groups into random rows for validation. Optional `rider_mass_kg` is constant
per route. Exported synthetic tables include `known_config_json` with complete
known settings; the loader validates consistency rather than discarding them.
`observed_route_energy_wh` is terminal electrical energy, not battery chemical
energy. Substantially saturated/incomplete trials require explicit curation
before calibrating the unconstrained energy-demand target.

## Telemetry

Recommended optional SI fields:
`timestamp, distance_m, speed_mps, acceleration_mps2, elevation_m, grade,
voltage_v, current_a, soc, temperature_c, wind_mps, assist_level, cadence_rpm,
human_power_w, latitude, longitude`. SOC is a fraction, time is ISO8601 or seconds.
`quality` produces a report and never edits input. No full automatic reconstruction
of route intervals from arbitrary telemetry is assumed; define sampling/integration
conventions explicitly. For power integration, compute Wh from V*I*dt/3600 and
document time alignment and the handling of stops/missing observations.

`synthetic_calibration.csv` is generated with known Crr=0.008, CdA=0.48,
zero structural discrepancy and zero sensor noise for parameter-recovery testing.
The benchmark generator uses a distinct structural residual and nonzero noise;
its dataset partitions and equation are stored inside each result folder.

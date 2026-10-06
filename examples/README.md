# Runnable examples

Install the package, then run `python examples/run_examples.py` from the project
root. The script executes all eleven examples and writes an index of artifacts:
flat route, uphill route, headwind, rider power, temperature, known-parameter
calibration, Monte Carlo, M1–M4 benchmark, CGPRA, unseen route and mission with
38% initial SOC over 26 km. Inputs are synthetic and runs are explicitly seeded.

Each experiment writes configuration and run metadata together with its results.
The model comparison also exports train, interval-calibration and test partitions.
Temperature uses air density by default; no unmeasured battery-temperature curve
is invented. A power-limited example records feasibility instead of quietly
claiming the prescribed profile can be sustained.

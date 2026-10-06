"""One-at-a-time energy sensitivities, with explicit feasible-profile reporting."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bikeenergylab import BikeModel, Config, Route


def one_at_a_time(config: Config, route: Route, relative_step: float = 0.05) -> pd.DataFrame:
    """Evaluate +/-5% perturbations, or absolute steps for zero wind/temperature.

    Elasticity uses unconstrained electrical demand; simulator feasibility is
    reported separately. It is a local numerical sensitivity, not a causal effect.
    """
    if not 0 < relative_step < 0.5:
        raise ValueError("relative_step must lie in (0,0.5)")
    if config.motor.efficiency_map:
        raise ValueError(
            "motor.efficiency is overridden by its efficiency map; select explicit global sensitivity bounds"
        )
    paths = [
        "bike.crr",
        "bike.cda_m2",
        "rider.mass_kg",
        "rider.human_power_w",
        "route.speed_mps",
        "environment.wind_mps",
        "environment.temperature_c",
        "motor.efficiency",
    ]
    base_energy = BikeModel(config).predict_energy(route)
    rows = []
    for path in paths:
        if path == "route.speed_mps":
            value = float(np.average(route.frame.speed_mps, weights=route.frame.dt_s))
        else:
            section, key = path.split(".")
            value = float(getattr(getattr(config, section), key))
            override = {
                "environment.wind_mps": "wind_mps",
                "environment.temperature_c": "temperature_c",
                "rider.human_power_w": "human_power_w",
            }.get(path)
            if override and override in route.frame:
                raise ValueError(
                    f"Sensitivity {path} is overridden by route profile; use a scalar-condition route"
                )
        step = max(abs(value) * relative_step, 0.5 if path.startswith("environment.") else 1e-6)
        energies, feasible, endpoints = [], [], []
        for sign in [-1, 1]:
            cfg = config
            sample = route
            point = value + sign * step
            if path in {"bike.crr", "bike.cda_m2"}:
                point = max(0, point)
            if path == "environment.temperature_c":
                point = min(100, max(-100, point))
            if path in {"rider.human_power_w", "rider.mass_kg"}:
                point = max(0 if path.endswith("human_power_w") else 1e-6, point)
            if path == "motor.efficiency":
                point = min(1, max(1e-6, point))
            if path == "route.speed_mps":
                frame = route.frame.copy()
                frame["speed_mps"] *= point / value
                frame["dt_s"] = np.divide(
                    frame.length_m,
                    frame.speed_mps,
                    out=frame.dt_s.to_numpy().copy(),
                    where=frame.speed_mps > 0,
                )
                frame = frame.drop(columns="acceleration_mps2")
                sample = Route(frame, route.name, route.provenance)
            else:
                cfg = config.changed(path, point)
            model = BikeModel(cfg)
            energies.append(model.predict_energy(sample))
            check = model.operating_profile(sample)
            feasible.append(
                bool(
                    (
                        check.power_wheel_w - check.power_human_w - check.power_motor_requested_w
                        <= 1e-7
                    ).all()
                )
            )
            endpoints.append(point)
        derivative = (energies[1] - energies[0]) / (endpoints[1] - endpoints[0])
        rows.append(
            {
                "parameter": path,
                "base_value": value,
                "low": endpoints[0],
                "high": endpoints[1],
                "energy_low_wh": energies[0],
                "energy_high_wh": energies[1],
                "derivative_wh_per_parameter_unit": derivative,
                "elasticity": derivative * value / base_energy
                if abs(base_energy) > 1e-12
                else np.nan,
                "low_drive_feasible": feasible[0],
                "high_drive_feasible": feasible[1],
            }
        )
    return pd.DataFrame(rows)

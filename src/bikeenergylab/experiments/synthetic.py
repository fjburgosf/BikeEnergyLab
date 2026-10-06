"""Controlled synthetic observations with declared truth and structural discrepancy."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.calibration import Observation

SCENARIOS = [
    "ID",
    "OOD-Route",
    "OOD-Slope",
    "OOD-Temperature",
    "OOD-Rider",
    "OOD-Mass",
    "OOD-Wind",
    "OOD-Combined",
]


def generate_observations(
    n: int,
    seed: int = 42,
    scenario: str = "ID",
    discrepancy: bool = True,
    noise_std_wh_per_km: float = 0.12,
    prefix: str = "sample",
) -> list[Observation]:
    """Truth differs in Crr/CdA; residual has a declared, non-universal analytic form."""
    if scenario not in SCENARIOS or n < 1 or noise_std_wh_per_km < 0:
        raise ValueError("Invalid synthetic generator inputs")
    rng = np.random.default_rng(seed)
    observations = []
    for index in range(n):
        cfg = Config()
        cfg.motor.nominal_power_w = 2000
        cfg.motor.max_torque_nm = 150
        cfg.motor.max_speed_mps = 20
        cfg.battery.max_current_a = 100
        cfg.rider.human_power_w = float(rng.uniform(40, 90))
        cfg.environment.wind_mps = float(rng.uniform(-1, 1))
        cfg.environment.temperature_c = float(rng.uniform(15, 25))
        cfg.rider.mass_kg = float(rng.uniform(65, 85))
        speed = float(rng.uniform(4.5, 7))
        slope = float(rng.uniform(0.005, 0.03))
        length = float(rng.uniform(1500, 6000))
        if scenario in {"OOD-Slope", "OOD-Combined"}:
            slope = float(rng.uniform(0.06, 0.10))
        if scenario in {"OOD-Temperature", "OOD-Combined"}:
            cfg.environment.temperature_c = float(rng.uniform(-5, 5))
        if scenario in {"OOD-Rider", "OOD-Combined"}:
            cfg.rider.human_power_w = float(rng.uniform(140, 200))
        if scenario in {"OOD-Mass", "OOD-Combined"}:
            cfg.rider.mass_kg = float(rng.uniform(100, 120))
        if scenario in {"OOD-Wind", "OOD-Combined"}:
            cfg.environment.wind_mps = float(rng.uniform(-6, -3))
        phase = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        grades = slope * (0.6 + 0.4 * np.sin(phase + rng.uniform(0, 2 * np.pi)))
        velocities = np.full(24, speed)
        if scenario == "OOD-Route":
            # A different route morphology at familiar mean operating conditions.
            grades = slope * np.where(np.sin(3 * phase) > 0, 1.5, -0.5)
            velocities = speed * (1 + 0.15 * np.sin(2 * phase))
        d = np.full(24, length / 24)
        route = Route(
            pd.DataFrame(
                {"length_m": d, "dt_s": d / velocities, "speed_mps": velocities, "grade": grades}
            ),
            f"{prefix}-{scenario}-{index}",
            {"source": "synthetic", "scenario": scenario},
        )
        truth = cfg.changed("bike.crr", 0.008).changed("bike.cda_m2", 0.48)
        physical = BikeModel(truth).predict_energy(route)
        residual_rate = (
            (0.7 + 0.10 * (speed - 5) + 0.015 * (cfg.environment.temperature_c - 20) ** 2)
            if discrepancy
            else 0
        )
        energy = physical + length / 1000 * (residual_rate + rng.normal(0, noise_std_wh_per_km))
        observations.append(Observation(route, float(energy), cfg, route.name))
    return observations


def serialize_observations(observations: list[Observation]) -> pd.DataFrame:
    rows = []
    for observation in observations:
        frame = observation.route.frame.copy()
        frame["route_id"] = observation.group
        frame["observed_route_energy_wh"] = observation.energy_wh
        frame["observation_weight"] = observation.weight
        frame["rider_mass_kg"] = observation.config.rider.mass_kg
        for column, value in {
            "human_power_w": observation.config.rider.human_power_w,
            "wind_mps": observation.config.environment.wind_mps,
            "temperature_c": observation.config.environment.temperature_c,
        }.items():
            if column not in frame:
                frame[column] = value
        frame["known_config_json"] = json.dumps(observation.config.to_dict(), sort_keys=True)
        frame["route_provenance_json"] = json.dumps(observation.route.provenance, sort_keys=True)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def observations_from_csv(path: str, config: Config | None = None) -> list[Observation]:
    from pathlib import Path

    frame = pd.read_csv(path, float_precision="round_trip", dtype={"route_id": str})
    required = {"route_id", "observed_route_energy_wh", "length_m", "dt_s", "speed_mps", "grade"}
    if not required.issubset(frame):
        raise ValueError(f"Calibration CSV requires {sorted(required)}")
    result = []
    if frame.route_id.isna().any():
        raise ValueError("Missing route_id is not an independent group")
    for group, block in frame.groupby("route_id", sort=False):
        if (
            block.observed_route_energy_wh.isna().any()
            or block.observed_route_energy_wh.nunique() != 1
        ):
            raise ValueError("Each route must repeat one measured total route energy")
        if "known_config_json" in block:
            if block.known_config_json.nunique() != 1:
                raise ValueError("Known configuration must be constant per route")
            cfg = Config.from_dict(json.loads(block.known_config_json.iloc[0]))
            if cfg.motor.efficiency_map and not Path(cfg.motor.efficiency_map).is_absolute():
                cfg.motor.efficiency_map = str(
                    Path(path).resolve().parent / cfg.motor.efficiency_map
                )
        else:
            cfg = Config.from_dict((config or Config()).to_dict())
        if "rider_mass_kg" in block:
            if block.rider_mass_kg.nunique() != 1:
                raise ValueError("Rider mass must be constant per route")
            cfg = cfg.changed("rider.mass_kg", float(block.rider_mass_kg.iloc[0]))
        weight = 1.0
        if "observation_weight" in block:
            if block.observation_weight.isna().any() or block.observation_weight.nunique() != 1:
                raise ValueError("Observation weight must be constant per route")
            weight = float(block.observation_weight.iloc[0])
        provenance = {"source": "csv"}
        if "route_provenance_json" in block:
            if (
                block.route_provenance_json.isna().any()
                or block.route_provenance_json.nunique() != 1
            ):
                raise ValueError("Route provenance must be constant per route")
            provenance = json.loads(block.route_provenance_json.iloc[0])
            if not isinstance(provenance, dict):
                raise ValueError("Route provenance must be a JSON object")
        route = Route(
            block.drop(
                columns=[
                    "route_id",
                    "observed_route_energy_wh",
                    "rider_mass_kg",
                    "known_config_json",
                    "observation_weight",
                    "route_provenance_json",
                ],
                errors="ignore",
            ),
            str(group),
            provenance,
        )
        result.append(
            Observation(
                route, float(block.observed_route_energy_wh.iloc[0]), cfg, str(group), weight
            )
        )
    return result

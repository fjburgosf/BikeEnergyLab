"""Longitudinal SI equations with signed air-relative velocity."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GRAVITY_MPS2 = 9.80665
JOULES_PER_WH = 3600.0


@dataclass
class Forces:
    rolling_n: np.ndarray
    grade_n: np.ndarray
    aero_n: np.ndarray
    acceleration_n: np.ndarray

    @property
    def total_n(self) -> np.ndarray:
        return self.rolling_n + self.grade_n + self.aero_n + self.acceleration_n


def air_density(temperature_c: np.ndarray | float, pressure_pa: float = 101325) -> np.ndarray:
    """Dry ideal gas approximation; measured density may override it."""
    return pressure_pa / (287.05 * (np.asarray(temperature_c) + 273.15))


def longitudinal_forces(
    mass_kg: float,
    crr: np.ndarray | float,
    cda_m2: float,
    speed_mps: np.ndarray | float,
    grade: np.ndarray | float = 0,
    acceleration_mps2: np.ndarray | float = 0,
    wind_mps: np.ndarray | float = 0,
    density_kgm3: np.ndarray | float = 1.225,
) -> Forces:
    """Positive wind is tailwind; negative air-relative speed produces forward drag.

    Grade is rise/run (0.05 = 5%). Motion is forward only. Rolling force is zero
    at rest: static friction is outside this prescribed-speed model.
    """
    speed = np.asarray(speed_mps, float)
    angle = np.arctan(grade)
    relative = speed - wind_mps
    return Forces(
        mass_kg * GRAVITY_MPS2 * np.asarray(crr) * np.cos(angle) * (speed > 0),
        mass_kg * GRAVITY_MPS2 * np.sin(angle),
        0.5 * np.asarray(density_kgm3) * cda_m2 * relative * np.abs(relative),
        mass_kg * np.asarray(acceleration_mps2),
    )

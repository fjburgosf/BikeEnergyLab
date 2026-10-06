"""Motor maps and configurable controller limits, without brand assumptions."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator


class EfficiencyMap:
    """Rectangular measured or illustrative CSV map; clamped extrapolation is explicit."""

    def __init__(self, frame: pd.DataFrame) -> None:
        required = {"omega_rad_s", "torque_nm", "efficiency"}
        if not required.issubset(frame) or frame.duplicated(["omega_rad_s", "torque_nm"]).any():
            raise ValueError("Map requires unique omega_rad_s, torque_nm, efficiency rows")
        if (
            not np.isfinite(frame[list(required)].to_numpy()).all()
            or not frame.efficiency.between(1e-6, 1).all()
        ):
            raise ValueError("Invalid map efficiency")
        table = (
            frame.pivot(index="omega_rad_s", columns="torque_nm", values="efficiency")
            .sort_index()
            .sort_index(axis=1)
        )
        if (
            table.isna().any().any()
            or min(table.shape) < 2
            or (table.index < 0).any()
            or (table.columns < 0).any()
        ):
            raise ValueError("Map must be a complete nonnegative rectangular grid >=2x2")
        self.omega = table.index.to_numpy()
        self.torque = table.columns.to_numpy()
        self.interpolator = RegularGridInterpolator((self.omega, self.torque), table.to_numpy())

    @classmethod
    def from_csv(cls, path: str | Path) -> EfficiencyMap:
        return cls(pd.read_csv(path))

    def evaluate(self, omega: np.ndarray, torque: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        omega, torque = np.broadcast_arrays(omega, torque)
        outside = (
            (omega < self.omega[0])
            | (omega > self.omega[-1])
            | (torque < self.torque[0])
            | (torque > self.torque[-1])
        )
        points = np.column_stack(
            [
                np.clip(omega.ravel(), self.omega[0], self.omega[-1]),
                np.clip(torque.ravel(), self.torque[0], self.torque[-1]),
            ]
        )
        return self.interpolator(points).reshape(omega.shape), outside


def generate_illustrative_map(path: str | Path, peak_efficiency: float = 0.88) -> None:
    """Create an explicitly illustrative map, never a universal measured motor curve."""
    if not 0.1 <= peak_efficiency <= 1:
        raise ValueError("peak efficiency outside [0.1, 1]")
    rows = []
    for omega in np.linspace(0, 40, 9):
        for torque in np.linspace(0, 80, 9):
            eta = np.clip(
                peak_efficiency
                - 0.25 * ((omega - 20) / 20) ** 2
                - 0.20 * ((torque - 30) / 50) ** 2,
                0.1,
                peak_efficiency,
            )
            rows.append((omega, torque, eta))
    pd.DataFrame(rows, columns=["omega_rad_s", "torque_nm", "efficiency"]).to_csv(path, index=False)

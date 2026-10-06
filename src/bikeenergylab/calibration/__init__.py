"""Bounded offline fitting, practical identifiability and sequential adaptation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from bikeenergylab import BikeModel, Config, Route

LOGGER = logging.getLogger(__name__)
DEFAULT_BOUNDS = {
    "bike.crr": (0.001, 0.04),
    "bike.cda_m2": (0.1, 1.5),
    "motor.efficiency": (0.4, 0.98),
    "simulation.auxiliary_power_w": (0, 50),
    "rider.human_power_w": (0, 350),
}


@dataclass
class Observation:
    route: Route
    energy_wh: float
    config: Config = field(default_factory=Config)
    group: str = "observation"
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.energy_wh) or not np.isfinite(self.weight) or self.weight <= 0:
            raise ValueError("Observation energy must be finite and weight positive/finite")
        if not isinstance(self.group, str) or not self.group.strip():
            raise ValueError("Observation needs a nonempty string route group")


def transfer_parameters(target: Config, source: Config, names: list[str]) -> Config:
    result = target
    for path in names:
        section, key = path.split(".")
        result = result.changed(path, getattr(getattr(source, section), key))
    return result


@dataclass
class CalibrationResult:
    config: Config
    parameters: dict[str, float]
    covariance: np.ndarray
    identifiability: dict[str, Any]
    residuals_wh: np.ndarray
    success: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameters": self.parameters,
            "covariance": self.covariance,
            "identifiability": self.identifiability,
            "residuals_wh": self.residuals_wh,
            "success": self.success,
            "message": self.message,
        }


def calibrate(
    config: Config,
    observations: list[Observation],
    parameters: list[str] | None = None,
    bounds: dict[str, tuple[float, float]] | None = None,
    loss: str = "linear",
) -> CalibrationResult:
    names = parameters or ["bike.crr", "bike.cda_m2"]
    limits = dict(DEFAULT_BOUNDS, **(bounds or {}))
    if len(observations) < len(names) + 1 or len(set(names)) != len(names):
        raise ValueError("Need more observations than unique fitted parameters")
    if any(
        not np.isfinite(o.energy_wh) or not np.isfinite(o.weight) or o.weight <= 0
        for o in observations
    ):
        raise ValueError("Observations must have finite energy and positive weights")
    low, high = np.array([limits[n] for n in names]).T
    if not np.isfinite([low, high]).all() or np.any(low >= high):
        raise ValueError("Invalid calibration bounds")
    initial = np.array([getattr(getattr(config, n.split(".")[0]), n.split(".")[1]) for n in names])
    if np.any(initial < low) or np.any(initial > high):
        raise ValueError("Initial parameters lie outside calibration bounds")

    def unpack(vector: np.ndarray) -> Config:
        current = config
        for name, val in zip(names, vector):
            current = current.changed(name, float(val))
        return current

    def residual(vector: np.ndarray) -> np.ndarray:
        current = unpack(vector)
        return np.array(
            [
                (
                    BikeModel(transfer_parameters(o.config, current, names)).predict_energy(o.route)
                    - o.energy_wh
                )
                * np.sqrt(o.weight)
                for o in observations
            ]
        )

    fit = least_squares(
        residual,
        initial,
        bounds=(low, high),
        x_scale=high - low,
        loss=loss,
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-10,
    )
    scaled_jac = fit.jac * (high - low)
    singular = np.linalg.svd(scaled_jac, compute_uv=False)
    rank = int(np.linalg.matrix_rank(scaled_jac))
    condition = float(singular[0] / singular[-1]) if singular[-1] > 1e-12 else float("inf")
    dof = max(1, len(observations) - len(names))
    covariance = np.linalg.pinv(fit.jac.T @ fit.jac) * float(fit.fun @ fit.fun) / dof
    norms = np.linalg.norm(scaled_jac, axis=0)
    normalized = np.divide(scaled_jac, norms, out=np.zeros_like(scaled_jac), where=norms > 0)
    correlation = normalized.T @ normalized
    warnings = []
    if rank < len(names) or condition > 1e6:
        warnings.append("Parameters are practically non-identifiable or ill-conditioned")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if abs(correlation[i, j]) > 0.98:
                warnings.append(f"Highly correlated sensitivities: {names[i]} / {names[j]}")
    if np.any(fit.active_mask != 0):
        warnings.append("One or more fitted parameters reached their bounds")
    for message in warnings:
        LOGGER.warning(message)
    identifiability = {
        "rank": rank,
        "scaled_condition_number": condition,
        "scaled_singular_values": singular.tolist(),
        "sensitivity_cosine": correlation.tolist(),
        "warnings": warnings,
        "covariance_assumption": "local linear, independent errors; approximate for robust loss",
    }
    current = unpack(fit.x)
    return CalibrationResult(
        current,
        dict(zip(names, map(float, fit.x))),
        covariance,
        identifiability,
        fit.fun,
        bool(fit.success),
        fit.message,
    )


class SequentialCalibrator:
    """Bounded local-Jacobian recursive least squares in normalized parameter space.

    Used only for causally available observations. Not an SOC observer or a global
    convergence guarantee. Initialization can use an offline calibration.
    """

    def __init__(
        self,
        config: Config,
        parameters: list[str] | None = None,
        forgetting_factor: float = 0.995,
        observation_variance_wh2: float = 1.0,
    ) -> None:
        self.config = config
        self.names = parameters or ["bike.crr", "bike.cda_m2"]
        if (
            not 0 < forgetting_factor <= 1
            or not np.isfinite(observation_variance_wh2)
            or observation_variance_wh2 <= 0
        ):
            raise ValueError("Invalid sequential update controls")
        self.forgetting = forgetting_factor
        self.noise = observation_variance_wh2
        self.covariance = np.eye(len(self.names)) * 0.1
        self.updates = 0

    def update(self, observation: Observation) -> dict[str, Any]:
        if not np.isfinite(observation.energy_wh):
            raise ValueError("Finite observed energy required")
        cfg = transfer_parameters(observation.config, self.config, self.names)
        prediction = BikeModel(cfg).predict_energy(observation.route)
        gradient, theta, scale = [], [], []
        for name in self.names:
            section, key = name.split(".")
            value = getattr(getattr(self.config, section), key)
            low, high = DEFAULT_BOUNDS[name]
            span = high - low
            h = span * 1e-5
            left, right = max(low, value - h), min(high, value + h)
            slope = (
                BikeModel(cfg.changed(name, right)).predict_energy(observation.route)
                - BikeModel(cfg.changed(name, left)).predict_energy(observation.route)
            ) / (right - left)
            gradient.append(slope * span)
            theta.append((value - low) / span)
            scale.append((low, span))
        jac = np.array(gradient)
        prior = self.covariance / self.forgetting
        gain = prior @ jac / (self.noise + jac @ prior @ jac)
        error = observation.energy_wh - prediction
        updated = np.clip(np.array(theta) + gain * error, 0, 1)
        # Joseph form preserves positive semidefinite covariance.
        identity = np.eye(len(jac)) - np.outer(gain, jac)
        covariance = identity @ prior @ identity.T + np.outer(gain, gain) * self.noise
        updated_config = self.config
        for name, val, (low, span) in zip(self.names, updated, scale):
            updated_config = updated_config.changed(name, float(low + span * val))
        self.config, self.covariance = updated_config, covariance
        self.updates += 1
        return {
            "innovation_wh": error,
            "prediction_before_update_wh": prediction,
            "updates": self.updates,
            "normalized_covariance": self.covariance.tolist(),
        }

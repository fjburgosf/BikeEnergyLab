"""M1–M4 physics/residual predictors and two support-based confidence gates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from bikeenergylab import BikeModel, Config
from bikeenergylab.calibration import Observation, calibrate, transfer_parameters

FEATURE_NAMES = [
    "mean_speed_mps",
    "mean_speed_cubed",
    "mean_acceleration_mps2",
    "mean_grade",
    "positive_grade",
    "mean_wind_mps",
    "temperature_c",
    "human_power_w",
    "mass_kg",
    "assist_level",
    "mean_crr",
    "speed_std",
]


class StableScaler(StandardScaler):
    """Prevent amplification of roundoff in numerically constant route features.

    A 1e-6 scale floor in each feature's declared unit regularizes division only;
    it is a numerical tolerance, not a claimed sensor resolution. Exact and nearly
    constant training dimensions remain available for support/OOD diagnostics.
    """

    def fit(self, x: np.ndarray, y: Any = None, sample_weight: Any = None) -> StableScaler:
        super().fit(x, y, sample_weight=sample_weight)
        self.scale_ = np.maximum(self.scale_, 1e-6)
        return self


def features(observation: Observation, reference_crr: float | None = None) -> np.ndarray:
    f, cfg = observation.route.frame, observation.config

    def mean(key: str, default: float) -> float:
        return float(np.average(f[key], weights=f.dt_s)) if key in f else default

    v = f.speed_mps.to_numpy()
    avg_v = mean("speed_mps", 0)
    # Global Crr is a fitted latent parameter, not a new operating condition.
    # Use one calibrated reference for fit/inference; known surface contrasts remain.
    base_crr = cfg.bike.crr if reference_crr is None else reference_crr
    crr = [base_crr if s == "default" else cfg.bike.surface_crr[s] for s in f.surface]
    return np.array(
        [
            avg_v,
            np.average(v**3, weights=f.dt_s),
            mean("acceleration_mps2", 0),
            mean("grade", 0),
            np.average(np.maximum(f.grade, 0), weights=f.dt_s),
            mean("wind_mps", cfg.environment.wind_mps),
            mean("temperature_c", cfg.environment.temperature_c),
            mean("human_power_w", cfg.rider.human_power_w),
            cfg.total_mass_kg,
            mean("assist_level", cfg.motor.assist_level),
            np.average(crr, weights=f.dt_s),
            np.sqrt(np.average((v - avg_v) ** 2, weights=f.dt_s)),
        ],
        dtype=float,
    )


class ConfidenceGate:
    """kNN gate (simple) or shrinkage Mahalanobis + ensemble uncertainty (advanced)."""

    def __init__(self, strategy: str = "advanced") -> None:
        if strategy not in {"simple", "advanced"}:
            raise ValueError("Gate strategy must be simple or advanced")
        self.strategy = strategy

    def fit(self, x: np.ndarray, residuals: np.ndarray) -> ConfidenceGate:
        if len(x) < 3:
            raise ValueError("Gate needs at least 3 support samples")
        self.scaler = StableScaler().fit(x)
        z = self.scaler.transform(x)
        self.n = len(x)
        self.residual_scale = max(float(np.std(residuals)), 0.1)
        self.neighbors = NearestNeighbors(n_neighbors=min(6, len(x))).fit(z)
        # Leave-self-out distances prevent zero-distance threshold leakage.
        distances, _ = self.neighbors.kneighbors(z)
        self.knn_scale = max(float(np.quantile(distances[:, 1:].mean(axis=1), 0.95)), 1e-6)
        self.covariance = LedoitWolf().fit(z)
        self.maha_scale = max(
            float(np.quantile(np.sqrt(self.covariance.mahalanobis(z)), 0.95)), 1e-6
        )
        return self

    def evaluate(
        self, x: np.ndarray, predictive_std: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        z = self.scaler.transform(x)
        distances, _ = self.neighbors.kneighbors(z)
        knn = distances.mean(axis=1) / self.knn_scale
        if self.strategy == "simple":
            score = knn
            uncertainty = np.zeros(len(x))
        else:
            maha = np.sqrt(self.covariance.mahalanobis(z)) / self.maha_scale
            score = np.maximum(knn, maha)
            uncertainty = (
                np.zeros(len(x)) if predictive_std is None else predictive_std / self.residual_scale
            )
        sample_support = self.n / (self.n + 20)
        alpha = sample_support * np.exp(-(np.maximum(score - 1, 0) ** 2)) / (1 + uncertainty**2)
        return np.clip(alpha, 0, 1), score


@dataclass
class Prediction:
    energy_wh: np.ndarray
    alpha: np.ndarray
    ood_score: np.ndarray
    residual_std_wh: np.ndarray
    lower_wh: np.ndarray | None = None
    upper_wh: np.ndarray | None = None


class CGPRAModel:
    """Train only on training routes; conformal calibration uses separate routes.

    Models learn Wh/km rather than total energy so route length is not a nuisance.
    Gate hyperparameters are fixed a priori. Conformal intervals require exchangeability
    for coverage; no coverage guarantee is claimed under OOD.
    """

    def __init__(
        self,
        config: Config | None = None,
        seed: int = 42,
        gate_strategy: str = "advanced",
        calibrate_physics: bool = True,
    ) -> None:
        self.config = config or Config()
        self.seed = seed
        self.gate = ConfidenceGate(gate_strategy)
        self.calibrate_physics = calibrate_physics
        self.parameter_names = ["bike.crr", "bike.cda_m2"]
        self.quantiles: dict[tuple[str, float], float] = {}
        self.signed_errors_wh_per_km: dict[str, np.ndarray] = {}
        self.interval_groups: set[str] = set()
        self.invalidated_interval_groups: set[str] = set()
        self.interval_observations: list[Observation] = []
        self.fitted = False

    def physical(self, observations: list[Observation]) -> np.ndarray:
        return np.array(
            [
                BikeModel(
                    transfer_parameters(o.config, self.config, self.parameter_names)
                ).predict_energy(o.route)
                for o in observations
            ]
        )

    def fit(self, observations: list[Observation]) -> CGPRAModel:
        """Commit a new fit only after all physical and statistical steps succeed."""
        staged = deepcopy(self)
        staged._fit_in_place(observations)
        staged.__dict__.pop("sequential", None)
        self.__dict__ = staged.__dict__
        return self

    def _fit_in_place(self, observations: list[Observation]) -> CGPRAModel:
        if len(observations) < 10 or len({o.group for o in observations}) != len(observations):
            raise ValueError("Fit needs >=10 independent route groups, one observation per group")
        self.training_groups = {o.group for o in observations}
        self.calibration_result = None
        if self.calibrate_physics:
            self.calibration_result = calibrate(self.config, observations)
            self.config = self.calibration_result.config
        km = np.array([o.route.distance_m / 1000 for o in observations])
        if (km <= 0).any():
            raise ValueError("Positive route distance required for learning")
        x = np.vstack([features(o, self.config.bike.crr) for o in observations])
        y = np.array([o.energy_wh for o in observations]) / km
        physical = self.physical(observations) / km
        residual = y - physical
        self.data = make_pipeline(StableScaler(), Ridge(alpha=2.0)).fit(x, y)
        self.residual = RandomForestRegressor(
            n_estimators=80, min_samples_leaf=3, max_features=0.85, random_state=self.seed, n_jobs=1
        ).fit(x, residual)
        self.gate.fit(x, residual)
        self.fitted = True
        self.observations = list(observations)
        self.quantiles.clear()
        self.signed_errors_wh_per_km.clear()
        self.interval_groups.clear()
        self.interval_observations.clear()
        return self

    def adapt(self, observation: Observation) -> dict[str, Any]:
        """Consume a new observed route causally, update physics, then retrain residuals.

        Previous conformal quantiles become stale and are discarded. Recalibrate
        them on fresh independent routes after any adaptation.
        """
        staged = deepcopy(self)
        update = staged._adapt_in_place(observation)
        self.__dict__ = staged.__dict__
        return update

    def _adapt_in_place(self, observation: Observation) -> dict[str, Any]:
        from bikeenergylab.calibration import SequentialCalibrator

        if not self.fitted:
            raise ValueError("Fit before sequential adaptation")
        if observation.group in (
            self.training_groups | self.interval_groups | self.invalidated_interval_groups
        ):
            raise ValueError(
                "Adaptation needs a new route group, disjoint from held-out interval calibration"
            )
        if not hasattr(self, "sequential"):
            self.sequential = SequentialCalibrator(self.config, self.parameter_names)
        update = self.sequential.update(observation)
        self.config = self.sequential.config
        history = self.observations + [observation]
        # Retarget old residuals using the updated physical parameters. Never reuse
        # a residual trained against a different physical model without rebuilding.
        old_mode = self.calibrate_physics
        self.invalidated_interval_groups.update(self.interval_groups)
        self.calibrate_physics = False
        try:
            self._fit_in_place(history)
        finally:
            self.calibrate_physics = old_mode
        update["intervals_invalidated"] = True
        return update

    def predict(
        self,
        observations: list[Observation],
        model: str = "M4",
        coverage: float | None = None,
        use_uncertainty_gate: bool = True,
        physical_energy_wh: np.ndarray | None = None,
    ) -> Prediction:
        if not self.fitted or not observations:
            raise ValueError("Fit model first and supply observations")
        x = np.vstack([features(o, self.config.bike.crr) for o in observations])
        km = np.array([o.route.distance_m / 1000 for o in observations])
        physical = (
            self.physical(observations)
            if physical_energy_wh is None
            else np.asarray(physical_energy_wh, dtype=float)
        )
        if physical.shape != km.shape or not np.isfinite(physical).all():
            raise ValueError("Physical energy override must contain one finite value per route")
        residual = self.residual.predict(x) * km
        ensemble = np.vstack([tree.predict(x) for tree in self.residual.estimators_])
        std = ensemble.std(axis=0) * km
        alpha, score = self.gate.evaluate(x, std / km if use_uncertainty_gate else None)
        if model == "M1":
            energy = physical
        elif model == "M2":
            energy = self.data.predict(x) * km
        elif model == "M3":
            energy = physical + residual
        elif model == "M4":
            energy = physical + alpha * residual
        else:
            raise ValueError(f"Unknown baseline {model}")
        # Clipping is inappropriate for signed net energy with regeneration.
        lower, upper = None, None
        if coverage is not None:
            key = (model, coverage)
            if key not in self.quantiles:
                raise ValueError("Calibrate intervals at this coverage on held-out routes first")
            width = self.quantiles[key] * km
            lower, upper = energy - width, energy + width
        return Prediction(energy, alpha, score, std, lower, upper)

    def calibrate_intervals(
        self, observations: list[Observation], coverages: tuple[float, ...] = (0.8, 0.95)
    ) -> None:
        if not self.fitted or not observations:
            raise ValueError("Fit first and provide independent interval calibration routes")
        groups = {o.group for o in observations}
        if groups & (self.training_groups | self.invalidated_interval_groups) or len(groups) != len(
            observations
        ):
            raise ValueError(
                "Interval calibration groups must be independent and disjoint from training"
            )
        for coverage in coverages:
            if not 0 < coverage < 1:
                raise ValueError("Coverage must be in (0,1)")
            if int(np.ceil((len(observations) + 1) * coverage)) > len(observations):
                raise ValueError("Too few held-out routes for requested finite-sample coverage")
        if not coverages:
            raise ValueError("Supply at least one interval coverage")
        km = np.array([o.route.distance_m / 1000 for o in observations])
        observed = np.array([o.energy_wh for o in observations])
        quantiles, errors = {}, {}
        for model in ["M1", "M2", "M3", "M4"]:
            errors[model] = (observed - self.predict(observations, model).energy_wh) / km
            scores = np.sort(np.abs(errors[model]))
            for coverage in coverages:
                rank = int(np.ceil((len(scores) + 1) * coverage))
                quantiles[(model, coverage)] = float(scores[rank - 1])
        self.quantiles = quantiles
        self.signed_errors_wh_per_km = errors
        self.interval_groups = groups
        self.interval_observations = list(observations)

    def annotate_simulation(self, result: Any, coverage: float = 0.95) -> Any:
        """Attach a full-route prediction once; retain the physical battery trace."""
        observation = Observation(result.route, 0, result.config, "prediction")
        physical = BikeModel(result.config).predict_energy(result.route)
        effective_coverage = coverage if ("M4", coverage) in self.quantiles else None
        prediction = self.predict(
            [observation], coverage=effective_coverage, physical_energy_wh=np.array([physical])
        )
        result.summary["CGPRA"] = {
            "full_route_energy_wh": float(prediction.energy_wh[0]),
            "physical_full_route_demand_wh": physical,
            "alpha": float(prediction.alpha[0]),
            "ood_score": float(prediction.ood_score[0]),
            "prediction_interval_wh": [
                float(prediction.lower_wh[0]),
                float(prediction.upper_wh[0]),
            ]
            if effective_coverage is not None
            else None,
            "coverage": effective_coverage,
            "interval_status": "calibrated"
            if effective_coverage is not None
            else "fresh independent interval calibration required",
            "scope": "requested full route; physical SOC trace is unchanged",
        }
        result.hybrid_model = self
        return result

    def save(self, directory: str | Path) -> Path:
        from .artifact import save_model

        return save_model(self, directory)

    @classmethod
    def load(cls, directory: str | Path) -> CGPRAModel:
        from .artifact import load_model

        return load_model(directory)

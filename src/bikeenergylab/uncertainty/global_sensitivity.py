"""Seeded elementary effects and variance sensitivity for independent bounded inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import qmc, spearmanr

from bikeenergylab import BikeModel, Config, Route


@dataclass
class SensitivityResult:
    indices: pd.DataFrame
    evaluations: pd.DataFrame
    protocol: dict

    def export(
        self, config: Config, route: Route, output: str | Path = "results", figures: bool = True
    ) -> Path:
        from bikeenergylab.io import create_run, write_json

        destination = create_run(
            output,
            config,
            {
                "route": route.frame,
                "sensitivity": self.indices,
                "evaluations": self.evaluations,
            },
        )
        write_json(destination / "protocol.json", self.protocol)
        if figures:
            from bikeenergylab.visualization import sensitivity_figures

            sensitivity_figures(self.indices, self.protocol["method"], destination / "figures")
        return destination


def analyze_global(
    evaluate: Callable[[np.ndarray], float],
    bounds: dict[str, list[float]],
    method: str = "sobol",
    n: int = 256,
    seed: int = 42,
    levels: int = 6,
    bootstrap: int = 200,
) -> SensitivityResult:
    """Analyze a deterministic scalar response on a rectangular uniform input law.

    Sobol uses scrambled 2D-dimensional base-2 designs, Saltelli's centered
    first-order estimator and Jansen's total-effect estimator. Bootstrap intervals
    describe finite-design estimation uncertainty. Indices are never clipped.
    Morris effects are per unit change in normalized input, in output units.
    Spearman describes marginal association, not a causal effect.
    """
    names = list(bounds)
    limits = np.asarray(list(bounds.values()), dtype=float)
    if not names or limits.shape != (len(names), 2) or not np.isfinite(limits).all():
        raise ValueError("Supply finite [low, high] bounds for each input")
    if (limits[:, 1] <= limits[:, 0]).any():
        raise ValueError("Each upper bound must exceed its lower bound")
    if not isinstance(n, int) or n < 2 or not isinstance(bootstrap, int) or bootstrap < 2:
        raise ValueError("n and bootstrap must be integers >=2")
    rng = np.random.default_rng(seed)
    dimension, records = len(names), []

    def response(u: np.ndarray, design: str, index: int) -> float:
        values = limits[:, 0] + u * (limits[:, 1] - limits[:, 0])
        output = float(evaluate(values))
        if not np.isfinite(output):
            raise ValueError("Sensitivity response must be finite")
        records.append(
            {"design": design, "index": index, **dict(zip(names, values)), "response": output}
        )
        return output

    protocol = {
        "method": method,
        "seed": seed,
        "n": n,
        "bounds": bounds,
        "input_law": "independent uniform bounded inputs",
        "response": "user supplied deterministic scalar",
        "limitations": "Conditional on bounds and model; no causal attribution",
    }
    if method == "morris":
        if not isinstance(levels, int) or levels < 4 or levels % 2:
            raise ValueError("Morris levels must be an even integer >=4")
        delta = levels / (2 * (levels - 1))
        effects = np.zeros((n, dimension))
        for trajectory in range(n):
            directions = rng.choice([-1, 1], dimension)
            u = rng.integers(0, levels // 2, dimension) / (levels - 1)
            u += np.where(directions < 0, delta, 0)
            previous = response(u, f"trajectory-{trajectory}", 0)
            for step, j in enumerate(rng.permutation(dimension), 1):
                u = u.copy()
                u[j] += directions[j] * delta
                current = response(u, f"trajectory-{trajectory}", step)
                effects[trajectory, j] = (current - previous) / (directions[j] * delta)
                previous = current
        indices = pd.DataFrame(
            {
                "parameter": names,
                "mu": effects.mean(axis=0),
                "mu_star": np.abs(effects).mean(axis=0),
                "sigma": effects.std(axis=0, ddof=1),
            }
        )
        protocol.update(
            levels=levels,
            normalized_step=delta,
            estimator="Morris randomized one-factor trajectories",
            index_units="response units per normalized input unit",
        )
    elif method == "sobol":
        if n & (n - 1):
            raise ValueError("Sobol n must be a power of two")
        design = qmc.Sobol(d=2 * dimension, scramble=True, seed=seed).random_base2(
            n.bit_length() - 1
        )
        a, b = design[:, :dimension], design[:, dimension:]
        ya = np.array([response(u, "A", i) for i, u in enumerate(a)])
        yb = np.array([response(u, "B", i) for i, u in enumerate(b)])
        yab = []
        for j, name in enumerate(names):
            ab = a.copy()
            ab[:, j] = b[:, j]
            yab.append(np.array([response(u, f"AB-{name}", i) for i, u in enumerate(ab)]))
        yab = np.asarray(yab)

        def estimate(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            aa, bb, ab = ya[rows], yb[rows], yab[:, rows]
            variance = np.var(np.r_[aa, bb], ddof=1)
            if variance <= np.finfo(float).eps * max(1.0, np.mean(np.r_[aa, bb] ** 2)):
                return np.full(dimension, np.nan), np.full(dimension, np.nan)
            centered_b = bb - np.mean(np.r_[aa, bb])
            first = np.mean(centered_b * (ab - aa), axis=1) / variance
            total = np.mean((aa - ab) ** 2, axis=1) / (2 * variance)
            return first, total

        first, total = estimate(np.arange(n))
        resampled = np.array([estimate(rng.integers(n, size=n)) for _ in range(bootstrap)])
        if np.isfinite(resampled).all():
            lo, hi = np.quantile(resampled, [0.025, 0.975], axis=0)
        else:
            lo = hi = np.full((2, dimension), np.nan)
        indices = pd.DataFrame(
            {
                "parameter": names,
                "S1": first,
                "ST": total,
                "S1_low95": lo[0],
                "S1_high95": hi[0],
                "ST_low95": lo[1],
                "ST_high95": hi[1],
            }
        )
        protocol.update(
            estimator="centered Saltelli first order; Jansen total effect",
            bootstrap_replicates=bootstrap,
            variance_defined=bool(np.isfinite(first).all()),
            interval_scope="paired-row bootstrap; approximate finite-design uncertainty",
            index_units="variance fraction; finite estimates can lie outside [0,1]",
        )
    elif method == "spearman":
        design = qmc.LatinHypercube(d=dimension, seed=seed).random(n)
        y = np.array([response(u, "latin-hypercube", i) for i, u in enumerate(design)])
        correlations = [
            float(spearmanr(design[:, j], y).statistic) if np.ptp(y) > 0 else np.nan
            for j in range(dimension)
        ]
        indices = pd.DataFrame({"parameter": names, "spearman_rho": correlations})
        protocol.update(estimator="Spearman marginal rank correlation", index_units="unitless")
    else:
        raise ValueError("method must be morris, sobol or spearman")
    protocol["evaluations"] = len(records)
    return SensitivityResult(indices, pd.DataFrame(records), protocol)


def default_bounds(config: Config, route: Route) -> dict[str, list[float]]:
    speed = float(np.average(route.frame.speed_mps, weights=route.frame.dt_s))
    return {
        "bike.crr": [max(0.0001, config.bike.crr * 0.7), max(0.0002, config.bike.crr * 1.3)],
        "bike.cda_m2": [config.bike.cda_m2 * 0.7, max(0.01, config.bike.cda_m2 * 1.3)],
        "rider.mass_kg": [max(1e-6, config.rider.mass_kg * 0.8), config.rider.mass_kg * 1.2],
        "rider.human_power_w": [
            max(0, config.rider.human_power_w - 30),
            config.rider.human_power_w + 30,
        ],
        "route.speed_mps": [speed * 0.8, speed * 1.2],
        "environment.wind_mps": [config.environment.wind_mps - 2, config.environment.wind_mps + 2],
        "environment.temperature_c": [
            max(-100, config.environment.temperature_c - 5),
            min(100, config.environment.temperature_c + 5),
        ],
        "motor.efficiency": [
            max(1e-6, config.motor.efficiency - 0.08),
            min(1, config.motor.efficiency + 0.08),
        ],
    }


def physical_sensitivity(
    config: Config,
    route: Route,
    method: str = "sobol",
    bounds: dict[str, list[float]] | None = None,
    **options,
) -> SensitivityResult:
    """Electrical full-route demand sensitivity, before battery depletion constraints."""
    bounds = bounds if bounds is not None else default_bounds(config, route)
    for path in bounds:
        override = {
            "environment.wind_mps": "wind_mps",
            "environment.temperature_c": "temperature_c",
            "rider.human_power_w": "human_power_w",
        }.get(path)
        if override and override in route.frame:
            raise ValueError(f"{path} is overridden by the route profile")
        if path == "motor.efficiency" and config.motor.efficiency_map:
            raise ValueError("motor.efficiency is overridden by its efficiency map")

    def evaluate(values: np.ndarray) -> float:
        cfg, sample = config, route
        for path, value in zip(bounds, values):
            if path == "route.speed_mps":
                if value <= 0:
                    raise ValueError("Speed sensitivity requires positive bounds")
                frame = route.frame.copy()
                average = np.average(frame.speed_mps, weights=frame.dt_s)
                frame["speed_mps"] *= value / average
                frame["dt_s"] = np.divide(
                    frame.length_m,
                    frame.speed_mps,
                    out=frame.dt_s.to_numpy().copy(),
                    where=frame.speed_mps > 0,
                )
                sample = Route(
                    frame.drop(columns="acceleration_mps2"), route.name, route.provenance
                )
            else:
                cfg = cfg.changed(path, float(value))
        return BikeModel(cfg).predict_energy(sample)

    result = analyze_global(evaluate, bounds, method, **options)
    result.protocol["response"] = (
        "full-route requested electrical energy [Wh] before battery constraints"
    )
    result.protocol["limitations"] += (
        "; controller power limits remain active; inspect drive feasibility separately"
    )
    return result

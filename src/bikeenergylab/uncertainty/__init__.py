"""Seeded uncertainty propagation and mission feasibility on a repeated route."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter
from scipy.stats import spearmanr, truncnorm

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.battery import BatteryState, temperature_multiplier
from bikeenergylab.calibration import Observation


@dataclass
class UncertaintyResult:
    samples: pd.DataFrame
    summary: dict[str, Any]
    config: Config
    route: Route
    hybrid_model: Any = None
    trajectory_bands: pd.DataFrame | None = None

    def export(self, output: str | Path = "results", figures: bool = True) -> Path:
        from bikeenergylab.io import create_run, write_json
        from bikeenergylab.visualization import uncertainty_figures

        tables = {"route": self.route.frame, "distributions": self.samples}
        if self.trajectory_bands is not None:
            tables["trajectory_bands"] = self.trajectory_bands
        destination = create_run(output, self.config, tables)
        write_json(destination / "summary.json", self.summary)
        pd.DataFrame([{k: v for k, v in self.summary.items() if not isinstance(v, dict)}]).to_csv(
            destination / "metrics.csv", index=False
        )
        if self.hybrid_model is not None:
            self.hybrid_model.save(destination / "hybrid_model")
        if figures:
            uncertainty_figures(self.samples, destination / "figures", self.trajectory_bands)
        (destination / "logs" / "run.log").write_text(
            "Seeded Monte Carlo completed\n", encoding="utf-8"
        )
        return destination


def _draw(spec: dict[str, Any], rng: np.random.Generator) -> float:
    distribution = spec.get("distribution", "normal")
    if distribution == "uniform":
        low, high = spec["low"], spec["high"]
        if not np.isfinite([low, high]).all() or low >= high:
            raise ValueError("Uniform bounds must be finite and increasing")
        return float(rng.uniform(low, high))
    if distribution == "normal":
        mean, std = spec["mean"], spec["std"]
        low, high = spec.get("low", -np.inf), spec.get("high", np.inf)
        if not np.isfinite([mean, std]).all() or std < 0 or low >= high:
            raise ValueError("Invalid normal distribution")
        if std == 0:
            if not low <= mean <= high:
                raise ValueError("Degenerate mean lies outside bounds")
            return float(mean)
        return float(
            truncnorm.rvs(
                (low - mean) / std, (high - mean) / std, loc=mean, scale=std, random_state=rng
            )
        )
    raise ValueError(f"Unsupported distribution: {distribution}")


def repeated_route_range(
    model: BikeModel, route: Route, max_distance_km: float = 500
) -> tuple[float, bool]:
    """Integrate actual signed battery demand until reserve or a feasibility limit.

    The route is repeated from its last segment back to the first with no invented
    transition; callers must use a cycle-compatible speed/elevation profile. A cap
    yields a right-censored distance, never an asserted infinite range.
    """
    cfg = model.config
    sampled = route.subdivide(cfg.simulation.timestep_s) if cfg.battery.model == "ecm" else route
    f = model.operating_profile(sampled)
    deficit = f.power_wheel_w - f.power_human_w - f.power_motor_requested_w
    if (deficit > 1e-7).any():
        # The requested route cannot be sustained; range inference is not admissible.
        return 0.0, False
    state = BatteryState(cfg.battery)
    distance = 0.0
    power = f.power_battery_requested_w.to_numpy()
    durations = f.dt_s.to_numpy()
    speeds = f.speed_mps.to_numpy()
    temperatures = f.temperature_c.to_numpy()
    maximum = max_distance_km * 1000
    while distance < maximum:
        for requested, dt, speed, temp in zip(power, durations, speeds, temperatures):
            if speed > 0:
                dt = min(dt, (maximum - distance) / speed)
            step = state.step(float(requested), float(dt), float(temp))
            if requested > 0 and step.power_w < requested - 1e-7:
                return distance / 1000, False
            distance += speed * step.dt_s
            if step.dt_s < dt - 1e-9 or state.soc <= cfg.battery.soc_min + 1e-12:
                return distance / 1000, False
            if distance >= maximum - 1e-7:
                return max_distance_km, True
    return distance / 1000, True


def monte_carlo(
    config: Config,
    route: Route,
    n_samples: int = 100,
    seed: int = 42,
    distributions: dict[str, dict[str, Any]] | None = None,
    reserve_soc: float | None = None,
    target_range_km: float | None = None,
    max_distance_km: float = 500,
    joint_parameters: dict[str, Any] | None = None,
    hybrid_model: Any = None,
    predictive_baseline: str = "M4",
) -> UncertaintyResult:
    if n_samples < 2 or max_distance_km <= 0:
        raise ValueError("Need >=2 samples and positive range horizon")
    reserve = config.battery.soc_min if reserve_soc is None else reserve_soc
    if not config.battery.soc_min <= reserve <= config.battery.soc_max:
        raise ValueError("Mission reserve lies outside allowed SOC window")
    distributions = distributions or {}
    if hybrid_model is not None and predictive_baseline not in hybrid_model.signed_errors_wh_per_km:
        raise ValueError(
            "Predictive propagation requires fresh independent held-out error calibration"
        )
    joint = joint_parameters or {}
    if joint:
        names = joint["parameters"]
        mean = np.asarray(joint["mean"], float)
        covariance = np.asarray(joint["covariance"], float)
        lower, upper = np.asarray(joint["low"], float), np.asarray(joint["high"], float)
        if len(set(names)) != len(names) or set(names) & set(distributions):
            raise ValueError("Joint parameters must be unique and disjoint from independent draws")
        if any(key.startswith("route.") for key in names):
            raise ValueError("Joint Gaussian supports configuration parameters only")
        if (
            mean.shape != (len(names),)
            or lower.shape != mean.shape
            or upper.shape != mean.shape
            or covariance.shape != (len(names), len(names))
        ):
            raise ValueError("Joint Gaussian dimensions do not match parameter names")
        if (
            not np.isfinite([mean, lower, upper]).all()
            or not np.isfinite(covariance).all()
            or (lower >= upper).any()
        ):
            raise ValueError("Invalid joint parameter distribution")
        if (
            not np.allclose(covariance, covariance.T)
            or np.linalg.eigvalsh(covariance).min() < -1e-12
        ):
            raise ValueError("Joint covariance must be symmetric positive semidefinite")
    rng = np.random.default_rng(seed)
    records = []
    fractions = np.linspace(0, 1, 51)
    soc_paths, energy_paths = [], []
    prediction_observations = []
    profile_overrides = {
        "environment.wind_mps": "wind_mps",
        "environment.temperature_c": "temperature_c",
        "rider.human_power_w": "human_power_w",
        "motor.assist_level": "assist_level",
        "simulation.auxiliary_power_w": "auxiliary_power_w",
    }
    for key in set(distributions) | set(joint.get("parameters", [])):
        if key in profile_overrides and profile_overrides[key] in route.frame:
            raise ValueError(
                f"{key} is overridden by route profile; vary route.{profile_overrides[key]} instead"
            )
    for _ in range(n_samples):
        cfg = Config.from_dict(config.to_dict())
        frame = route.frame.copy()
        values = {}
        if joint:
            for attempt in range(10000):
                draw = rng.multivariate_normal(mean, covariance)
                if np.all((draw >= lower) & (draw <= upper)):
                    break
            else:
                raise ValueError(
                    "Joint bounded Gaussian acceptance too low; revise mean/covariance/bounds"
                )
            for key, value in zip(names, draw):
                cfg = cfg.changed(key, float(value))
                values[key] = float(value)
        for key, specification in distributions.items():
            if key == "route.elevation_noise_m":
                if "route.grade" in distributions:
                    raise ValueError("Choose elevation noise or sampled grade, not both")
                original = frame.elevation_m.to_numpy()
                initial = (
                    original[0] - np.sin(np.arctan(frame.grade.iloc[0])) * frame.length_m.iloc[0]
                )
                elevation = np.r_[initial, original]
                noise = np.array([_draw(specification, rng) for _ in elevation])
                noisy = median_filter(elevation + noise, size=3, mode="nearest")
                horizontal = frame.length_m.to_numpy() * np.cos(np.arctan(frame.grade.to_numpy()))
                dh = np.diff(noisy)
                dh[horizontal == 0] = 0.0  # Stops have no physical elevation displacement.
                grades = np.divide(dh, horizontal, out=np.zeros_like(dh), where=horizontal > 0)
                lengths = np.hypot(horizontal, dh)
                frame["length_m"], frame["grade"] = lengths, grades
                frame["dt_s"] = np.divide(
                    lengths,
                    frame.speed_mps,
                    out=frame.dt_s.to_numpy().copy(),
                    where=frame.speed_mps > 0,
                )
                frame["elevation_m"] = noisy[0] + np.cumsum(dh)
                frame = frame.drop(columns="acceleration_mps2", errors="ignore")
                values[key] = float(np.sqrt(np.mean(noise**2)))
                continue
            value = _draw(specification, rng)
            values[key] = value
            if key.startswith("route."):
                column = key.split(".", 1)[1]
                if column not in {
                    "speed_mps",
                    "wind_mps",
                    "temperature_c",
                    "human_power_w",
                    "grade",
                    "auxiliary_power_w",
                }:
                    raise ValueError(f"Unsupported operational uncertainty {key}")
                frame[column] = value
                if column == "speed_mps":
                    if value <= 0:
                        raise ValueError("Sampled route speed must be positive")
                    frame["dt_s"] = frame.length_m / value
                    frame = frame.drop(columns="acceleration_mps2", errors="ignore")
                if column == "grade":
                    frame = frame.drop(columns="elevation_m", errors="ignore")
            else:
                cfg = cfg.changed(key, value)
        sampled = Route(frame, route.name, route.provenance)
        model = BikeModel(cfg)
        profile = model.operating_profile(sampled)
        demand_wh = float(np.sum(profile.power_battery_requested_w * profile.dt_s) / 3600)
        # For constant-power energy/SOC models coarse interval integration is exact
        # up to charging saturation; ECM retains the configured time resolution.
        mission_cfg = (
            cfg
            if cfg.battery.model == "ecm"
            else cfg.changed("simulation.timestep_s", float(sampled.frame.dt_s.max()))
        )
        result = BikeModel(mission_cfg).simulate(sampled)
        if len(result.trace):
            positions = np.r_[0, result.trace.distance_m.to_numpy() / sampled.distance_m]
            if result.summary["completed_route"]:
                positions[-1] = 1.0
            soc_paths.append(
                np.interp(
                    fractions,
                    positions,
                    np.r_[cfg.battery.initial_soc, result.trace.soc],
                    right=np.nan,
                )
            )
            energy_paths.append(
                np.interp(
                    fractions, positions, np.r_[0, result.trace.cumulative_energy_wh], right=np.nan
                )
            )
        else:
            soc_path, energy_path = np.full(51, np.nan), np.full(51, np.nan)
            soc_path[0], energy_path[0] = cfg.battery.initial_soc, 0
            soc_paths.append(soc_path)
            energy_paths.append(energy_path)
        range_km, censored = repeated_route_range(model, sampled, max_distance_km)
        success = result.summary["feasible"] and result.summary["final_soc"] >= reserve - 1e-12
        records.append(
            dict(
                energy_wh=result.summary["energy_wh"],
                full_route_demand_wh=demand_wh,
                soc_final=result.summary["final_soc"],
                range_km=range_km,
                range_right_censored=censored,
                completed_route=result.summary["completed_route"],
                feasible=result.summary["feasible"],
                mission_success=bool(success),
                **values,
            )
        )
        if hybrid_model is not None:
            prediction_observations.append(Observation(sampled, 0, cfg, f"mc-{len(records)}"))
            scales = np.array(
                [
                    temperature_multiplier(cfg.battery.capacity_temperature_curve, t)
                    for t in profile.temperature_c
                ]
            )
            supported = (
                cfg.battery.model in {"energy", "soc"}
                and (profile.power_battery_requested_w >= -1e-9).all()
                and np.allclose(scales, scales[0], rtol=0, atol=1e-12)
            )
            records[-1].update(
                energy_budget_supported=bool(supported),
                energy_budget_wh=(
                    cfg.battery.nominal_energy_wh
                    * cfg.battery.usable_fraction
                    * scales[0]
                    * (cfg.battery.initial_soc - reserve)
                    if supported
                    else np.nan
                ),
                minimum_energy_wh=(
                    float(np.sum(profile.power_aux_w * profile.dt_s) / 3600)
                    if not cfg.regeneration.enabled
                    else 0.0
                ),
                baseline_power_feasible=bool(
                    (
                        profile.power_wheel_w
                        - profile.power_human_w
                        - profile.power_motor_requested_w
                        <= 1e-7
                    ).all()
                    and (
                        profile.power_battery_requested_w
                        <= cfg.battery.max_current_a * cfg.battery.nominal_voltage_v + 1e-7
                    ).all()
                ),
            )
    samples = pd.DataFrame(records)
    bands = pd.DataFrame(
        {
            "route_fraction": fractions,
            "reference_distance_m": fractions * route.distance_m,
            "n_reached": np.isfinite(soc_paths).sum(axis=0),
        }
    )
    for key, paths in [("soc", soc_paths), ("energy_wh", energy_paths)]:
        array = np.asarray(paths)
        quantiles = np.full((3, 51), np.nan)
        valid = np.isfinite(array).any(axis=0)
        quantiles[:, valid] = np.nanquantile(array[:, valid], [0.025, 0.5, 0.975], axis=0)
        for label, values in zip(["low95", "median", "high95"], quantiles):
            bands[f"{key}_{label}"] = values

    def statistics(column: str) -> dict[str, float]:
        vals = samples[column].to_numpy()
        return {
            "mean": float(vals.mean()),
            "median": float(np.median(vals)),
            "sd": float(vals.std(ddof=1)),
            "p2_5": float(np.quantile(vals, 0.025)),
            "p97_5": float(np.quantile(vals, 0.975)),
        }

    probability = float(samples.mission_success.mean())
    # Wilson interval measures Monte Carlo sampling error, not model correctness.
    z, n = 1.96, n_samples
    center = (probability + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(probability * (1 - probability) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    summary = {
        "n_samples": n_samples,
        "seed": seed,
        "reserve_soc": reserve,
        "mission_probability": probability,
        "mission_probability_mc_interval95": [max(0, center - half), min(1, center + half)],
        "range_km": statistics("range_km"),
        "energy_wh": statistics("energy_wh"),
        "full_route_demand_wh": statistics("full_route_demand_wh"),
        "soc_final": statistics("soc_final"),
        "range_censoring_fraction": float(samples.range_right_censored.mean()),
        "range_horizon_km": max_distance_km,
        "distribution_scope": "physical parameters and operational assumptions; no learned predictive-error component",
        "interval_interpretation": "central 95% simulation intervals conditional on specified distributions, not confidence intervals for reality",
        "trajectory_bands_scope": "Physical endpoint interpolation on normalized route progress, conditional on samples reaching each point; n_reached reports attrition, no extrapolation after depletion",
    }
    if hybrid_model is not None:
        prediction = hybrid_model.predict(
            prediction_observations,
            model=predictive_baseline,
            physical_energy_wh=samples.full_route_demand_wh.to_numpy(),
        )
        # Separate stream preserves identical physical draws with/without learning.
        error_rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(1)[0])
        pool = hybrid_model.signed_errors_wh_per_km[predictive_baseline]
        sampled_error = error_rng.choice(pool, size=n_samples)
        distances_km = np.array([o.route.distance_m / 1000 for o in prediction_observations])
        samples["predictive_error_wh_per_km"] = sampled_error
        samples["predictive_center_wh"] = prediction.energy_wh
        samples["predictive_energy_wh"] = prediction.energy_wh + sampled_error * distances_km
        samples["alpha"] = prediction.alpha
        samples["ood_score"] = prediction.ood_score
        admissible = samples.predictive_energy_wh >= samples.minimum_energy_wh - 1e-9
        identified = samples.energy_budget_supported & admissible
        success = identified & (samples.predictive_energy_wh <= samples.energy_budget_wh + 1e-9)
        samples["predictive_energy_admissible"] = admissible.astype("boolean").mask(
            ~samples.energy_budget_supported
        )
        samples["energy_budget_success"] = success.astype("boolean").mask(~identified)
        known, unknown = float(success.mean()), float((~identified).mean())
        summary["predictive_energy"] = {
            "baseline": predictive_baseline,
            "energy_wh": statistics("predictive_energy_wh"),
            "held_out_error_routes": len(pool),
            "mean_alpha": float(samples.alpha.mean()),
            "outside_support_fraction": float((samples.ood_score > 1).mean()),
            "inadmissible_energy_fraction": float(
                (~admissible & samples.energy_budget_supported).mean()
            ),
            "admissibility_scope": "Auxiliary-energy lower bound applies only within supported nonnegative-demand budget domain; signed regenerative energy outside it is unclassified",
            "energy_budget_probability": known if unknown == 0 else None,
            "energy_budget_probability_bounds": [known, min(1.0, known + unknown)],
            "energy_budget_unidentified_fraction": unknown,
            "baseline_power_feasible_fraction": float(samples.baseline_power_feasible.mean()),
            "baseline_power_check_scope": "Prescribed controller demand and nominal-voltage current cap; not dynamic battery certification",
            "error_assumption": "Uncentered held-out signed Wh/km errors are bootstrapped independently of input draws and assumed transportable; not reduced by alpha",
            "interpretation": "Energy-budget screening only; no learned dynamic SOC, current/voltage feasibility or mission-completion guarantee",
            "support_policy": "OOD scores are exported; held-out errors have no guaranteed calibration under shifted conditions",
            "budget_scope": "Energy/SOC battery with constant effective capacity and nonnegative requested battery demand; invalid energy draws and unsupported cases remain unidentified",
            "double_counting": "Held-out error may already contain parameter/measurement uncertainty; input priors are explicit conditional assumptions, not an identified joint posterior",
        }
        summary["distribution_scope"] = (
            "Physical input propagation plus optional empirical full-route predictive-energy errors; physical mission/range statistics retain their original meaning"
        )
    if target_range_km is not None:
        if target_range_km >= max_distance_km:
            raise ValueError("Target range must lie below censoring horizon")
        summary["probability_range_above_target"] = float(
            (samples.range_km > target_range_km).mean()
        )
    run_config = Config.from_dict(config.to_dict())
    run_config.experiment["seed"] = seed
    from bikeenergylab.io import json_safe

    run_config.uncertainty = json_safe(
        {
            "n_samples": n_samples,
            "seed": seed,
            "distributions": distributions,
            "reserve_soc": reserve,
            "target_range_km": target_range_km,
            "max_distance_km": max_distance_km,
            "joint_parameters": joint_parameters,
        }
    )
    if hybrid_model is not None:
        run_config.uncertainty.update(
            model_artifact="hybrid_model", predictive_baseline=predictive_baseline
        )
    if "route.elevation_noise_m" in distributions:
        summary["elevation_noise_processing"] = (
            "independent knot perturbations, three-point median filter, preserve horizontal distance"
        )
    return UncertaintyResult(samples, summary, run_config, route, hybrid_model, bands)


def spearman_sensitivity(result: UncertaintyResult) -> pd.DataFrame:
    columns = [key for key in result.samples if "." in key]
    rows = []
    for key in columns:
        if result.samples[key].nunique() < 2 or result.samples.energy_wh.nunique() < 2:
            coefficient, pvalue = np.nan, np.nan
        else:
            coefficient, pvalue = spearmanr(result.samples[key], result.samples.energy_wh)
        rows.append({"parameter": key, "spearman_energy": coefficient, "pvalue": pvalue})
    return pd.DataFrame(rows)

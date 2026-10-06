"""Prescribed-speed physical model with explicit feasibility and energy balance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .battery import BatteryState, temperature_multiplier
from .config import Config
from .motor import EfficiencyMap
from .physics import air_density, longitudinal_forces
from .routes import Route

LOGGER = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    trace: pd.DataFrame
    summary: dict[str, Any]
    config: Config
    route: Route
    hybrid_model: Any = None

    def export(self, output: str | Path = "results", figures: bool = True) -> Path:
        from .io import export_simulation

        return export_simulation(self, output, figures)


class BikeModel:
    def __init__(self, config: Config | None = None, **sections: Any) -> None:
        if config is not None and sections:
            raise ValueError("Use a Config or keyword sections, not both")
        self.config = config or Config.from_dict(sections)
        self.config.validate()

    def operating_profile(self, route: Route) -> pd.DataFrame:
        """Compute forces and requested motor/battery powers before state integration."""
        cfg = self.config
        cfg.validate()
        f = route.frame.copy()

        def column(name: str, default: float) -> np.ndarray:
            return f[name].to_numpy(float) if name in f else np.full(len(f), default)

        v = f.speed_mps.to_numpy()
        temperature = column("temperature_c", cfg.environment.temperature_c)
        wind = column("wind_mps", cfg.environment.wind_mps)
        density = cfg.environment.air_density_kgm3
        rho = air_density(temperature, cfg.environment.pressure_pa) if density is None else density
        crr = np.array(
            [
                cfg.bike.crr if s == "default" else cfg.bike.surface_crr.get(s, np.nan)
                for s in f.surface
            ]
        )
        if np.isnan(crr).any():
            raise ValueError("Unknown surface: define its Crr explicitly")
        forces = longitudinal_forces(
            cfg.total_mass_kg,
            crr,
            cfg.bike.cda_m2,
            v,
            f.grade.to_numpy(),
            f.acceleration_mps2.to_numpy(),
            wind,
            rho,
        )
        for name, values in [
            ("rolling", forces.rolling_n),
            ("grade", forces.grade_n),
            ("aero", forces.aero_n),
            ("acceleration", forces.acceleration_n),
        ]:
            f[f"force_{name}_n"] = values
            f[f"power_{name}_w"] = values * v
        wheel = forces.total_n * v
        human = column("human_power_w", cfg.rider.human_power_w)
        if cfg.rider.mode == "conditions" and "human_power_w" not in f:
            cadence = column("cadence_rpm", cfg.rider.cadence_reference_rpm)
            human = np.maximum(
                0, human + cfg.rider.grade_gain_w * np.maximum(f.grade.to_numpy(), 0)
            )
            human *= np.clip(cadence / cfg.rider.cadence_reference_rpm, 0, 1.5)
            human *= np.exp(-cfg.rider.fatigue_per_hour * f.time_s.to_numpy() / 3600)
        human_wheel = np.minimum(human * cfg.bike.drivetrain_efficiency, np.maximum(wheel, 0))
        human_wheel[v == 0] = 0
        demand = np.maximum(wheel - human_wheel, 0)
        assist = column("assist_level", cfg.motor.assist_level)
        command = (
            demand * assist
            if cfg.motor.assist_mode == "demand"
            else np.minimum(demand, human_wheel * assist * cfg.motor.assist_ratio)
        )
        omega = v / cfg.bike.wheel_radius_m
        controller_max = (
            np.minimum(cfg.motor.nominal_power_w, cfg.motor.max_torque_nm * omega)
            * cfg.bike.drivetrain_efficiency
        )
        motor = np.minimum(command, controller_max)
        motor[v >= cfg.motor.max_speed_mps] = 0.0
        eta = np.full(len(f), cfg.motor.efficiency)
        map_outside = np.zeros(len(f), bool)
        if cfg.motor.efficiency_map:
            torque = np.divide(
                motor / cfg.bike.drivetrain_efficiency,
                omega,
                out=np.zeros_like(motor),
                where=omega > 0,
            )
            eta, map_outside = EfficiencyMap.from_csv(cfg.motor.efficiency_map).evaluate(
                omega, torque
            )
        eta *= 1 + cfg.motor.temperature_coefficient_per_c * (temperature - 20)
        if (eta <= 0).any() or (eta > 1).any():
            raise ValueError("Configured temperature response produces invalid motor efficiency")
        aux = column("auxiliary_power_w", cfg.simulation.auxiliary_power_w)
        regen_electric = np.zeros(len(f))
        if cfg.regeneration.enabled:
            regen_electric = np.minimum(
                np.maximum(-wheel, 0) * cfg.regeneration.efficiency, cfg.regeneration.max_power_w
            )
            regen_electric[v < cfg.regeneration.min_speed_mps] = 0
        f["power_wheel_w"] = wheel
        f["power_human_w"] = human_wheel
        f["power_human_available_w"] = human
        f["power_motor_requested_w"] = motor
        f["motor_efficiency"] = eta
        f["motor_map_outside"] = map_outside
        f["power_aux_w"] = aux
        f["power_regen_requested_w"] = regen_electric
        f["power_battery_requested_w"] = (
            motor / (eta * cfg.bike.drivetrain_efficiency) + aux - regen_electric
        )
        f["temperature_c"], f["wind_mps"], f["assist_level"] = temperature, wind, assist
        return f

    def predict_energy(self, route: Route) -> float:
        """Unconstrained route electrical demand in Wh, suitable for calibration.

        Controller limits apply; battery SOC saturation does not. For completed
        mission feasibility use simulate(), not this target alone.
        """
        f = self.operating_profile(route)
        return float(np.dot(f.power_battery_requested_w, f.dt_s) / 3600)

    def simulate(self, route: Route) -> SimulationResult:
        cfg = self.config
        sampled = route.subdivide(cfg.simulation.timestep_s)
        profile = self.operating_profile(sampled)
        battery = BatteryState(cfg.battery)
        records = []
        distance, time, energy = 0.0, 0.0, 0.0
        for row in profile.to_dict("records"):
            step = battery.step(row["power_battery_requested_w"], row["dt_s"], row["temperature_c"])
            if step.dt_s <= 1e-10:
                break
            dt = step.dt_s
            # Realized regenerative power is inferred from net battery absorption + auxiliaries.
            regen = min(row["power_regen_requested_w"], max(row["power_aux_w"] - step.power_w, 0))
            motor_electrical = max(0, step.power_w - row["power_aux_w"] + regen)
            motor = min(
                row["power_motor_requested_w"],
                motor_electrical * row["motor_efficiency"] * cfg.bike.drivetrain_efficiency,
            )
            supplied_aux = min(row["power_aux_w"], max(0, step.power_w + regen))
            motor_input = motor / cfg.bike.drivetrain_efficiency
            motor_loss = motor_electrical - motor_input
            regen_wheel = regen / cfg.regeneration.efficiency if cfg.regeneration.enabled else 0
            brake = max(0, -row["power_wheel_w"] - regen_wheel)
            deficit = max(0, row["power_wheel_w"] - row["power_human_w"] - motor)
            energy += step.power_w * dt / 3600
            distance += row["speed_mps"] * dt
            time += dt
            row.update(
                dt_s=dt,
                length_m=row["speed_mps"] * dt,
                distance_m=distance,
                time_s=time,
                soc=step.soc,
                voltage_v=step.voltage_v,
                current_a=step.current_a,
                power_battery_w=step.power_w,
                power_motor_w=motor,
                power_regen_w=regen,
                power_braking_w=brake,
                power_drivetrain_loss_w=motor_input - motor,
                power_motor_loss_w=motor_loss,
                power_regen_loss_w=regen_wheel - regen,
                power_unmet_w=deficit,
                power_aux_w=supplied_aux,
                power_aux_unmet_w=max(0, row["power_aux_w"] - supplied_aux),
                chemical_power_w=step.chemical_power_w,
                cumulative_energy_wh=energy,
                battery_limited=step.limited,
            )
            row["energy_balance_error_w"] = step.power_w - (
                row["power_wheel_w"]
                - row["power_human_w"]
                + brake
                - deficit
                + row["power_drivetrain_loss_w"]
                + motor_loss
                + row["power_regen_loss_w"]
                + supplied_aux
            )
            records.append(row)
            if dt < sampled.frame.dt_s.iloc[len(records) - 1] - 1e-9:
                break
        trace = pd.DataFrame(records)
        completed = distance >= route.distance_m - 1e-6 and time >= sampled.frame.dt_s.sum() - 1e-6
        unmet = float(np.dot(trace.power_unmet_w, trace.dt_s) / 3600) if len(trace) else 0.0
        aux_unmet = float(np.dot(trace.power_aux_unmet_w, trace.dt_s) / 3600) if len(trace) else 0.0
        feasible = bool(completed and unmet < 1e-6 and aux_unmet < 1e-6)
        consumption = energy / (distance / 1000) if distance > 0 else None
        scale = temperature_multiplier(
            cfg.battery.capacity_temperature_curve, cfg.environment.temperature_c
        )
        available = (
            cfg.battery.nominal_energy_wh
            * cfg.battery.usable_fraction
            * scale
            * (cfg.battery.initial_soc - cfg.battery.soc_min)
        )
        # Stationary-equivalent range is labeled separately from reached route distance.
        equivalent = (
            available / consumption
            if consumption and consumption > 0 and unmet < 1e-6 and aux_unmet < 1e-6
            else None
        )
        decomposition = {}
        if len(trace):
            for name in [
                "rolling",
                "grade",
                "aero",
                "acceleration",
                "human",
                "braking",
                "drivetrain_loss",
                "motor_loss",
                "regen_loss",
                "aux",
                "regen",
                "unmet",
            ]:
                decomposition[f"{name}_wh"] = float(
                    np.dot(trace[f"power_{name}_w"], trace.dt_s) / 3600
                )
        summary = {
            "energy_wh": energy,
            "distance_km": distance / 1000,
            "route_distance_km": route.distance_m / 1000,
            "duration_s": time,
            "final_soc": battery.soc,
            "wh_per_km": consumption,
            "completed_route": bool(completed),
            "feasible": feasible,
            "unmet_mechanical_energy_wh": unmet,
            "available_energy_wh": available,
            "unmet_auxiliary_energy_wh": aux_unmet,
            "stationary_equivalent_range_km": equivalent,
            "decomposition": decomposition,
            "max_energy_balance_error_w": float(trace.energy_balance_error_w.abs().max())
            if len(trace)
            else 0,
            "battery_model": cfg.battery.model,
        }
        if not feasible:
            LOGGER.warning("Prescribed route is incomplete or has insufficient drive power")
        return SimulationResult(trace, summary, cfg, route)

    def calibrate(self, data: Any, **options: Any) -> Any:
        from .calibration import calibrate

        result = calibrate(self.config, data, **options)
        self.config = result.config
        return result

    def predict_range(self, route: Route, **options: Any) -> Any:
        from .uncertainty import monte_carlo

        return monte_carlo(self.config, route, **options)

    def predict_mission_probability(self, route: Route, **options: Any) -> Any:
        return self.predict_range(route, **options)

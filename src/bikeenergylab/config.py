"""Validated, serializable scientific configuration; defaults are assumptions."""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Bicycle:
    mass_kg: float = 25.0
    cargo_kg: float = 0.0
    cda_m2: float = 0.55
    crr: float = 0.006
    wheel_radius_m: float = 0.35
    drivetrain_efficiency: float = 0.96
    surface_crr: dict[str, float] = field(
        default_factory=lambda: {
            "asphalt": 0.006,
            "concrete": 0.007,
            "gravel": 0.012,
            "dirt": 0.018,
        }
    )


@dataclass
class Rider:
    mass_kg: float = 75.0
    human_power_w: float = 100.0
    mode: str = "constant"
    grade_gain_w: float = 0.0
    cadence_reference_rpm: float = 75.0
    fatigue_per_hour: float = 0.0


@dataclass
class Motor:
    nominal_power_w: float = 500.0
    efficiency: float = 0.82
    assist_level: float = 1.0
    assist_ratio: float = 4.0
    assist_mode: str = "demand"
    max_torque_nm: float = 80.0
    max_speed_mps: float = 12.0
    efficiency_map: str | None = None
    temperature_coefficient_per_c: float = 0.0


@dataclass
class Battery:
    nominal_energy_wh: float = 500.0
    usable_fraction: float = 0.95
    initial_soc: float = 0.90
    soc_min: float = 0.10
    soc_max: float = 0.95
    model: str = "soc"
    nominal_voltage_v: float = 36.0
    capacity_ah: float = 13.8888888889
    max_current_a: float = 25.0
    max_charge_current_a: float = 8.0
    min_voltage_v: float = 28.0
    r0_ohm: float = 0.10
    r1_ohm: float = 0.05
    c1_f: float = 2000.0
    ocv_soc: list[float] = field(default_factory=lambda: [0.0, 1.0])
    ocv_voltage_v: list[float] = field(default_factory=lambda: [30.0, 42.0])
    capacity_temperature_curve: list[list[float]] = field(default_factory=list)
    resistance_temperature_curve: list[list[float]] = field(default_factory=list)


@dataclass
class Environment:
    temperature_c: float = 20.0
    wind_mps: float = 0.0
    pressure_pa: float = 101325.0
    air_density_kgm3: float | None = None


@dataclass
class Regeneration:
    enabled: bool = False
    efficiency: float = 0.60
    max_power_w: float = 150.0
    min_speed_mps: float = 2.0


@dataclass
class Simulation:
    timestep_s: float = 1.0
    auxiliary_power_w: float = 5.0


@dataclass
class Config:
    bike: Bicycle = field(default_factory=Bicycle)
    rider: Rider = field(default_factory=Rider)
    motor: Motor = field(default_factory=Motor)
    battery: Battery = field(default_factory=Battery)
    environment: Environment = field(default_factory=Environment)
    regeneration: Regeneration = field(default_factory=Regeneration)
    simulation: Simulation = field(default_factory=Simulation)
    experiment: dict[str, Any] = field(default_factory=lambda: {"name": "flat_route", "seed": 42})
    route: dict[str, Any] = field(
        default_factory=lambda: {
            "kind": "synthetic",
            "distance_m": 10000.0,
            "speed_mps": 5.0,
            "grade": 0.0,
        }
    )
    uncertainty: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Config:
        """Reject misspelled parameters instead of ignoring them."""
        if not isinstance(values, dict):
            raise ValueError("Configuration must be a mapping")
        unknown = set(values) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown configuration sections: {sorted(unknown)}")
        result = cls()
        for name, value in values.items():
            existing = getattr(result, name)
            if hasattr(existing, "__dataclass_fields__"):
                if not isinstance(value, dict):
                    raise ValueError(f"{name} must be a mapping")
                setattr(result, name, type(existing)(**value))
            else:
                setattr(result, name, copy.deepcopy(value))
        result.validate()
        return result

    @classmethod
    def from_yaml(cls, path: str | Path) -> Config:
        path = Path(path).resolve()
        result = cls.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
        for section, key in [(result.route, "path")]:
            if section.get(key):
                section[key] = str((path.parent / section[key]).resolve())
        if result.motor.efficiency_map:
            result.motor.efficiency_map = str((path.parent / result.motor.efficiency_map).resolve())
        return result

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        """Check domains at construction and before every simulation."""

        def within(name: str, value: float, low: float, high: float) -> None:
            if isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be finite within [{low}, {high}]")

        for section in [
            self.bike,
            self.rider,
            self.motor,
            self.battery,
            self.environment,
            self.regeneration,
            self.simulation,
        ]:
            for key, value in asdict(section).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if not math.isfinite(value):
                        raise ValueError(f"{key} must be finite")
        for name, val in [
            ("bike mass", self.bike.mass_kg),
            ("rider mass", self.rider.mass_kg),
            ("battery energy", self.battery.nominal_energy_wh),
            ("voltage", self.battery.nominal_voltage_v),
            ("capacity", self.battery.capacity_ah),
            ("dt", self.simulation.timestep_s),
            ("wheel radius", self.bike.wheel_radius_m),
            ("C1", self.battery.c1_f),
        ]:
            within(name, val, 1e-6, 1e9)
        for name, val in [
            ("Crr", self.bike.crr),
            ("CdA", self.bike.cda_m2),
            ("cargo", self.bike.cargo_kg),
            ("human power", self.rider.human_power_w),
            ("auxiliary power", self.simulation.auxiliary_power_w),
            ("motor power", self.motor.nominal_power_w),
            ("assist ratio", self.motor.assist_ratio),
            ("torque", self.motor.max_torque_nm),
            ("cutoff speed", self.motor.max_speed_mps),
            ("R0", self.battery.r0_ohm),
            ("R1", self.battery.r1_ohm),
            ("max current", self.battery.max_current_a),
            ("charge current", self.battery.max_charge_current_a),
            ("regen power", self.regeneration.max_power_w),
            ("regen speed", self.regeneration.min_speed_mps),
            ("fatigue", self.rider.fatigue_per_hour),
        ]:
            within(name, val, 0.0, 1e9)
        for name, val in [
            ("motor efficiency", self.motor.efficiency),
            ("drivetrain efficiency", self.bike.drivetrain_efficiency),
            ("usable fraction", self.battery.usable_fraction),
            ("regen efficiency", self.regeneration.efficiency),
        ]:
            within(name, val, 1e-6, 1.0)
        within("assist", self.motor.assist_level, 0, 1)
        within("soc_min", self.battery.soc_min, 0, 1)
        within("soc_max", self.battery.soc_max, 0, 1)
        if self.battery.soc_min >= self.battery.soc_max:
            raise ValueError("soc_min must be below soc_max")
        within("initial_soc", self.battery.initial_soc, self.battery.soc_min, self.battery.soc_max)
        within("temperature", self.environment.temperature_c, -100, 100)
        within("pressure", self.environment.pressure_pa, 1, 200000)
        within("cadence_reference", self.rider.cadence_reference_rpm, 1e-6, 1000)
        within("min_voltage", self.battery.min_voltage_v, 1e-6, 1000)
        if self.environment.air_density_kgm3 is not None:
            within("density", self.environment.air_density_kgm3, 1e-6, 10)
        if self.rider.mode not in {"constant", "conditions"}:
            raise ValueError(
                "Rider mode must be constant or conditions; temporal power is a route column"
            )
        if self.motor.assist_mode not in {"demand", "proportional"}:
            raise ValueError("Unknown assist mode")
        if self.battery.model not in {"energy", "soc", "ecm"}:
            raise ValueError("Battery model must be energy, soc or ecm")
        for surface, val in self.bike.surface_crr.items():
            within(f"Crr {surface}", val, 0, 0.5)
        if (
            len(self.battery.ocv_soc) != len(self.battery.ocv_voltage_v)
            or len(self.battery.ocv_soc) < 2
        ):
            raise ValueError("OCV vectors must have matching length >= 2")
        if self.battery.ocv_soc[0] != 0 or self.battery.ocv_soc[-1] != 1:
            raise ValueError("OCV SOC grid must span [0, 1]")
        if any(a >= b for a, b in zip(self.battery.ocv_soc, self.battery.ocv_soc[1:])):
            raise ValueError("OCV SOC knots must strictly increase")
        for val in self.battery.ocv_soc:
            within("OCV SOC", val, 0, 1)
        for val in self.battery.ocv_voltage_v:
            within("OCV voltage", val, 1e-6, 1000)
        for curve in [
            self.battery.capacity_temperature_curve,
            self.battery.resistance_temperature_curve,
        ]:
            if curve:
                if len(curve) < 2 or any(len(pair) != 2 for pair in curve):
                    raise ValueError("Temperature curves need >=2 [temperature, multiplier] knots")
                if any(a[0] >= b[0] for a, b in zip(curve, curve[1:])):
                    raise ValueError("Temperature knots must increase")
                for temp, multiplier in curve:
                    within("curve temperature", temp, -100, 100)
                    within("curve multiplier", multiplier, 1e-6, 10)

    @property
    def total_mass_kg(self) -> float:
        return self.bike.mass_kg + self.bike.cargo_kg + self.rider.mass_kg

    def changed(self, path: str, value: Any) -> Config:
        """Copy configuration and set an explicit section.parameter path."""
        result = copy.deepcopy(self)
        section, name = path.split(".")
        target = getattr(result, section)
        if not hasattr(target, name):
            raise ValueError(f"Unknown parameter {path}")
        setattr(target, name, value)
        result.validate()
        return result

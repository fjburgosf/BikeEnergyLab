"""Energy/SOC battery and optional one-RC Thevenin model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bikeenergylab.config import Battery


def temperature_multiplier(curve: list[list[float]], temperature_c: float) -> float:
    if not curve:
        return 1.0
    knots = np.asarray(curve, float)
    if not knots[0, 0] <= temperature_c <= knots[-1, 0]:
        raise ValueError("Temperature lies outside supplied empirical curve; extrapolation refused")
    return float(np.interp(temperature_c, knots[:, 0], knots[:, 1]))


@dataclass
class BatteryStep:
    power_w: float
    dt_s: float
    soc: float
    voltage_v: float
    current_a: float
    chemical_power_w: float
    limited: bool


class BatteryState:
    def __init__(self, settings: Battery) -> None:
        self.settings = settings
        self.soc = settings.initial_soc
        self.v_rc = 0.0

    def step(self, requested_power_w: float, dt_s: float, temperature_c: float) -> BatteryStep:
        """Solve P=VI on the stable low-current branch; stop exactly at SOC reserve.

        Positive power discharges, negative power charges. ECM uses coulomb counting;
        energy/SOC use a temperature-adjusted energy denominator. RC update is exact
        for constant current within this step. Voltage is the start-of-step voltage.
        """
        cfg = self.settings
        scale = temperature_multiplier(cfg.capacity_temperature_curve, temperature_c)
        full_wh = cfg.nominal_energy_wh * cfg.usable_fraction * scale
        ocv = float(np.interp(self.soc, cfg.ocv_soc, cfg.ocv_voltage_v))
        effective_voltage = ocv - self.v_rc if cfg.model == "ecm" else cfg.nominal_voltage_v
        if cfg.model == "ecm":
            resistance = cfg.r0_ohm * temperature_multiplier(
                cfg.resistance_temperature_curve, temperature_c
            )
            if resistance > 0:
                discriminant = effective_voltage**2 - 4 * resistance * requested_power_w
                # Rationalized root avoids cancellation for small powers.
                root = np.sqrt(max(0.0, discriminant))
                current = 2 * requested_power_w / max(effective_voltage + root, 1e-12)
                current = min(
                    current,
                    effective_voltage / (2 * resistance),
                    max(0.0, (effective_voltage - cfg.min_voltage_v) / resistance),
                )
            else:
                current = requested_power_w / max(effective_voltage, 1e-12)
                if effective_voltage < cfg.min_voltage_v and current > 0:
                    current = 0.0
        else:
            resistance = 0.0
            current = requested_power_w / cfg.nominal_voltage_v
        current = float(np.clip(current, -cfg.max_charge_current_a, cfg.max_current_a))
        if self.soc >= cfg.soc_max - 1e-12 and current < 0:
            current = 0.0
        voltage = effective_voltage - resistance * current
        power = voltage * current
        rate = (
            current / (cfg.capacity_ah * cfg.usable_fraction * scale * 3600)
            if cfg.model == "ecm"
            else power / (full_wh * 3600)
        )
        actual_dt = dt_s
        if rate > 0:
            actual_dt = min(dt_s, max(0.0, (self.soc - cfg.soc_min) / rate))
        elif rate < 0:
            # Cap charging current to finish this interval exactly at soc_max.
            fraction = min(1.0, max(0.0, (cfg.soc_max - self.soc) / (-rate * dt_s)))
            current *= fraction
            voltage = effective_voltage - resistance * current
            power = voltage * current
            rate = (
                current / (cfg.capacity_ah * cfg.usable_fraction * scale * 3600)
                if cfg.model == "ecm"
                else power / (full_wh * 3600)
            )
        self.soc = float(np.clip(self.soc - rate * actual_dt, cfg.soc_min, cfg.soc_max))
        if cfg.model == "ecm" and cfg.r1_ohm > 0:
            decay = np.exp(-actual_dt / (cfg.r1_ohm * cfg.c1_f))
            self.v_rc = self.v_rc * decay + current * cfg.r1_ohm * (1 - decay)
        return BatteryStep(
            power,
            actual_dt,
            self.soc,
            voltage,
            current,
            ocv * current if cfg.model == "ecm" else power,
            abs(power - requested_power_w) > 1e-7 or actual_dt < dt_s - 1e-9,
        )

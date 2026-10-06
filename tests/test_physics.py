import numpy as np
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.battery import BatteryState
from bikeenergylab.config import Battery
from bikeenergylab.physics import GRAVITY_MPS2, longitudinal_forces


def test_forces_and_power_analytical():
    f = longitudinal_forces(
        100, 0.006, 0.5, 5, grade=0.1, acceleration_mps2=0.2, wind_mps=-2, density_kgm3=1.2
    )
    assert f.rolling_n == pytest.approx(100 * GRAVITY_MPS2 * 0.006 / np.sqrt(1.01))
    assert f.grade_n == pytest.approx(100 * GRAVITY_MPS2 * 0.1 / np.sqrt(1.01))
    assert f.aero_n == pytest.approx(0.5 * 1.2 * 0.5 * 49)
    assert f.acceleration_n == 20


def test_aero_zero_rest_and_cubic():
    speeds = np.array([0, 3, 6])
    power = longitudinal_forces(100, 0.006, 0.5, speeds).aero_n * speeds
    assert power[0] == 0
    assert power[2] / power[1] == pytest.approx(8)


def test_tailwind_faster_than_bicycle_has_correct_sign():
    assert longitudinal_forces(100, 0.006, 0.5, 5, wind_mps=10).aero_n < 0


def test_sanity_energy_monotonicity():
    base = Config().changed("rider.human_power_w", 50)
    flat = Route.synthetic(1000, 5, segments=10)
    e = BikeModel(base).predict_energy(flat)
    assert BikeModel(base).predict_energy(Route.synthetic(1000, 5, grade=0.03, segments=10)) > e
    assert BikeModel(base.changed("environment.wind_mps", -2)).predict_energy(flat) > e
    assert BikeModel(base.changed("rider.human_power_w", 0)).predict_energy(flat) > e
    assert BikeModel(base.changed("bike.mass_kg", 40)).predict_energy(flat) > e


def test_mass_components_scale():
    a = longitudinal_forces(100, 0.006, 0.5, 5, grade=0.1, acceleration_mps2=0.2)
    b = longitudinal_forces(200, 0.006, 0.5, 5, grade=0.1, acceleration_mps2=0.2)
    for name in ["rolling_n", "grade_n", "acceleration_n"]:
        assert getattr(b, name) == pytest.approx(2 * getattr(a, name))
    assert b.aero_n == a.aero_n


def test_simulation_energy_soc_and_balance():
    cfg = Config()
    route = Route.synthetic(1000, 5, segments=10)
    model = BikeModel(cfg)
    result = model.simulate(route)
    assert result.summary["feasible"]
    assert result.summary["energy_wh"] == pytest.approx(model.predict_energy(route))
    assert result.summary["final_soc"] == pytest.approx(
        cfg.battery.initial_soc - result.summary["energy_wh"] / (500 * 0.95)
    )
    assert result.summary["max_energy_balance_error_w"] < 1e-8


def test_exact_battery_depletion_and_infeasibility():
    cfg = Config().changed("battery.nominal_energy_wh", 0.1)
    result = BikeModel(cfg).simulate(Route.synthetic(1000, 5, segments=10))
    assert not result.summary["completed_route"]
    assert result.summary["final_soc"] == pytest.approx(cfg.battery.soc_min)
    assert result.summary["energy_wh"] == pytest.approx(0.1 * 0.95 * 0.8)
    limited = BikeModel(Config().changed("motor.nominal_power_w", 10)).simulate(
        Route.synthetic(100, 7)
    )
    assert limited.summary["completed_route"]
    assert not limited.summary["feasible"]
    assert limited.summary["stationary_equivalent_range_km"] is None


def test_regeneration_disabled_and_enabled_balance():
    cfg = Config()
    route = Route.synthetic(500, 5, grade=-0.08, segments=10)
    off = BikeModel(cfg).simulate(route)
    on = BikeModel(cfg.changed("regeneration.enabled", True)).simulate(route)
    assert off.trace.power_regen_w.max() == 0
    assert on.summary["energy_wh"] < off.summary["energy_wh"]
    assert on.summary["max_energy_balance_error_w"] < 1e-8
    assert on.summary["final_soc"] <= cfg.battery.soc_max


def test_assistance_limits_and_current_limit():
    route = Route.synthetic(100, 7)
    result = BikeModel(Config().changed("motor.assist_level", 0)).simulate(route)
    assert result.trace.power_motor_w.max() == 0
    assert not result.summary["feasible"]
    result = BikeModel(Config().changed("battery.max_current_a", 0.1)).simulate(route)
    assert result.trace.current_a.max() <= 0.1 + 1e-10
    assert result.summary["max_energy_balance_error_w"] < 1e-8


def test_ecm_constant_power_and_rc_state():
    state = BatteryState(Battery(model="ecm"))
    first = state.step(200, 1, 20)
    assert first.power_w == pytest.approx(200)
    assert first.voltage_v * first.current_a == pytest.approx(200)
    assert state.v_rc > 0
    second = state.step(200, 1, 20)
    assert second.voltage_v < first.voltage_v
    assert second.soc < first.soc


def test_invalid_config_rejected():
    for values in [{"motor": {"efficiency": 1.1}}, {"battery": {"soc_min": 0.96}}, {"bik": {}}]:
        with pytest.raises(ValueError):
            Config.from_dict(values)

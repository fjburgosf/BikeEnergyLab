import pandas as pd
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.battery import BatteryState
from bikeenergylab.cli import main
from bikeenergylab.config import Battery
from bikeenergylab.experiments.synthetic import generate_observations
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.uncertainty import monte_carlo


def test_battery_full_regeneration_and_auxiliary_balance():
    cfg = Config().changed("battery.initial_soc", 0.95).changed("regeneration.enabled", True)
    result = BikeModel(cfg).simulate(Route.synthetic(100, 5, grade=-0.08))
    assert result.trace.soc.max() <= 0.95
    assert result.trace.power_battery_w.min() >= -1e-8
    assert result.summary["max_energy_balance_error_w"] < 1e-8
    assert result.trace.power_regen_w.max() == pytest.approx(5)


def test_auxiliary_limit_prevents_false_feasible_result():
    cfg = Config().changed("battery.max_current_a", 0)
    result = BikeModel(cfg).simulate(Route.synthetic(100, 5))
    assert result.summary["unmet_auxiliary_energy_wh"] > 0
    assert not result.summary["feasible"]


def test_empty_battery_does_not_travel():
    result = BikeModel(Config().changed("battery.initial_soc", 0.10)).simulate(
        Route.synthetic(100, 7)
    )
    assert result.summary["distance_km"] == 0
    assert result.trace.empty


def test_ecm_high_load_current_voltage_and_soc_limits():
    cfg = Battery(model="ecm", initial_soc=0.11, max_current_a=10)
    state = BatteryState(cfg)
    step = state.step(5000, 10000, 20)
    assert step.current_a <= 10
    assert step.voltage_v >= cfg.min_voltage_v - 1e-9
    assert step.soc == pytest.approx(cfg.soc_min)
    assert step.dt_s < 10000
    assert step.limited


def test_explicit_temporal_human_wind_aux_profiles():
    route = Route.synthetic(
        100, 6, segments=2, human_power_w=[0, 100], wind_mps=[-2, 2], auxiliary_power_w=[5, 10]
    )
    profile = BikeModel().operating_profile(route)
    assert profile.power_human_w.iloc[1] > profile.power_human_w.iloc[0]
    assert profile.force_aero_n.iloc[0] > profile.force_aero_n.iloc[1]
    assert profile.power_aux_w.tolist() == [5, 10]


def test_adaptation_invalidates_intervals_and_rejects_duplicate_groups():
    train = generate_observations(20, 51, prefix="train")
    heldout = generate_observations(20, 52, prefix="held")
    model = CGPRAModel().fit(train)
    model.calibrate_intervals(heldout)
    with pytest.raises(ValueError):
        model.adapt(heldout[0])
    new = generate_observations(1, 53, prefix="new")[0]
    update = model.adapt(new)
    assert update["intervals_invalidated"]
    assert not model.quantiles
    with pytest.raises(ValueError):
        model.predict([new], coverage=0.95)


def test_profile_override_uncertainty_is_explicit():
    route = Route.synthetic(100, 6, wind_mps=1)
    with pytest.raises(ValueError, match="overridden"):
        monte_carlo(
            Config(),
            route,
            n_samples=2,
            distributions={"environment.wind_mps": {"mean": 0, "std": 1}},
        )


def test_cli_simulation_and_quality(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("route:\n  distance_m: 100\n  speed_mps: 7\n  segments: 5\n")
    assert (
        main(["simulate", str(config), "--output", str(tmp_path / "results"), "--no-figures"]) == 0
    )
    dataset = tmp_path / "bad.csv"
    pd.DataFrame({"soc": [2]}).to_csv(dataset, index=False)
    assert main(["quality", str(dataset), "--output", str(tmp_path / "quality.json")]) == 2


def test_stops_consume_auxiliaries_and_energy_timestep_converges():
    frame = pd.DataFrame(
        {
            "length_m": [0, 100],
            "dt_s": [10, 20],
            "speed_mps": [0, 5],
            "grade": [0, 0],
            "acceleration_mps2": [0, 0],
        }
    )
    result = BikeModel().simulate(Route(frame))
    assert result.trace.iloc[0].power_battery_w == 5
    route = Route.synthetic(100, 7)
    a = BikeModel(Config().changed("simulation.timestep_s", 0.5)).simulate(route)
    b = BikeModel(Config().changed("simulation.timestep_s", 3)).simulate(route)
    assert a.summary["energy_wh"] == pytest.approx(b.summary["energy_wh"])

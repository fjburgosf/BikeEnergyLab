import numpy as np
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.calibration import Observation, SequentialCalibrator, calibrate
from bikeenergylab.experiments.synthetic import (
    generate_observations,
    observations_from_csv,
    serialize_observations,
)
from bikeenergylab.metrics import empirical_crps, interval_metrics, point_metrics
from bikeenergylab.residual import CGPRAModel, ConfidenceGate, StableScaler
from bikeenergylab.uncertainty import monte_carlo, repeated_route_range


def test_parameter_recovery_with_known_synthetic_truth():
    data = generate_observations(35, seed=10, discrepancy=False, noise_std_wh_per_km=0)
    fitted = calibrate(Config(), data)
    assert fitted.success
    assert fitted.parameters["bike.crr"] == pytest.approx(0.008, abs=1e-7)
    assert fitted.parameters["bike.cda_m2"] == pytest.approx(0.48, abs=1e-6)
    assert fitted.identifiability["rank"] == 2


def test_nonidentifiable_same_speed_detected():
    cfg = Config().changed("rider.human_power_w", 0)
    truth = cfg.changed("bike.crr", 0.008).changed("bike.cda_m2", 0.48)
    data = [
        Observation(
            Route.synthetic(length, 5),
            BikeModel(truth).predict_energy(Route.synthetic(length, 5)),
            cfg,
            str(length),
        )
        for length in [100, 200, 300, 400, 500]
    ]
    fitted = calibrate(cfg, data)
    assert fitted.identifiability["warnings"]


def test_sequential_update_improves_predictions():
    observations = generate_observations(20, seed=11, discrepancy=False, noise_std_wh_per_km=0)
    updater = SequentialCalibrator(Config(), observation_variance_wh2=0.01)
    first = updater.update(observations[0])
    assert first["updates"] == 1
    for observation in observations[1:]:
        updater.update(observation)
    assert updater.config.bike.crr == pytest.approx(0.008, abs=0.0001)
    assert updater.config.bike.cda_m2 == pytest.approx(0.48, abs=0.003)
    assert np.linalg.eigvalsh(updater.covariance).min() >= -1e-12


@pytest.mark.parametrize("strategy", ["simple", "advanced"])
def test_confidence_gate_rejects_distant_and_small_support(strategy):
    rng = np.random.default_rng(42)
    x = rng.normal(size=(80, 3))
    residual = rng.normal(size=80)
    gate = ConfidenceGate(strategy).fit(x, residual)
    alpha, scores = gate.evaluate(np.array([[0, 0, 0], [100, 100, 100]]), np.array([0.1, 0.1]))
    assert 0 <= alpha[1] < alpha[0] <= 1
    assert scores[1] > scores[0]
    assert alpha[1] < 1e-6
    if strategy == "advanced":
        high, _ = gate.evaluate(np.array([[0, 0, 0]]), np.array([100]))
        assert high[0] < alpha[0]


def test_m1_m4_conformal_and_no_leakage():
    train = generate_observations(40, 1, prefix="train")
    hold = generate_observations(25, 2, prefix="hold")
    test = generate_observations(8, 3, scenario="OOD-Combined", prefix="test")
    model = CGPRAModel().fit(train)
    with pytest.raises(ValueError):
        model.calibrate_intervals(train)
    model.calibrate_intervals(hold)
    one = model.predict(test, "M1")
    three = model.predict(test, "M3")
    four = model.predict(test, "M4", coverage=0.95)
    np.testing.assert_allclose(
        four.energy_wh, one.energy_wh + four.alpha * (three.energy_wh - one.energy_wh)
    )
    assert four.alpha.mean() < 0.01
    assert np.all(four.lower_wh <= four.upper_wh)
    assert np.isfinite(model.predict(test, "M2").energy_wh).all()


def test_synthetic_csv_preserves_observations(tmp_path):
    data = generate_observations(3, 5, prefix="csv")
    path = tmp_path / "observations.csv"
    serialize_observations(data).to_csv(path, index=False)
    loaded = observations_from_csv(str(path), data[0].config)
    assert [o.energy_wh for o in loaded] == pytest.approx([o.energy_wh for o in data])
    assert loaded[1].config.rider.mass_kg == pytest.approx(data[1].config.rider.mass_kg)


def test_monte_carlo_reproducible_and_mission_bounds():
    cfg = Config().changed("rider.human_power_w", 30).changed("battery.nominal_energy_wh", 30)
    route = Route.synthetic(2000, 5, segments=10)
    distributions = {
        "environment.wind_mps": {
            "distribution": "normal",
            "mean": 0,
            "std": 1,
            "low": -4,
            "high": 4,
        }
    }
    first = monte_carlo(
        cfg, route, n_samples=12, seed=17, distributions=distributions, max_distance_km=20
    )
    second = monte_carlo(
        cfg, route, n_samples=12, seed=17, distributions=distributions, max_distance_km=20
    )
    assert first.samples.equals(second.samples)
    assert 0 <= first.summary["mission_probability"] <= 1
    assert first.summary["range_km"]["sd"] > 0
    assert first.samples.soc_final.between(cfg.battery.soc_min, cfg.battery.soc_max).all()


def test_range_repeated_cycle_matches_analytical_flat_case():
    cfg = Config().changed("rider.human_power_w", 30)
    route = Route.synthetic(1000, 5, segments=10)
    demand = BikeModel(cfg).predict_energy(route)
    range_km, censored = repeated_route_range(BikeModel(cfg), route)
    available = 500 * 0.95 * 0.8
    assert not censored
    assert range_km == pytest.approx(available / demand, rel=1e-8)


def test_metrics_and_crps_known_values():
    assert point_metrics(np.array([1, 2]), np.array([1, 4]))["mae"] == 1
    assert point_metrics(np.array([1, 1]), np.array([1, 1]))["r2"] is None
    assert interval_metrics(np.array([1, 3]), np.array([0, 0]), np.array([2, 2]))["coverage"] == 0.5
    assert empirical_crps(np.array([0, 2]), 1) == pytest.approx(0.5)


def test_temperature_requires_empirical_curve_and_reserve_validation():
    cfg = Config()
    assert cfg.battery.capacity_temperature_curve == []
    route = Route.synthetic(100, 7)
    with pytest.raises(ValueError):
        monte_carlo(cfg, route, n_samples=2, reserve_soc=0.99)
    cfg.battery.capacity_temperature_curve = [[0, 0.8], [20, 1.0], [40, 1.0]]
    cold = monte_carlo(
        cfg.changed("environment.temperature_c", 0), route, n_samples=2, max_distance_km=300
    )
    warm = monte_carlo(cfg, route, n_samples=2, max_distance_km=300)
    assert cold.summary["range_km"]["mean"] < warm.summary["range_km"]["mean"]


def test_data_baseline_does_not_amplify_roundoff_in_constant_route_features():
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline

    rng = np.random.default_rng(8)
    primary = rng.normal(size=50)
    x = np.column_stack([primary, rng.normal(scale=1e-16, size=50)])
    y = 2 * primary
    floating = make_pipeline(StableScaler(), Ridge(alpha=2)).fit(x, y)
    exact = make_pipeline(StableScaler(), Ridge(alpha=2)).fit(
        np.column_stack([primary, np.zeros(50)]), y
    )
    query = np.array([[1.0, 0.5]])
    assert floating.predict(query)[0] == pytest.approx(exact.predict(query)[0], abs=1e-5)
    model = CGPRAModel().fit(generate_observations(25, 8, prefix="train-stability"))
    unseen = generate_observations(5, 9, scenario="OOD-Route", prefix="test-stability")
    assert np.max(np.abs(model.predict(unseen, "M2").energy_wh)) < 10000

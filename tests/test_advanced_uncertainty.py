import pandas as pd
import pytest

from bikeenergylab import Config, Route
from bikeenergylab.io import quality_report
from bikeenergylab.uncertainty import monte_carlo


def test_uniform_grid_and_adaptive_max_length():
    route = Route.synthetic(1000, 5, segments=1)
    uniform = route.uniform(100)
    adaptive = route.adaptive(max_length_m=250)
    assert len(uniform.frame) == 10
    assert uniform.frame.length_m.max() <= 100.000001
    assert adaptive.frame.length_m.max() <= 250.000001
    assert adaptive.distance_m == pytest.approx(1000)


def test_joint_correlated_draws_and_exported_options(tmp_path):
    route = Route.synthetic(100, 6, segments=4)
    joint = {
        "parameters": ["bike.crr", "bike.cda_m2"],
        "mean": [0.006, 0.55],
        "covariance": [[1e-8, 5e-7], [5e-7, 1e-4]],
        "low": [0.001, 0.1],
        "high": [0.02, 1.0],
    }
    first = monte_carlo(
        Config(), route, n_samples=8, seed=2, max_distance_km=2, joint_parameters=joint
    )
    second = monte_carlo(
        Config(), route, n_samples=8, seed=2, max_distance_km=2, joint_parameters=joint
    )
    assert first.samples.equals(second.samples)
    assert first.config.uncertainty["seed"] == 2
    assert first.config.uncertainty["joint_parameters"] == joint
    joint["covariance"] = [[1e-8, 1], [1, 1e-4]]
    with pytest.raises(ValueError, match="positive semidefinite"):
        monte_carlo(Config(), route, n_samples=2, joint_parameters=joint)


def test_elevation_uncertainty_is_reproducible_and_changes_energy():
    route = Route.synthetic(1000, 5, segments=10)
    options = {
        "route.elevation_noise_m": {
            "distribution": "normal",
            "mean": 0,
            "std": 0.5,
            "low": -1,
            "high": 1,
        }
    }
    result = monte_carlo(
        Config(), route, n_samples=8, seed=3, distributions=options, max_distance_km=10
    )
    assert result.samples.energy_wh.std() > 0
    again = monte_carlo(
        Config(), route, n_samples=8, seed=3, distributions=options, max_distance_km=10
    )
    assert result.samples.equals(again.samples)


def test_quality_checks_are_per_route_group():
    frame = pd.DataFrame(
        {
            "route_id": ["a", "a", "b", "b"],
            "time_s": [0, 1, 0, 1],
            "distance_m": [0, 5, 0, 5],
            "speed_mps": [5, 5, 5, 5],
        }
    )
    report = quality_report(frame)
    assert report["valid"]
    assert not report["issues"]

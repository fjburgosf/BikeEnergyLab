import numpy as np
import pandas as pd
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.io import quality_report
from bikeenergylab.motor import EfficiencyMap, generate_illustrative_map


def test_uniform_adaptive_conservation_and_changes():
    route = Route.synthetic(1000, 5, segments=10, grade=np.r_[np.zeros(5), np.full(5, 0.02)])
    uniform = route.subdivide(3)
    adaptive = route.adaptive(max_length_m=1000)
    assert len(adaptive.frame) == 2
    assert uniform.distance_m == pytest.approx(route.distance_m)
    assert uniform.frame.dt_s.sum() == pytest.approx(route.frame.dt_s.sum())
    assert adaptive.distance_m == pytest.approx(route.distance_m)
    assert BikeModel().predict_energy(adaptive) == pytest.approx(BikeModel().predict_energy(route))


def test_filter_csv_gpx_roundtrip(tmp_path):
    route = Route.from_elevation(
        np.array([0, 10, 20, 30, 40]), np.array([0, 0, 4, 0, 0]), smoothing_window=3
    )
    assert route.frame.grade.abs().max() == 0
    path = tmp_path / "route.csv"
    route.frame.to_csv(path, index=False)
    assert Route.from_csv(path).distance_m == route.distance_m
    gpx = tmp_path / "route.gpx"
    gpx.write_text(
        '<gpx><trk><trkseg><trkpt lat="4" lon="-74"><ele>100</ele></trkpt><trkpt lat="4.001" lon="-74"><ele>102</ele></trkpt></trkseg></trk></gpx>'
    )
    loaded = Route.from_gpx(gpx, smoothing_window=1)
    assert 110 < loaded.distance_m < 112
    assert loaded.frame.grade.iloc[0] == pytest.approx(2 / 111.1949266, rel=1e-5)


def test_quality_report_does_not_modify():
    frame = pd.DataFrame(
        {
            "soc": [1.2, 0.5, np.nan],
            "speed_mps": [5, 50, 4],
            "timestamp": ["2026-01-01", "2025-01-01", "bad"],
        }
    )
    original = frame.copy(deep=True)
    report = quality_report(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert not report["valid"]
    assert {issue["code"] for issue in report["issues"]} >= {
        "implausible_soc",
        "invalid_timestamp",
        "implausible_speed_mps",
    }


def test_maps_and_export(tmp_path):
    map_path = tmp_path / "motor.csv"
    generate_illustrative_map(map_path)
    efficiency, outside = EfficiencyMap.from_csv(map_path).evaluate(
        np.array([20, 50]), np.array([30, 100])
    )
    assert efficiency[0] == pytest.approx(0.88, abs=0.002)
    assert outside.tolist() == [False, True]
    result = BikeModel().simulate(Route.synthetic(100, 7, segments=5))
    output = result.export(tmp_path, figures=False)
    assert (output / "metadata.json").exists()
    assert (output / "predictions.csv").exists()
    assert Config.from_yaml(output / "config.yaml").bike.mass_kg == 25
    exported = Config.from_yaml(output / "config.yaml")
    from bikeenergylab.routes import route_from_config

    assert route_from_config(exported).distance_m == pytest.approx(result.route.distance_m)


def test_route_unit_errors_rejected():
    with pytest.raises(ValueError):
        Route(pd.DataFrame({"length_m": [100], "dt_s": [1], "speed_mps": [5], "grade": [0]}))
    with pytest.raises(ValueError):
        Route.synthetic(100, 5, grade=5)

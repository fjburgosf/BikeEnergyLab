import numpy as np
import pandas as pd
import pytest

from bikeenergylab import Config, Route
from bikeenergylab.io.telemetry import load_telemetry
from bikeenergylab.uncertainty.sensitivity import one_at_a_time


def test_telemetry_integration_stops_and_provenance(tmp_path):
    frame = pd.DataFrame(
        {
            "time_s": [0, 10, 30],
            "distance_m": [0, 0, 100],
            "voltage_v": [36, 36, 36],
            "current_a": [1, 1, 2],
        }
    )
    path = tmp_path / "telemetry.csv"
    frame.to_csv(path, index=False)
    observations, report = load_telemetry(path)
    assert report["valid"] and not report["modified"]
    assert observations[0].route.frame.speed_mps.tolist() == [0, 5]
    assert observations[0].energy_wh == pytest.approx((36 * 10 + 54 * 20) / 3600)
    assert observations[0].route.provenance["integration"] == "endpoint trapezoid V*I"
    pd.testing.assert_frame_equal(pd.read_csv(path), frame)


def test_sensitivity_direction_and_required_parameters():
    cfg = Config().changed("rider.human_power_w", 20)
    table = one_at_a_time(cfg, Route.synthetic(1000, 6))
    slopes = table.set_index("parameter").derivative_wh_per_parameter_unit
    assert len(slopes) == 8
    assert slopes["bike.crr"] > 0
    assert slopes["bike.cda_m2"] > 0
    assert slopes["rider.human_power_w"] < 0
    assert slopes["environment.wind_mps"] < 0
    assert slopes["motor.efficiency"] < 0
    assert np.isfinite(slopes).all()

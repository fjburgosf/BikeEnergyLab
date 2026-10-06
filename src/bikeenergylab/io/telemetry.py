"""Convert explicit, validated sensor samples into observed route intervals."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter

from bikeenergylab import Config, Route
from bikeenergylab.calibration import Observation

from . import quality_report


def load_telemetry(
    path: str | Path, config: Config | None = None, smoothing_window: int = 5
) -> tuple[list[Observation], dict]:
    """Integrate terminal V*I with trapezoids; retain a transparent conversion report.

    Requires timestamp or time_s plus distance_m and voltage/current. Interval
    speed is derived from measured distance/time, while the original sensor file
    is left untouched. Stops remain intervals. Grouping is optional route_id.
    """
    frame = pd.read_csv(path)
    report = quality_report(frame)
    if not report["valid"]:
        raise ValueError(f"Telemetry quality errors: {report['issues']}")
    if not {"distance_m", "voltage_v", "current_a"}.issubset(frame) or not {
        "time_s",
        "timestamp",
    } & set(frame):
        raise ValueError("Telemetry requires distance_m, voltage_v, current_a and time_s/timestamp")
    if smoothing_window < 1 or smoothing_window % 2 == 0:
        raise ValueError("Smoothing window must be positive and odd")
    results = []
    groups = (
        frame.groupby("route_id", sort=False) if "route_id" in frame else [("telemetry", frame)]
    )
    for group, block in groups:
        if len(block) < 2:
            raise ValueError("Each telemetry route needs at least two endpoints")
        if "timestamp" in block:
            stamps = pd.to_datetime(block.timestamp, utc=True)
            time = (stamps - stamps.iloc[0]).dt.total_seconds().to_numpy()
        else:
            time = block.time_s.to_numpy(float)
        dt = np.diff(time)
        ds = np.diff(block.distance_m.to_numpy(float))
        if (dt <= 0).any() or (ds < 0).any():
            raise ValueError("Telemetry times must increase and distances cannot decrease")
        speed = ds / dt
        data = {"length_m": ds, "dt_s": dt, "speed_mps": speed, "grade": np.zeros(len(dt))}
        for key in [
            "grade",
            "wind_mps",
            "temperature_c",
            "human_power_w",
            "auxiliary_power_w",
            "assist_level",
            "cadence_rpm",
            "acceleration_mps2",
        ]:
            if key in block:
                vals = block[key].to_numpy(float)
                data[key] = (vals[:-1] + vals[1:]) / 2
        if "surface" in block:
            data["surface"] = block.surface.to_numpy()[:-1]
        if "elevation_m" in block:
            elevation = median_filter(
                block.elevation_m.to_numpy(float), size=smoothing_window, mode="nearest"
            )
            dh = np.diff(elevation)
            if np.any(np.abs(dh) > ds) or np.any((ds == 0) & (dh != 0)):
                raise ValueError(
                    "Elevation change exceeds along-road distance; inspect sensor quality"
                )
            data["elevation_m"] = elevation[1:]
            if "grade" not in block:
                horizontal = np.sqrt(np.maximum(ds**2 - dh**2, 0))
                if np.any((horizontal == 0) & (dh != 0)):
                    raise ValueError("Vertical segment cannot be a bicycle route")
                data["grade"] = np.divide(
                    dh, horizontal, out=np.zeros_like(dh), where=horizontal > 0
                )
        power = block.voltage_v.to_numpy() * block.current_a.to_numpy()
        energy_wh = float(np.dot((power[:-1] + power[1:]) / 2, dt) / 3600)
        provenance = {
            "source": "telemetry",
            "filename": Path(path).name,
            "integration": "endpoint trapezoid V*I",
            "speed": "derived from measured distance/time; original file unchanged",
            "elevation_filter": {"kind": "median", "window_points": smoothing_window},
            "quality_issues": report["issues"],
        }
        route = Route(pd.DataFrame(data), str(group), provenance)
        results.append(Observation(route, energy_wh, config or Config(), str(group)))
    report["conversion"] = {
        "routes": len(results),
        "integration": "trapezoidal terminal electrical power",
        "speed_derivation": "measured along-road distance / duration",
        "smoothing_window_points": smoothing_window,
    }
    if report["issues"]:
        logging.getLogger(__name__).warning(
            "Telemetry quality warnings retained: %s", report["issues"]
        )
    return results, report

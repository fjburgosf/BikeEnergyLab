"""Offline routes as piecewise-constant time intervals."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter


@dataclass
class Route:
    """Each row represents one interval; distance is along the road, grade is rise/run."""

    frame: pd.DataFrame
    name: str = "route"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.frame = self.frame.copy().reset_index(drop=True)
        required = ["length_m", "dt_s", "speed_mps", "grade"]
        if self.frame.empty or not set(required).issubset(self.frame):
            raise ValueError(f"Nonempty route requires {required}")
        numeric = self.frame.select_dtypes(include="number")
        if not np.isfinite(numeric.to_numpy()).all() or self.frame.isna().any().any():
            raise ValueError("Route contains missing or nonfinite values; inspect data quality")
        f = self.frame
        if (f.dt_s <= 0).any() or (f.speed_mps < 0).any() or (f.length_m < 0).any():
            raise ValueError("dt must be positive, speed and length nonnegative")
        if not np.allclose(f.length_m, f.speed_mps * f.dt_s, atol=1e-5, rtol=1e-5):
            raise ValueError("Interval length must equal speed * duration")
        if (f.grade.abs() > 1).any():
            raise ValueError("Grade is rise/run, not percent; absolute grade must be <=1")
        if f.length_m.sum() <= 0:
            raise ValueError("Route must include positive traveled distance")
        bounds = {
            "assist_level": (0, 1),
            "human_power_w": (0, 3000),
            "auxiliary_power_w": (0, 10000),
            "temperature_c": (-100, 100),
            "cadence_rpm": (0, 300),
        }
        for key, (low, high) in bounds.items():
            if key in f and not f[key].between(low, high).all():
                raise ValueError(f"{key} outside [{low}, {high}]")
        f["distance_m"] = f.length_m.cumsum()
        f["time_s"] = f.dt_s.cumsum()
        if "elevation_m" not in f:
            f["elevation_m"] = (np.sin(np.arctan(f.grade)) * f.length_m).cumsum()
        if "acceleration_mps2" not in f:
            # No invented acceleration from rest at the first interval.
            v = f.speed_mps.to_numpy()
            f["acceleration_mps2"] = np.r_[
                0.0, np.diff(v) / ((f.dt_s.to_numpy()[1:] + f.dt_s.to_numpy()[:-1]) / 2)
            ]
        if "surface" not in f:
            f["surface"] = "default"

    @property
    def distance_m(self) -> float:
        return float(self.frame.length_m.sum())

    @classmethod
    def synthetic(
        cls,
        distance_m: float = 10000,
        speed_mps: float = 5,
        grade: float = 0,
        segments: int = 100,
        **profiles: Any,
    ) -> Route:
        if distance_m <= 0 or speed_mps <= 0 or segments < 1:
            raise ValueError("Positive distance, speed and segments required")
        length = np.full(segments, distance_m / segments)
        data: dict[str, Any] = {
            "length_m": length,
            "dt_s": length / speed_mps,
            "speed_mps": speed_mps,
            "grade": grade,
        }
        data.update(profiles)
        return cls(pd.DataFrame(data), "synthetic", {"source": "synthetic"})

    @classmethod
    def from_csv(cls, path: str | Path) -> Route:
        return cls(
            pd.read_csv(path), Path(path).stem, {"source": "csv", "filename": Path(path).name}
        )

    @classmethod
    def from_elevation(
        cls,
        horizontal_distance_m: np.ndarray,
        elevation_m: np.ndarray,
        speed_mps: float = 5,
        smoothing_window: int = 5,
    ) -> Route:
        """Median filter elevations before slope; preserve explicit smoothing metadata."""
        x, z = np.asarray(horizontal_distance_m, float), np.asarray(elevation_m, float)
        if len(x) != len(z) or len(x) < 2 or not np.isfinite(x).all() or not np.isfinite(z).all():
            raise ValueError("Need matching finite distance and elevation vectors")
        if np.any(np.diff(x) <= 0) or speed_mps <= 0:
            raise ValueError("Horizontal distance must increase and speed must be positive")
        if smoothing_window < 1 or smoothing_window % 2 == 0:
            raise ValueError("Smoothing window must be positive and odd")
        filtered = median_filter(z, size=smoothing_window, mode="nearest")
        dx, dh = np.diff(x), np.diff(filtered)
        ds = np.hypot(dx, dh)
        return cls(
            pd.DataFrame(
                {
                    "length_m": ds,
                    "dt_s": ds / speed_mps,
                    "speed_mps": speed_mps,
                    "grade": dh / dx,
                    "elevation_m": filtered[1:],
                }
            ),
            "elevation",
            {"smoothing": "median", "window_points": smoothing_window},
        )

    @classmethod
    def from_gpx(cls, path: str | Path, speed_mps: float = 5, smoothing_window: int = 5) -> Route:
        """Load GPX coordinates/elevation offline. Times, when present, determine speed."""
        root = ET.parse(path).getroot()
        segments = root.findall(".//{*}trkseg")
        if len(segments) > 1:
            raise ValueError("Multiple GPX track segments require explicit joining")
        points = root.findall(".//{*}trkpt") or root.findall(".//{*}rtept")
        if len(points) < 2:
            raise ValueError("GPX needs at least two track or route points")
        lat = np.array([float(p.attrib["lat"]) for p in points])
        lon = np.array([float(p.attrib["lon"]) for p in points])
        if (
            not np.isfinite(lat).all()
            or not np.isfinite(lon).all()
            or (np.abs(lat) > 90).any()
            or (np.abs(lon) > 180).any()
        ):
            raise ValueError("Invalid GPX coordinates")
        elev = [p.find("{*}ele") for p in points]
        if any(e is None or e.text is None for e in elev):
            raise ValueError(
                "GPX lacks elevation; supply elevation rather than silently assuming flat"
            )
        phi, lam = np.radians(lat), np.radians(lon)
        hav = (
            np.sin(np.diff(phi) / 2) ** 2
            + np.cos(phi[:-1]) * np.cos(phi[1:]) * np.sin(np.diff(lam) / 2) ** 2
        )
        ground = 6371000 * 2 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))
        times = [p.find("{*}time") for p in points]
        if any(t is not None for t in times):
            if any(t is None or t.text is None for t in times):
                raise ValueError("Incomplete GPX timestamps")
            stamp = pd.to_datetime([t.text for t in times], utc=True)
            dt = np.asarray((stamp[1:] - stamp[:-1]).total_seconds())
            if not np.isfinite(dt).all() or (dt <= 0).any():
                raise ValueError("GPX timestamps must strictly increase")
            if smoothing_window < 1 or smoothing_window % 2 == 0:
                raise ValueError("Smoothing window must be positive and odd")
            elevation = median_filter(
                np.array([float(e.text) for e in elev]), size=smoothing_window, mode="nearest"
            )
            dh = np.diff(elevation)
            if np.any((ground == 0) & (np.abs(dh) > 1e-9)):
                raise ValueError("A stationary GPX interval cannot change elevation")
            length = np.hypot(ground, dh)
            grade = np.divide(dh, ground, out=np.zeros_like(dh), where=ground > 0)
            route = cls(
                pd.DataFrame(
                    {
                        "length_m": length,
                        "dt_s": dt,
                        "speed_mps": length / dt,
                        "grade": grade,
                        "elevation_m": elevation[1:],
                    }
                )
            )
            route.provenance.update(
                elevation_filter={"kind": "median", "window_points": smoothing_window},
                speed_source="GPX timestamps; stationary intervals retained",
            )
        else:
            route = cls.from_elevation(
                np.r_[0, np.cumsum(ground)],
                np.array([float(e.text) for e in elev]),
                speed_mps,
                smoothing_window,
            )
        route.frame["latitude"], route.frame["longitude"] = lat[1:], lon[1:]
        route.name = Path(path).stem
        route.provenance.update(source="gpx", filename=Path(path).name)
        route.__post_init__()
        return route

    def subdivide(self, timestep_s: float) -> Route:
        """Uniform time segmentation conserving each parent's distance and duration."""
        if not np.isfinite(timestep_s) or timestep_s <= 0:
            raise ValueError("timestep must be positive")
        f = self.frame
        counts = np.maximum(1, np.ceil(f.dt_s.to_numpy() / timestep_s).astype(int))
        parents = np.repeat(np.arange(len(f)), counts)
        split = f.iloc[parents].copy().reset_index(drop=True)
        split["dt_s"] = f.dt_s.to_numpy()[parents] / counts[parents]
        split["length_m"] = f.length_m.to_numpy()[parents] / counts[parents]
        start_z = (
            f.elevation_m.to_numpy() - np.sin(np.arctan(f.grade.to_numpy())) * f.length_m.to_numpy()
        )
        fractions = np.concatenate([np.arange(1, n + 1) / n for n in counts])
        split["elevation_m"] = start_z[parents] + fractions * (
            f.elevation_m.to_numpy()[parents] - start_z[parents]
        )
        return Route(split, self.name, dict(self.provenance, uniform_timestep_s=timestep_s))

    def adaptive(
        self,
        max_length_m: float = 250,
        grade_delta: float = 0.01,
        speed_delta_mps: float = 0.5,
        wind_delta_mps: float = 1.0,
        temperature_delta_c: float = 2.0,
    ) -> Route:
        """Merge intervals until a reproducible change threshold or length limit is crossed."""
        thresholds = {
            "grade": grade_delta,
            "speed_mps": speed_delta_mps,
            "wind_mps": wind_delta_mps,
            "temperature_c": temperature_delta_c,
        }
        if max_length_m <= 0 or any(v <= 0 for v in thresholds.values()):
            raise ValueError("Adaptive thresholds must be positive")
        if self.frame.length_m.max() > max_length_m:
            # First enforce maximum segment length, preserving original changes.
            return self.uniform(max_length_m).adaptive(
                max_length_m, grade_delta, speed_delta_mps, wind_delta_mps, temperature_delta_c
            )
        groups, current = [], []
        for index, row in self.frame.iterrows():
            if current:
                first = self.frame.iloc[current[0]]
                change = any(
                    key in row and abs(row[key] - first[key]) >= limit
                    for key, limit in thresholds.items()
                )
                # Never merge across rider/assist/acceleration discontinuities.
                change |= any(
                    key in row and row[key] != first[key]
                    for key in [
                        "surface",
                        "human_power_w",
                        "assist_level",
                        "auxiliary_power_w",
                        "acceleration_mps2",
                    ]
                )
                if change or self.frame.iloc[current].length_m.sum() + row.length_m > max_length_m:
                    groups.append(current)
                    current = []
            current.append(index)
        if current:
            groups.append(current)
        rows = []
        for indices in groups:
            block = self.frame.iloc[indices]
            row = block.iloc[-1].to_dict()
            for key in block.select_dtypes(include="number"):
                row[key] = np.average(block[key], weights=block.dt_s)
            row["dt_s"] = block.dt_s.sum()
            row["length_m"] = block.length_m.sum()
            row["speed_mps"] = row["length_m"] / row["dt_s"]
            row["elevation_m"] = block.elevation_m.iloc[-1]
            rows.append(row)
        return Route(
            pd.DataFrame(rows),
            self.name,
            dict(
                self.provenance,
                adaptive_thresholds=thresholds,
                max_length_m=max_length_m,
                approximation="time-weighted merging; compare convergence before use",
            ),
        )

    def uniform(self, segment_length_m: float = 100) -> Route:
        """Uniform distance-grid segmentation preserving original discontinuities/stops."""
        if not np.isfinite(segment_length_m) or segment_length_m <= 0:
            raise ValueError("Uniform segment length must be positive")
        rows = []
        start = 0.0
        for source in self.frame.to_dict("records"):
            length = source["length_m"]
            if length == 0:
                rows.append(source)
                continue
            end = start + length
            first_boundary = (np.floor(start / segment_length_m) + 1) * segment_length_m
            boundaries = np.r_[start, np.arange(first_boundary, end - 1e-8, segment_length_m), end]
            start_z = source["elevation_m"] - np.sin(np.arctan(source["grade"])) * length
            for left, right in zip(boundaries[:-1], boundaries[1:]):
                row = dict(source)
                row["length_m"] = right - left
                row["dt_s"] = (right - left) / source["speed_mps"]
                row["elevation_m"] = start_z + (right - start) / length * (
                    source["elevation_m"] - start_z
                )
                rows.append(row)
            start = end
        return Route(
            pd.DataFrame(rows),
            self.name,
            dict(
                self.provenance,
                uniform_segment_length_m=segment_length_m,
                preserve_original_breakpoints=True,
            ),
        )


def route_from_config(config: Any) -> Route:
    options = dict(config.route)
    kind = options.pop("kind", "synthetic")
    if kind == "csv":
        return Route.from_csv(options.pop("path"))
    if kind == "gpx":
        return Route.from_gpx(**options)
    if kind == "synthetic":
        return Route.synthetic(**options)
    raise ValueError(f"Unknown route kind: {kind}")

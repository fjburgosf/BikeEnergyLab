"""Transparent quality reports and reproducible artifact exports."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, Path):
        return value.name
    return value


def write_json(path: Path, values: Any) -> None:
    path.write_text(
        json.dumps(json_safe(values), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def quality_report(frame: pd.DataFrame) -> dict[str, Any]:
    """Report issues without changing, removing or imputing a single data value."""
    if "route_id" in frame and frame.route_id.nunique(dropna=False) > 1:
        issues = []
        for group, positions in frame.groupby("route_id", sort=False, dropna=False).indices.items():
            child = quality_report(frame.iloc[positions].drop(columns="route_id"))
            for issue in child["issues"]:
                issue["rows_zero_based"] = [int(positions[row]) for row in issue["rows_zero_based"]]
                issue["route_id"] = str(group)
                issues.append(issue)
        missing_group = np.flatnonzero(frame.route_id.isna()).tolist()
        if missing_group:
            issues.append(
                {"code": "missing_route_id", "severity": "error", "rows_zero_based": missing_group}
            )
        return {
            "rows": len(frame),
            "columns": frame.columns.tolist(),
            "issues": issues,
            "valid": not any(issue["severity"] == "error" for issue in issues),
            "unit_policy": "SI; monotonicity and jumps checked within route groups",
            "modified": False,
        }
    issues = []

    def add(code: str, mask: Any, severity: str = "error") -> None:
        rows = np.flatnonzero(np.asarray(mask)).tolist()
        if rows:
            issues.append({"code": code, "severity": severity, "rows_zero_based": rows})

    add("missing_values", frame.isna().any(axis=1))
    add("duplicates", frame.duplicated(keep=False))
    numeric = frame.select_dtypes(include="number")
    add("nonfinite_values", ~np.isfinite(numeric.to_numpy()).all(axis=1))
    for key, (low, high) in {
        "soc": (0, 1),
        "speed_mps": (0, 30),
        "current_a": (-100, 100),
        "voltage_v": (0, 100),
        "temperature_c": (-60, 80),
        "assist_level": (0, 1),
        "grade": (-1, 1),
    }.items():
        if key in frame:
            add(f"implausible_{key}", ~frame[key].between(low, high))
    for key in ["distance_m", "time_s"]:
        if key in frame:
            add(f"nonmonotone_{key}", frame[key].diff() < 0)
    if "timestamp" in frame:
        stamp = pd.to_datetime(frame.timestamp, errors="coerce", utc=True)
        add("invalid_timestamp", stamp.isna())
        add("nonincreasing_timestamp", stamp.diff().dt.total_seconds() <= 0)
    if "elevation_m" in frame and "distance_m" in frame:
        dx = frame.distance_m.diff()
        add("elevation_jump", frame.elevation_m.diff().abs() > np.maximum(dx.abs(), 20), "warning")
    if {"latitude", "longitude"}.issubset(frame):
        add("invalid_latitude", ~frame.latitude.between(-90, 90))
        add("invalid_longitude", ~frame.longitude.between(-180, 180))
        lat, lon = np.radians(frame.latitude), np.radians(frame.longitude)
        hav = (
            np.sin(lat.diff() / 2) ** 2
            + np.cos(lat.shift()) * np.cos(lat) * np.sin(lon.diff() / 2) ** 2
        )
        jump = 6371000 * 2 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))
        add("gps_jump", jump > 1000, "warning")
    if {"distance_m", "speed_mps", "time_s"}.issubset(frame):
        expected = frame.speed_mps.shift().add(frame.speed_mps).div(2) * frame.time_s.diff()
        add(
            "distance_speed_unit_mismatch",
            (frame.distance_m.diff() - expected).abs() > np.maximum(5, expected.abs() * 0.2),
            "warning",
        )
    return {
        "rows": len(frame),
        "columns": frame.columns.tolist(),
        "issues": issues,
        "valid": not any(item["severity"] == "error" for item in issues),
        "unit_policy": "SI columns; heuristic checks cannot infer unknown units",
        "modified": False,
    }


def create_run(output: str | Path, config: Any, inputs: dict[str, pd.DataFrame]) -> Path:
    from bikeenergylab import __version__

    now = datetime.now(ZoneInfo("America/Bogota"))
    experiment_id = f"EXP-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
    destination = Path(output).resolve() / experiment_id
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "figures").mkdir()
    (destination / "logs").mkdir()
    values = config.to_dict()
    # Portable run config uses relative input basenames, without personal paths.
    if "route" in inputs:
        values["route"] = {"kind": "csv", "path": "route.csv"}
    if values["motor"].get("efficiency_map"):
        source = Path(values["motor"]["efficiency_map"])
        (destination / "motor_map.csv").write_bytes(source.read_bytes())
        values["motor"]["efficiency_map"] = "motor_map.csv"
    (destination / "config.yaml").write_text(
        yaml.safe_dump(values, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    dependencies = {}
    for name in ["numpy", "scipy", "pandas", "scikit-learn", "matplotlib", "PyYAML"]:
        dependencies[name] = importlib.metadata.version(name)
    hashes = {}
    for name, frame in inputs.items():
        content = frame.to_csv(index=False).encode("utf-8")
        (destination / f"{name}.csv").write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    # Hash all installed package source files so changed local code is distinguishable.
    package_root = Path(__file__).parents[1]
    if getattr(sys, "frozen", False):
        manifest = json.loads((package_root / "source_manifest.json").read_text(encoding="utf-8"))
        source_digest = manifest["source_sha256"]
    else:
        source_hash = hashlib.sha256()
        for source in sorted(package_root.rglob("*.py")):
            source_hash.update(source.relative_to(package_root).as_posix().encode())
            source_hash.update(source.read_bytes())
        source_digest = source_hash.hexdigest()
    metadata = {
        "experiment_id": experiment_id,
        "timestamp": now.isoformat(),
        "software_version": __version__,
        "seed": values["experiment"].get("seed", 42),
        "python": platform.python_version(),
        "platform": platform.system(),
        "dependencies": dependencies,
        "input_sha256": hashes,
        "source_sha256": source_digest,
    }
    write_json(destination / "metadata.json", metadata)
    write_json(
        destination / "parameters.json",
        {k: v for k, v in values.items() if k not in {"route", "experiment"}},
    )
    return destination


def export_simulation(result: Any, output: str | Path, figures: bool = True) -> Path:
    destination = create_run(
        output, result.config, {"route": result.route.frame, "predictions": result.trace}
    )
    write_json(destination / "summary.json", result.summary)
    write_json(destination / "route_metadata.json", result.route.provenance)
    if result.hybrid_model is not None:
        result.hybrid_model.save(destination / "hybrid_model")
    pd.DataFrame([{k: v for k, v in result.summary.items() if k != "decomposition"}]).to_csv(
        destination / "metrics.csv", index=False
    )
    status = "feasible" if result.summary["feasible"] else "incomplete or power-limited"
    (destination / "logs" / "run.log").write_text(
        f"Simulation finished: {status}\n", encoding="utf-8"
    )
    if figures:
        from ..visualization import simulation_figures

        simulation_figures(result, destination / "figures")
    return destination

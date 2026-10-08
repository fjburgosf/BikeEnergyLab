"""Package only the frozen Windows application and its runtime dependencies.

The nine end-user examples and eight-step tutorial are embedded in the EXE.
Registration documents and development evidence remain outside this archive.
"""

from __future__ import annotations

import hashlib
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist/BikeEnergyLab"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
EXE = TARGET / "BikeEnergyLab.exe"
INTERNAL = TARGET / "_internal"
if not EXE.is_file() or not INTERNAL.is_dir():
    raise FileNotFoundError("Build the onedir executable before packaging")

files = [EXE, *sorted(path for path in INTERNAL.rglob("*") if path.is_file())]
assert files and all(path.resolve().is_relative_to(TARGET.resolve()) for path in files)
archive = ROOT / f"dist/BikeEnergyLab-{VERSION}-windows-x64.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for path in files:
        bundle.write(path, (Path("BikeEnergyLab") / path.relative_to(TARGET)).as_posix())
print(f"Portable Windows package: {archive}")
print(f"Runtime entries: {len(files)}")
print(f"SHA256: {hashlib.sha256(archive.read_bytes()).hexdigest()}")

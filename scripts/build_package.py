"""Build source/wheel and materialize user-readable delivery files."""

import subprocess
import sys
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=root, check=True)
delivery = root / "dist" / "packages"
delivery.mkdir(exist_ok=True)
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
for name in [f"bikeenergylab-{version}-py3-none-any.whl", f"bikeenergylab-{version}.tar.gz"]:
    # A regular new file inherits directory permissions, unlike protected temporary
    # files some managed build environments atomically move to the final output.
    (delivery / name).write_bytes((root / "dist" / name).read_bytes())

"""Record installed direct and transitive packages with evaluated platform markers."""

import importlib.metadata as metadata
from pathlib import Path

from packaging.requirements import Requirement

ROOTS = [
    "numpy",
    "scipy",
    "pandas",
    "scikit-learn",
    "matplotlib",
    "PyYAML",
    "pytest",
    "ruff",
    "setuptools",
    "wheel",
    "build",
    "pyinstaller",
]
pending, seen, pins = list(ROOTS), set(), []
while pending:
    name = pending.pop()
    distribution = metadata.distribution(name)
    canonical = distribution.metadata["Name"].lower().replace("_", "-")
    if canonical in seen:
        continue
    seen.add(canonical)
    pins.append(f"{distribution.metadata['Name']}=={distribution.version}")
    for text in distribution.requires or []:
        requirement = Requirement(text)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            pending.append(requirement.name)
Path("requirements-lock.txt").write_text(
    "# Verified Windows / Python 3.12 environment; platform-specific pins.\n"
    + "\n".join(sorted(pins, key=str.lower))
    + "\n",
    encoding="utf-8",
)

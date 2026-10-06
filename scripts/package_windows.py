"""Materialize a complete portable Windows distribution and integrity manifest."""

import hashlib
import importlib.metadata as metadata
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist/BikeEnergyLab"
version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
if not (TARGET / "BikeEnergyLab.exe").is_file():
    raise FileNotFoundError("Build the executable before packaging")
for name in ["configs", "docs", "examples", "datasets"]:
    shutil.copytree(
        ROOT / name,
        TARGET / name,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "~$*"),
    )
for name in ["README.md", "CHANGELOG.md", "CITATION.cff", "LICENSE", "requirements-lock.txt"]:
    shutil.copyfile(ROOT / name, TARGET / name)
license_directory = TARGET / "THIRD_PARTY_LICENSES"
license_directory.mkdir(exist_ok=True)
notices = []
for name in [
    "numpy",
    "scipy",
    "pandas",
    "scikit-learn",
    "matplotlib",
    "PyYAML",
    "pillow",
    "joblib",
    "threadpoolctl",
    "contourpy",
    "cycler",
    "fonttools",
    "kiwisolver",
    "packaging",
    "pyparsing",
    "python-dateutil",
    "six",
    "tzdata",
]:
    distribution = metadata.distribution(name)
    copied = []
    for file in distribution.files or []:
        # Dist-info license resources remain attributable to their dependency.
        if ".dist-info/" in str(file).replace("\\", "/") and any(
            word in file.name.lower() for word in ["license", "copying", "notice"]
        ):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                parts = Path(str(file).replace("\\", "/")).parts
                metadata_index = next(
                    i for i, part in enumerate(parts) if part.endswith(".dist-info")
                )
                destination = license_directory / name / Path(*parts[metadata_index + 1 :])
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                copied.append(destination.relative_to(TARGET).as_posix())
    notices.append(
        {
            "dependency": distribution.metadata["Name"],
            "version": distribution.version,
            "license_expression": distribution.metadata.get("License-Expression"),
            "license_files": copied,
        }
    )
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    shutil.copyfile(python_license, license_directory / "Python-LICENSE.txt")
for directory in (Path(sys.base_prefix) / "tcl").glob("*"):
    for name in ["license.terms", "LICENSE"]:
        source = directory / name
        if source.is_file():
            shutil.copyfile(source, license_directory / f"{directory.name}-{name}.txt")
(TARGET / "THIRD_PARTY_NOTICES.json").write_text(json.dumps(notices, indent=2), encoding="utf-8")
(TARGET / "START_HERE.txt").write_text(
    f"BikeEnergyLab {version}\n\n"
    "Extraer la carpeta completa / Extract the complete folder.\n"
    "Abrir BikeEnergyLab.exe para la GUI / Open BikeEnergyLab.exe for the GUI.\n"
    "Inicio: menu Ejemplos y Tutorial / Home: Examples dropdown and Tutorial.\n"
    "Word: docs/docx (cinco documentos: usuario, tecnico, metodologia, descripcion y funciones).\n"
    "Manual: docs/user_manual.md; docs/windows_distribution.md\n"
    "CLI: BikeEnergyLab.exe simulate configs/flat.yaml --output results\n"
    "El programa funciona offline. Los ejemplos son sintéticos. / Offline; synthetic examples.\n"
    "Conservar _internal junto al ejecutable. / Keep _internal beside the executable.\n",
    encoding="utf-8",
)
manifest = {
    path.relative_to(TARGET).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(TARGET.rglob("*"))
    if path.is_file() and path.name != "SHA256SUMS.json"
}
(TARGET / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
archive = ROOT / f"dist/BikeEnergyLab-{version}-windows-x64.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for path in sorted(TARGET.rglob("*")):
        if path.is_file():
            bundle.write(path, path.relative_to(TARGET.parent).as_posix())
print(f"Portable Windows package: {archive}")
print(f"SHA256: {hashlib.sha256(archive.read_bytes()).hexdigest()}")

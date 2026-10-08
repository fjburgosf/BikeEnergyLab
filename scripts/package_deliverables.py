"""Collect only final manuals and ZIP archives, retaining QA records separately."""

import hashlib
import json
import shutil
import tarfile
import tomllib
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
TARGET = ROOT / "Entregables"
PORTABLE = ROOT / "dist/BikeEnergyLab"
TARGET.mkdir(exist_ok=True)
if not (PORTABLE / "BikeEnergyLab.exe").is_file():
    raise FileNotFoundError("Build and verify the executable first")
documents = sorted((ROOT / "docs/docx").glob(f"*_{VERSION}.docx"))
if len(documents) != 5:
    raise ValueError("Exactly five final Word documents are required")
portable_zip = ROOT / f"dist/BikeEnergyLab-{VERSION}-windows-x64.zip"
source_name = f"BikeEnergyLab-{VERSION}-codigo-fuente.zip"
allowed = {document.name for document in documents} | {portable_zip.name, source_name}
extras = [path for path in TARGET.iterdir() if path.name not in allowed]
if extras:
    backup = ROOT / "build" / ("delivery-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir(parents=True)
    for path in extras:
        if path.parent.resolve() != TARGET.resolve() or not path.resolve().is_relative_to(
            ROOT.resolve()
        ):
            raise ValueError(f"Unsafe delivery cleanup path: {path}")
        shutil.move(str(path), backup / path.name)
    print(f"Auxiliary files preserved in {backup.relative_to(ROOT)}")
for document in documents:
    shutil.copyfile(document, TARGET / document.name)
shutil.copyfile(portable_zip, TARGET / portable_zip.name)
source_zip = TARGET / source_name
with (
    tarfile.open(ROOT / f"dist/packages/bikeenergylab-{VERSION}.tar.gz") as sources,
    zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive,
):
    for member in sources.getmembers():
        if member.isfile():
            archive.writestr(member.name, sources.extractfile(member).read())

verification = ROOT / f"results/delivery-{VERSION}/verification"
verification.mkdir(parents=True, exist_ok=True)
records = [
    "results/release_verification.json",
    f"results/release-{VERSION}/acceptance.json",
    f"results/distribution-verification-{VERSION}/verification.json",
    f"results/documents-verification-{VERSION}.json",
    f"results/gui-button-verification-{VERSION}/source/verification.json",
    f"results/gui-button-verification-{VERSION}/windows/verification.json",
]
for relative in records:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f"Missing required verification: {relative}")
    if "gui-button-verification" in relative:
        report = json.loads(path.read_text(encoding="utf-8"))
        runtime = "windows" if "/windows/" in relative else "source"
        log = ROOT / f"results/build_logs/gui-buttons-{runtime}-v{VERSION}.log"
        if not report.get("passed") or "GUI smoke passed:" not in log.read_text(encoding="utf-8"):
            raise ValueError(f"GUI callbacks or button verification did not pass: {runtime}")
    destination = verification / relative.removeprefix("results/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)

(verification.parent / "delivery-instructions.txt").write_text(
    f"BikeEnergyLab {VERSION}\nContacto: fjburgosf@gmail.com\n\n"
    f"Extraer {portable_zip.name} fuera de Entregables y abrir BikeEnergyLab/BikeEnergyLab.exe.\n"
    "Conservar _internal y la carpeta extraída completa.\n"
    "Entregables contiene únicamente cinco documentos Word y dos archivos ZIP.\n"
    f"Código fuente: {source_zip.name}. Descomprimir e instalar según README.md.\n"
    f"Paquete portátil para compartir: {portable_zip.name}.\n"
    "Cargar ejemplo prepara el caso. Simular ejecuta el ejemplo activo.\n"
    "El flujo de ejemplos tiene dos acciones: Cargar ejemplo y Simular.\n"
    "Los registros de revisión se conservan fuera de Entregables.\n"
    "Las pruebas usan datos sintéticos. No certifican precisión de campo.\n",
    encoding="utf-8",
)
manifest = {
    path.relative_to(TARGET).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(TARGET.rglob("*"))
    if path.is_file() and path.name != "SHA256SUMS.json"
}
if set(manifest) != allowed or len(list(TARGET.iterdir())) != 7:
    raise ValueError("Entregables must contain only five DOCX and two ZIP archives")
(verification.parent / "SHA256SUMS.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(f"Deliverables: {TARGET}; {len(manifest)} files; source ZIP {source_zip.name}")

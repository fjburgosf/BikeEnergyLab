"""Collect the runnable Windows app, source ZIP, manuals and verification records."""

import hashlib
import json
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
TARGET = ROOT / "Entregables"
PORTABLE = ROOT / "dist/BikeEnergyLab"
TARGET.mkdir(exist_ok=True)
if not (PORTABLE / "BikeEnergyLab.exe").is_file():
    raise FileNotFoundError("Build and verify the executable first")
shutil.copytree(PORTABLE, TARGET, dirs_exist_ok=True)
for document in (ROOT / "docs/docx").glob("*.docx"):
    if document.name.endswith(f"_{VERSION}.docx"):
        shutil.copyfile(document, TARGET / document.name)
portable_zip = ROOT / f"dist/BikeEnergyLab-{VERSION}-windows-x64.zip"
shutil.copyfile(portable_zip, TARGET / portable_zip.name)
source_zip = TARGET / f"BikeEnergyLab-{VERSION}-codigo-fuente.zip"
with (
    tarfile.open(ROOT / f"dist/packages/bikeenergylab-{VERSION}.tar.gz") as sources,
    zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive,
):
    for member in sources.getmembers():
        if member.isfile():
            archive.writestr(member.name, sources.extractfile(member).read())

verification = TARGET / "Verificacion"
verification.mkdir(exist_ok=True)
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

publication = ROOT / "results/github_publication.json"
if publication.is_file():
    shutil.copyfile(publication, TARGET / "PUBLICACION_GITHUB.json")
    github_status = json.loads(publication.read_text(encoding="utf-8"))["status"]
else:
    github_status = "pending_repository_creation_approval"
(TARGET / "LEEME_ENTREGA.txt").write_text(
    f"BikeEnergyLab {VERSION}\nContacto: fjburgosf@gmail.com\n\n"
    "Abrir BikeEnergyLab.exe; conservar _internal y la carpeta completa.\n"
    "Los cinco documentos Word están en esta carpeta y en docs/docx.\n"
    f"Código fuente: {source_zip.name}. Descomprimir e instalar según README.md.\n"
    f"Paquete portátil para compartir: {portable_zip.name}.\n"
    "Cargar ejemplo prepara el caso; Simular ejecuta el ejemplo activo.\n"
    "El flujo de ejemplos tiene dos acciones: Cargar ejemplo y Simular.\n"
    "Verificacion contiene los registros de pruebas y documentos.\n"
    f"Estado de GitHub: {github_status}; consultar PUBLICACION_GITHUB.json.\n"
    "Las pruebas usan datos sintéticos; no certifican precisión de campo.\n",
    encoding="utf-8",
)
manifest = {
    path.relative_to(TARGET).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(TARGET.rglob("*"))
    if path.is_file() and path.name != "SHA256SUMS.json"
}
(TARGET / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Deliverables: {TARGET}; {len(manifest)} files; source ZIP {source_zip.name}")

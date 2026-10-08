"""Synchronize final deliverables from the immutable DNDA reference.

This script only reads Entregables/DNDA. It never deletes or writes there.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = (ROOT / "Entregables").resolve()
DNDA = (TARGET / "DNDA").resolve()
assert DNDA.is_dir() and DNDA.parent == TARGET

REFERENCE = (
    "Codigo_Fuente.zip",
    "Manual_de_usuario.docx",
    "Manual_de_usuario.pdf",
    "Manual_tecnico.docx",
    "Titulo_y_descripcion_de_funciones_BikeEnergyLab_1.0.0.docx",
)
PORTABLE = ROOT / "dist/BikeEnergyLab-1.0.0-windows-x64.zip"
DESCRIPTION = ROOT / "docs/docx/Descripcion_del_Software_BikeEnergyLab_1.0.0.docx"
EXPECTED = {
    *REFERENCE,
    "BikeEnergyLab-1.0.0-windows-x64.zip",
    "Descripcion_del_Software_BikeEnergyLab_1.0.0.docx",
}
assert all((DNDA / name).is_file() for name in REFERENCE)
assert PORTABLE.is_file() and DESCRIPTION.is_file()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = {name: sha(DNDA / name) for name in REFERENCE}
for name in REFERENCE[:-1]:
    shutil.copyfile(DNDA / name, TARGET / name)

functions_name = REFERENCE[-1]
buffer = io.BytesIO()
with ZipFile(DNDA / functions_name) as original, ZipFile(buffer, "w") as cleaned:
    for member in original.infolist():
        data = original.read(member.filename)
        if member.filename == "docProps/core.xml":
            text = data.decode("utf-8")
            old = "Corrección de auditoría del 8 de octubre de 2026"
            if text.count(old) != 1:
                raise ValueError("Unexpected DNDA functions metadata")
            data = text.replace(old, "Edición 1.0.0 del 8 de octubre de 2026").encode("utf-8")
        cleaned.writestr(member, data)
(TARGET / functions_name).write_bytes(buffer.getvalue())

shutil.copyfile(DESCRIPTION, TARGET / DESCRIPTION.name)
shutil.copyfile(PORTABLE, TARGET / PORTABLE.name)
after = {name: sha(DNDA / name) for name in REFERENCE}
assert before == after, "DNDA changed unexpectedly"
assert {path.name for path in TARGET.iterdir()} == EXPECTED | {"DNDA"}

manifest = {name: sha(TARGET / name) for name in sorted(EXPECTED)}
record = ROOT / "results/delivery-1.0.0/SHA256SUMS.json"
record.parent.mkdir(parents=True, exist_ok=True)
record.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(f"Entregables: {len(manifest)} files plus untouched DNDA reference")
print(f"DNDA SHA256 unchanged: {len(before)} files")

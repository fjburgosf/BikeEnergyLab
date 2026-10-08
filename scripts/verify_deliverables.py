"""Verify the seven final deliverables and the untouched DNDA reference."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "Entregables"
DNDA = TARGET / "DNDA"
REFERENCE_HASHES = {
    "Codigo_Fuente.zip": "da3421ccd548b13da1beebecc49debf1a464010a8b5efcecf44e61407062a962",
    "Manual_de_usuario.docx": "0a3d1a1c2f0345a67f74a62344a85b50d5d912548e815551356c5e8df29e444d",
    "Manual_de_usuario.pdf": "053cfaed059f34c40340186fe0eb94def9f727e7cac70257a30f746dbac63821",
    "Manual_tecnico.docx": "838e9b9653fc678290142518d3f43b7c7748b71a991ce3afcadd3a197b68b7da",
    "Titulo_y_descripcion_de_funciones_BikeEnergyLab_1.0.0.docx": "b97b53c8ce7db83fbec5ef3816b15f4876981688ca39a0614d382101b00bcb2c",
}
PORTABLE_NAME = "BikeEnergyLab-1.0.0-windows-x64.zip"
DESCRIPTION_NAME = "Descripcion_del_Software_BikeEnergyLab_1.0.0.docx"
FUNCTIONS_NAME = "Titulo_y_descripcion_de_funciones_BikeEnergyLab_1.0.0.docx"
EXPECTED = {*REFERENCE_HASHES, PORTABLE_NAME, DESCRIPTION_NAME}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text("utf-8"))


assert DNDA.is_dir() and DNDA.resolve().parent == TARGET.resolve()
assert {p.name for p in DNDA.iterdir()} == set(REFERENCE_HASHES)
assert {p.name for p in TARGET.iterdir()} == EXPECTED | {"DNDA"}
assert {name: sha(DNDA / name) for name in REFERENCE_HASHES} == REFERENCE_HASHES
manifest = read_json(ROOT / "results/delivery-1.0.0/SHA256SUMS.json")
actual = {name: sha(TARGET / name) for name in sorted(EXPECTED)}
assert actual == manifest
for name in [
    "Codigo_Fuente.zip",
    "Manual_de_usuario.docx",
    "Manual_de_usuario.pdf",
    "Manual_tecnico.docx",
]:
    assert actual[name] == REFERENCE_HASHES[name]

with ZipFile(DNDA / FUNCTIONS_NAME) as reference, ZipFile(TARGET / FUNCTIONS_NAME) as clean:
    assert reference.namelist() == clean.namelist()
    assert reference.testzip() is None and clean.testzip() is None
    for name in reference.namelist():
        if name == "docProps/core.xml":
            original = reference.read(name).decode("utf-8")
            updated = clean.read(name).decode("utf-8")
            assert updated == original.replace(
                "Corrección de auditoría del 8 de octubre de 2026",
                "Edición 1.0.0 del 8 de octubre de 2026",
            )
            assert updated != original
        else:
            assert reference.read(name) == clean.read(name), name

review = read_json(ROOT / "results/documents-verification-1.0.0.json")
assert review["version"] == "1.0.0" and len(review["documents"]) == 4
assert review["total_pages"] == 67
mapping = {
    "Manual_de_usuario_BikeEnergyLab_1.0.0.docx": "Manual_de_usuario.docx",
    "Manual_tecnico_BikeEnergyLab_1.0.0.docx": "Manual_tecnico.docx",
    DESCRIPTION_NAME: DESCRIPTION_NAME,
    FUNCTIONS_NAME: FUNCTIONS_NAME,
}
for entry in review["documents"]:
    root_name = mapping[Path(entry["path"]).name]
    assert sha(ROOT / entry["path"]) == entry["sha256"] == actual[root_name]
    with ZipFile(TARGET / root_name) as doc:
        assert doc.testzip() is None
        assert not any(
            "auditor" in doc.read(name).decode("utf-8", errors="ignore").lower()
            for name in ["word/document.xml", "docProps/core.xml"]
        )

source_path = TARGET / "Codigo_Fuente.zip"
with ZipFile(source_path) as source:
    names = source.namelist()
    assert source.testzip() is None and len(names) == 40
    assert all(name.startswith("bikeenergylab-1.0.0/") for name in names)
    assert all(
        not any(
            part in {"docs", "results", "scripts", "tests", "build", "dist"}
            for part in Path(name).parts
        )
        for name in names
    )
    assert any(name.endswith("/examples/run_examples.py") for name in names)
    assert any(name.endswith("/src/bikeenergylab/gui/app.py") for name in names)

portable_path = TARGET / PORTABLE_NAME
assert sha(portable_path) == sha(ROOT / "dist" / PORTABLE_NAME)
with ZipFile(portable_path) as portable:
    names = portable.namelist()
    assert portable.testzip() is None and len(names) == 2703
    assert len(set(names)) == len(names)
    assert all(
        name == "BikeEnergyLab/BikeEnergyLab.exe" or name.startswith("BikeEnergyLab/_internal/")
        for name in names
    )
    for name in names:
        staged = ROOT / "dist" / Path(name)
        assert staged.is_file() and data_sha(portable.read(name)) == sha(staged), name

release = read_json(ROOT / "results/release_verification.json")
assert release["artifact_sha256"]["dist/BikeEnergyLab/BikeEnergyLab.exe"] == sha(
    ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"
)
assert release["artifact_sha256"][f"dist/{PORTABLE_NAME}"] == actual[PORTABLE_NAME]
acceptance_path = ROOT / "build/runtime-check-20261008-152204/acceptance/verification.json"
acceptance = read_json(acceptance_path)
assert (
    acceptance["version"] == "1.0.0" and acceptance["passed"] and acceptance["cases_passed"] == 114
)
assert all(case["passed"] for case in acceptance["cases"])

stamp = datetime.now(timezone.utc).isoformat()
portable_report = {
    "version": "1.0.0",
    "completed_utc": stamp,
    "passed": True,
    "archive": str(portable_path.relative_to(ROOT)).replace("\\", "/"),
    "archive_sha256": actual[PORTABLE_NAME],
    "files_verified": len(names),
    "exe_sha256": sha(ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"),
    "isolated_gui_cases_passed": 114,
    "isolated_gui_report": str(acceptance_path.relative_to(ROOT)).replace("\\", "/"),
    "runtime_only": True,
}
delivery_report = {
    "version": "1.0.0",
    "completed_utc": stamp,
    "passed": True,
    "files_verified": len(actual),
    "dnda_files_untouched": len(REFERENCE_HASHES),
    "dnda_sha256": REFERENCE_HASHES,
    "source_zip_sha256": actual["Codigo_Fuente.zip"],
    "portable_zip_sha256": actual[PORTABLE_NAME],
    "reviewed_docx": 4,
    "reviewed_pages": review["total_pages"],
    "functions_metadata_cleaned_in_entregables_only": True,
    "source_archive_compact": True,
    "portable_archive_runtime_only": True,
}
for name, record in [
    ("portable-verification-1.0.0.json", portable_report),
    ("deliverables-verification-1.0.0.json", delivery_report),
]:
    path = ROOT / "results" / name
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", "utf-8")
    mirror = ROOT / "results/delivery-1.0.0/verification" / name
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_bytes(path.read_bytes())
print(
    json.dumps(
        {
            "passed": True,
            "files": len(actual),
            "source_entries": 40,
            "portable_entries": len(names),
            "gui_cases": 114,
            "dnda_unchanged": True,
        }
    )
)

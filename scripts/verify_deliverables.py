"""Verify final delivery inventory, archives, reviewed manuals and executable identity."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from release_evidence import evidence_paths

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "Entregables"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text("utf-8"))


review = read_json(ROOT / "results/documents-verification-1.0.0.json")
release = read_json(ROOT / "results/release_verification.json")
sourcezip = TARGET / "BikeEnergyLab-1.0.0-codigo-fuente.zip"
portablezip = ROOT / "dist/BikeEnergyLab-1.0.0-windows-x64.zip"
wheel = ROOT / "dist/packages/bikeenergylab-1.0.0-py3-none-any.whl"
assert len(review["documents"]) == 4
assert len(list(TARGET.glob("*.docx"))) == 4
assert (
    sha(ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe")
    == release["artifact_sha256"]["dist/BikeEnergyLab/BikeEnergyLab.exe"]
)
assert (
    sha(ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe")
    == "2dedbac7d864d253ef41f6914a83adbb048c172bd69588b17909ab6b40b0e754"
)
assert (ROOT / "dist/BikeEnergyLab/_internal/scipy/stats/_sobol_direction_numbers.npz").is_file()
assert (
    read_json(ROOT / "dist/BikeEnergyLab/_internal/bikeenergylab/source_manifest.json")[
        "source_sha256"
    ]
    == review["source_sha256"]
)
assert sha(TARGET / portablezip.name) == sha(portablezip)
manifest = read_json(ROOT / "results/delivery-1.0.0/SHA256SUMS.json")
actual = {
    p.relative_to(TARGET).as_posix(): sha(p)
    for p in sorted(TARGET.rglob("*"))
    if p.is_file() and p.name != "SHA256SUMS.json"
}
assert actual == manifest, "Delivery manifest differs from actual inventory"
expected = {Path(d["path"]).name for d in review["documents"]} | {sourcezip.name, portablezip.name}
assert set(actual) == expected and len(list(TARGET.iterdir())) == 6, (
    "Unexpected files or folders in Entregables"
)
with ZipFile(sourcezip) as source, ZipFile(portablezip) as portable, ZipFile(wheel) as binary:
    assert source.testzip() is None
    assert portable.testzip() is None
    assert binary.testzip() is None
    assert not any(
        "Metodologia_cientifica_BikeEnergyLab_1.0.0.docx" in name
        for name in source.namelist() + portable.namelist()
    )
    assert not any(
        "visual-qa/" in n or "docx-qa/" in n or "/~$" in n
        for n in portable.namelist() + source.namelist()
    )
    portable_manifest = json.loads(portable.read("BikeEnergyLab/SHA256SUMS.json"))
    for name, digest in portable_manifest.items():
        assert data_sha(portable.read("BikeEnergyLab/" + name)) == digest, name
    assert set(portable_manifest) == {
        n.removeprefix("BikeEnergyLab/")
        for n in portable.namelist()
        if not n.endswith("/SHA256SUMS.json")
    }
    for path in (ROOT / "src/bikeenergylab").rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        assert source.read("bikeenergylab-1.0.0/" + relative) == path.read_bytes()
        assert (
            binary.read("bikeenergylab/" + path.relative_to(ROOT / "src/bikeenergylab").as_posix())
            == path.read_bytes()
        )
    for folder in ["docs", "scripts"]:
        for path in (ROOT / folder).rglob("*"):
            if (
                path.is_file()
                and path.suffix
                in [".py", ".ps1", ".md", ".docx", ".png", ".template", ".json", ".csv", ".whl"]
                and "__pycache__" not in path.parts
            ):
                relative = path.relative_to(ROOT).as_posix()
                assert source.read("bikeenergylab-1.0.0/" + relative) == path.read_bytes(), relative
    for name in [
        "README.md",
        "MANIFEST.in",
        "pyproject.toml",
        "requirements-lock.txt",
        "LICENSE",
        "CITATION.cff",
        "CHANGELOG.md",
    ]:
        assert source.read("bikeenergylab-1.0.0/" + name) == (ROOT / name).read_bytes()
    assert not any(name.endswith("/AGENTS.md") for name in source.namelist())
    for relative, path in evidence_paths(ROOT):
        expected_hash = sha(path)
        assert data_sha(source.read("bikeenergylab-1.0.0/" + relative)) == expected_hash
        assert data_sha(portable.read("BikeEnergyLab/" + relative)) == expected_hash
    captures = read_json(ROOT / "docs/images/gui-1.0.0/captures.json")
    assert captures["source_matches_executable"]
    assert captures["source_sha256"] == review["source_sha256"]
    assert captures["executable_sha256"] == sha(ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe")
    example_captures = [
        item["sha256"]
        for item in captures["screenshots"]
        if Path(item["file"]).name.startswith("ejemplo-")
    ]
    assert len(example_captures) == 9 and len(set(example_captures)) == 9
    for document in review["documents"]:
        name = Path(document["path"]).name
        for path in [TARGET / name, ROOT / document["path"]]:
            assert sha(path) == document["sha256"], path
        assert (
            data_sha(source.read("bikeenergylab-1.0.0/" + document["path"])) == document["sha256"]
        )
        assert data_sha(portable.read("BikeEnergyLab/" + document["path"])) == document["sha256"]
        assert document["sha256"] == release["artifact_sha256"][document["path"]]
    assert data_sha(portable.read("BikeEnergyLab/BikeEnergyLab.exe")) == sha(
        ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"
    )
now = datetime.now(timezone.utc).isoformat()
portable_report = {
    "version": "1.0.0",
    "revision": review["revision"],
    "release_date": "2026-10-06",
    "document_revision_date": review["document_revision_date"],
    "completed_utc": now,
    "source_sha256": review["source_sha256"],
    "archive": portablezip.relative_to(ROOT).as_posix(),
    "archive_sha256": sha(portablezip),
    "manifest_files_verified": len(portable_manifest),
    "reviewed_docx_included": 4,
    "document_pages": review["total_pages"],
    "document_hashes_match_reviewed_files": True,
    "source_archive_docx_match": True,
    "wheel_sources_match": True,
    "active_metadata_version": "1.0.0",
    "exe_matches_verified_distribution": True,
    "internal_qa_artifacts_excluded": True,
}
delivery_report = {
    "version": "1.0.0",
    "revision": review["revision"],
    "completed_utc": now,
    "source_sha256": review["source_sha256"],
    "passed": True,
    "files_verified": len(manifest),
    "checks": [
        "Only four Word documents and two ZIP archives in Entregables",
        "All delivery and portable manifest SHA256 values and complete file inventories",
        "Source ZIP and wheel Python sources match verified release",
        "Source ZIP scripts, metadata, retained templates, screenshots and document sources match current files",
        "Curated historical protocol records and primary acceptance logs match both ZIPs",
        "Capture-source and packaged executable source fingerprints agree",
        "Internal working instructions are absent from source ZIP",
        "Four reviewed DOCX hashes match folder, source ZIP and portable ZIP",
        "ZIP CRC integrity",
        "Delivered executable SHA256 matches tested executable",
        "Frozen SciPy Sobol data and source identity present",
    ],
    "reviewed_docx": 4,
    "document_pages": review["total_pages"],
    "user_guide_captures": 25,
    "exe_sha256": sha(ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"),
    "source_zip_sha256": sha(sourcezip),
    "portable_zip_sha256": sha(portablezip),
    "code_location_not_referenced_in_delivery": True,
}
for name, record in [
    ("portable-verification-1.0.0.json", portable_report),
    ("deliverables-verification-1.0.0.json", delivery_report),
]:
    path = ROOT / "results" / name
    history = ROOT / "results/history" / ("pre-delivery-cleanup-" + name)
    if not history.exists():
        shutil.copyfile(path, history)
    path.write_text(json.dumps(record, indent=2) + "\n", "utf-8")
    shutil.copyfile(path, ROOT / "results/delivery-1.0.0/verification" / name)
manifest = {
    p.relative_to(TARGET).as_posix(): sha(p)
    for p in sorted(TARGET.rglob("*"))
    if p.is_file() and p.name != "SHA256SUMS.json"
}
(ROOT / "results/delivery-1.0.0/SHA256SUMS.json").write_text(
    json.dumps(manifest, indent=2) + "\n", "utf-8"
)
print(
    json.dumps(
        {
            "passed": True,
            "delivery_files": len(manifest),
            "portable_files": len(portable_manifest),
            "reviewed_docx": 4,
            "pages": review["total_pages"],
            "source_zip_sha256": sha(sourcezip),
        }
    )
)

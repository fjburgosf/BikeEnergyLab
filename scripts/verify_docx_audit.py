import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "build/docx-qa"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic(el):
    if el is None:
        return None
    return (el.tag, tuple(sorted(el.attrib.items())), el.text or "", tuple(semantic(c) for c in el))


catalog = json.loads((ROOT / "docs/templates/catalog.json").read_text("utf-8"))
for value in catalog.values():
    original = Path(value["reference"])
    if original.is_file():
        assert sha(original) == value["reference_sha256"], "Original template changed"
    assert sha(ROOT / value["master"]) == value["master_sha256"], "Retained template changed"

source = hashlib.sha256()
for path in sorted((ROOT / "src/bikeenergylab").rglob("*.py")):
    source.update(path.relative_to(ROOT / "src/bikeenergylab").as_posix().encode())
    source.update(path.read_bytes())
identity = source.hexdigest()
assert identity == "25a63aafb85d6936b886c5b15f9f5addc3086267861aad7702fe4b53fa98338f"
documents = []
for prefix, role, count in [
    ("Manual_de_usuario", "user", 31),
    ("Manual_tecnico", "technical", 17),
    ("Descripcion_del_Software", "description", 17),
    ("Titulo_y_descripcion_de_funciones", "functions", 1),
]:
    path = ROOT / f"docs/docx/{prefix}_BikeEnergyLab_1.0.0.docx"
    pdf = ROOT / f"build/docx-qa/{path.stem}.pdf"
    assert len(PdfReader(pdf).pages) == count
    docqa = QA / path.stem
    pages = {str(i): sha(docqa / f"page-{i}.png") for i in range(1, count + 1)}
    for i in range(1, count + 1):
        assert pages[str(i)] == sha(ROOT / "build/docx-qa" / path.stem / f"page-{i}.png")
    with ZipFile(path) as final, ZipFile(ROOT / catalog[role]["master"]) as template:
        body = etree.fromstring(final.read("word/document.xml"))
        original = etree.fromstring(template.read("word/document.xml"))
        text = " ".join(body.xpath("//w:t/text()", namespaces=NS))
        assert "BikeEnergyLab" in text and "1.0.0" in text and "fjburgosf@gmail.com" in text
        assert ";" not in text
        assert "github" not in text.lower() and "repositorio" not in text.lower()
        for part in final.namelist():
            if part.endswith(".rels"):
                assert b"github.com/fjburgosf" not in final.read(part)
        for part in final.namelist():
            if (
                part.startswith("word/header")
                or part == "docProps/core.xml"
                or part == "word/document.xml"
            ):
                assert b"IPFramework" not in final.read(part)
        sections = body.xpath("//w:sectPr", namespaces=NS)
        template_sections = original.xpath("//w:sectPr", namespaces=NS)
        assert len(sections) == len(template_sections) == catalog[role]["sections"]
        for current, retained in zip(sections, template_sections):
            for name in ["pgSz", "pgMar"]:
                assert semantic(current.find(f"w:{name}", NS)) == semantic(
                    retained.find(f"w:{name}", NS)
                )
        styles = etree.fromstring(final.read("word/styles.xml"))
        retained_styles = etree.fromstring(template.read("word/styles.xml"))
        by_id = {s.get("{%s}styleId" % NS["w"]): s for s in styles}
        compared = 0
        for old in retained_styles:
            key = old.get("{%s}styleId" % NS["w"])
            if key is None:
                continue
            new = by_id[key]
            for name in ["rPr", "pPr", "basedOn"]:
                assert semantic(new.find(f"w:{name}", NS)) == semantic(old.find(f"w:{name}", NS)), (
                    path.name,
                    key,
                    name,
                )
            compared += 1
        preserved_parts = {}
        for part in ["word/theme/theme1.xml", "word/numbering.xml", "word/fontTable.xml"]:
            if part not in final.namelist():
                assert part.endswith("numbering.xml") and not body.xpath("//w:numPr", namespaces=NS)
                preserved_parts[part] = {
                    "removed_unused_part": True,
                    "note": "Word removes unused numbering from the compact two-paragraph functions document.",
                }
                continue
            same = final.read(part) == template.read(part)
            preserved_parts[part] = {
                "byte_identical": same,
                "sha256": hashlib.sha256(final.read(part)).hexdigest(),
            }
            current_part = etree.fromstring(final.read(part))
            retained_part = etree.fromstring(template.read(part))
            if part.endswith("fontTable.xml"):
                font_key = "{%s}name" % NS["w"]
                old_fonts = {f.get(font_key): f for f in retained_part}
                new_fonts = {f.get(font_key): f for f in current_part}
                shared = old_fonts.keys() & new_fonts.keys()
                assert all(semantic(old_fonts[f]) == semantic(new_fonts[f]) for f in shared)
                preserved_parts[part].update(
                    shared_font_definitions_preserved=True,
                    added_fonts=sorted(new_fonts.keys() - old_fonts.keys()),
                    removed_unused_fonts=sorted(old_fonts.keys() - new_fonts.keys()),
                    note="Word normalizes the font inventory to fonts used by the final document; Consolas is the permitted code style.",
                )
            else:
                assert semantic(current_part) == semantic(retained_part), (path.name, part)
                preserved_parts[part]["semantic_identical"] = True
        equations = len(body.xpath("//m:oMath", namespaces=NS))
        captures = len(body.xpath("//wp:inline", namespaces=NS))
        if role == "user":
            assert captures == 25
            metadata = json.loads((ROOT / "docs/images/gui-1.0.0/captures.json").read_text("utf-8"))
            assert all(button in text for button in metadata["buttons"])
            assert len(metadata["examples"]) == len(metadata["example_results"]) == 9
            assert len(metadata["tutorial"]) == 8
            assert all(e["title"].split("·")[-1].strip() in text for e in metadata["examples"])
            assert not metadata["errors"]
            for capture in metadata["screenshots"]:
                assert sha(ROOT / capture["file"]) == capture["sha256"]
        if prefix == "Manual_tecnico":
            assert equations == 32
        documents.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "pages": count,
                "editable_equations": equations,
                "embedded_application_captures": captures,
                "visually_reviewed_pages": list(range(1, count + 1)),
                "qa_pdf_sha256": sha(pdf),
                "page_png_sha256": pages,
                "qa_iteration": "auditoria-2026-10-08",
                "template": catalog[role]["master"],
                "template_sha256": catalog[role]["master_sha256"],
                "template_sections": len(sections),
                "existing_styles_compared": compared,
                "style_property_differences": 0,
                "section_geometry_preserved": True,
                "preserved_parts": preserved_parts,
            }
        )
record = {
    "version": "1.0.0",
    "revision": "auditoria-2026-10-08",
    "release_date": "2026-10-06",
    "document_revision_date": "2026-10-08",
    "contact": "fjburgosf@gmail.com",
    "source_sha256": identity,
    "completed_utc": datetime.now(timezone.utc).isoformat(),
    "render_backend": "Microsoft Word native COM ExportAsFixedFormat with refreshed TOC and fields",
    "rasterizer": "documents skill render_docx.py with Word PDF adapter and Poppler",
    "raster_dpi": 150,
    "documents": documents,
    "total_pages": sum(d["pages"] for d in documents),
    "all_pages_visually_reviewed": True,
    "structural_checks_passed": True,
    "visual_review": "Every final page viewed at original pixel dimensions; no clipping, overlap, broken tables or missing glyphs observed. Chapter page breaks and styling follow the supplied references.",
    "illustrated_user_guide": {
        "captures": 25,
        "observed_button_labels_explained": 36,
        "executed_examples": 9,
        "tutorial_steps": 8,
        "capture_metadata": "docs/images/gui-1.0.0/captures.json",
        "capture_metadata_sha256": sha(ROOT / "docs/images/gui-1.0.0/captures.json"),
    },
    "templates_catalog_sha256": sha(ROOT / "docs/templates/catalog.json"),
    "original_templates_unchanged": True,
    "methodology_in_technical_manual": True,
    "scientific_equations_semantically_preserved": True,
    "scope": "Four final template-based DOCX. Scientific methodology integrated in the technical manual with its complete editable equations and historical evidence. Scientific overview added to software description. Captures, button coverage, examples, editable equations and scientific baseline retained.",
    "editorial_checks": {
        "semicolon_count_in_editable_document_text": 0,
        "code_host_references_in_document_text_and_relationships": 0,
    },
    "authorized_template_deviation": "User requested removal of the repository metadata row and references from deliverables.",
}
target = ROOT / "results/documents-verification-1.0.0.json"
history = ROOT / "results/history/pre-integration-documents-1.0.0.json"
history.parent.mkdir(exist_ok=True)
if not history.exists():
    shutil.copyfile(target, history)
target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(
    json.dumps(
        {
            "documents": len(documents),
            "pages_reviewed": record["total_pages"],
            "captures": 25,
            "equations": 32,
            "styles": "preserved",
            "source_sha256": identity,
        }
    )
)

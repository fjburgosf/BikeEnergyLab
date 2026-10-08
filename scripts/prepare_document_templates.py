"""Retain the supplied Word design without redistributing its previous content."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/templates"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
FILES = {
    "user": "manual_de_usuario.docx",
    "technical": "manual_tecnico.docx",
    "description": "Descripcion_del_Software.docx",
    "functions": "titulo_ y_descripcion_de_funciones.docx",
}


def sanitized_xml(raw):
    xml = etree.fromstring(raw)
    for p in xml.xpath("//w:p", namespaces=NS):
        for child in list(p):
            if child.tag == f"{{{NS['w']}}}pPr":
                continue
            if child.tag == f"{{{NS['w']}}}r":
                for node in list(child):
                    if node.tag != f"{{{NS['w']}}}rPr":
                        child.remove(node)
            else:
                p.remove(child)
    return etree.tostring(xml, xml_declaration=True, encoding="UTF-8", standalone=True)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare sanitized design masters from supplied Word templates"
    )
    parser.add_argument("--reference-dir", type=Path, required=True)
    reference = parser.parse_args().reference_dir
    OUT.mkdir(exist_ok=True)
    catalog = {}
    for key, filename in FILES.items():
        source = reference / filename
        with zipfile.ZipFile(source) as original:
            body = etree.fromstring(original.read("word/document.xml"))
            preserved = [
                n
                for n in original.namelist()
                if n in ["word/styles.xml", "word/numbering.xml", "word/fontTable.xml"]
                or n.startswith("word/theme/")
            ]
            inventory = {
                n: {
                    "size": len(original.read(n)),
                    "sha256": hashlib.sha256(original.read(n)).hexdigest(),
                }
                for n in original.namelist()
            }
            target = OUT / f"{key}.template"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as clean:
                for name in original.namelist():
                    if name.startswith("word/media/") or name.startswith("docProps/"):
                        continue
                    raw = original.read(name)
                    if name == "word/document.xml" or (
                        name.startswith("word/")
                        and name.split("/")[-1].startswith(
                            ("header", "footer", "comments", "footnotes", "endnotes")
                        )
                        and name.endswith(".xml")
                    ):
                        raw = sanitized_xml(raw)
                    elif name.endswith(".rels"):
                        xml = etree.fromstring(raw)
                        for rel in list(xml):
                            if rel.get("Type", "").split("/")[-1] in [
                                "image",
                                "hyperlink",
                                "core-properties",
                                "extended-properties",
                                "custom-properties",
                            ]:
                                xml.remove(rel)
                        raw = etree.tostring(
                            xml, xml_declaration=True, encoding="UTF-8", standalone=True
                        )
                    elif name == "[Content_Types].xml":
                        xml = etree.fromstring(raw)
                        for item in list(xml):
                            if item.get("PartName", "").startswith(("/word/media/", "/docProps/")):
                                xml.remove(item)
                        raw = etree.tostring(
                            xml, xml_declaration=True, encoding="UTF-8", standalone=True
                        )
                    clean.writestr(name, raw)
            # The source body is inspected solely to locate real template roles.
            paragraphs = body.xpath("/w:document/w:body/w:p", namespaces=NS)
            divider = next(
                (i for i, p in enumerate(paragraphs[:10]) if p.xpath(".//w:pBdr", namespaces=NS)),
                None,
            )
            catalog[key] = {
                "reference": str(source),
                "reference_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "master": target.relative_to(ROOT).as_posix(),
                "master_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "sections": len(body.xpath("//w:sectPr", namespaces=NS)),
                "title_paragraph": 0,
                "subtitle_paragraph": 1,
                "introduction_paragraph": 2 if key == "description" else 5,
                "divider_paragraph": divider,
                "preserve_parts": {n: inventory[n] for n in preserved},
                "package_inventory": inventory,
            }
            assert (
                hashlib.sha256(source.read_bytes()).hexdigest() == catalog[key]["reference_sha256"]
            )
    (OUT / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Retained four sanitized design masters; original files unchanged")


if __name__ == "__main__":
    main()

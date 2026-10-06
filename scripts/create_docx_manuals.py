"""Build three Spanish manuals with bundled python-docx and editable Word math.

Run with the Python returned by load_workspace_dependencies, then render every page.
"""

from __future__ import annotations

import csv
import hashlib
import re
import tomllib
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/docx"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
RELEASE_DATE = date.fromisoformat(
    re.search(
        r"^date-released: (\d{4}-\d{2}-\d{2})$",
        (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        re.MULTILINE,
    )[1]
)
BLACK = RGBColor(0, 0, 0)


def sub(base, index):
    return ("sub", base, index)


def sup(base, power):
    return ("sup", base, power)


def frac(top, bottom):
    return ("frac", top, bottom)


def math_node(token):
    if isinstance(token, str):
        run = OxmlElement("m:r")
        text = OxmlElement("m:t")
        text.text = token
        run.append(text)
        return run
    kind, a, b = token
    if kind in {"sub", "sup"}:
        node = OxmlElement("m:sSub" if kind == "sub" else "m:sSup")
        first, second = "m:e", "m:sub" if kind == "sub" else "m:sup"
    elif kind == "frac":
        node = OxmlElement("m:f")
        first, second = "m:num", "m:den"
    else:
        raise ValueError(kind)
    for key, items in [(first, a), (second, b)]:
        child = OxmlElement(key)
        for item in items if isinstance(items, list) else [items]:
            child.append(math_node(item))
        node.append(child)
    return node


def add_equation(doc, tokens):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(7)
    math = OxmlElement("m:oMath")
    for token in tokens:
        math.append(math_node(token))
    p._p.append(math)


EQUATIONS = {
    "forces": [
        [
            "θ = atan(grade)     m = ",
            sub("m", "bike"),
            " + ",
            sub("m", "rider"),
            " + ",
            sub("m", "cargo"),
        ],
        [
            sub("F", "roll"),
            " = mg",
            sub("C", "rr"),
            "cos(θ)     ",
            sub("F", "grade"),
            " = mg sin(θ)",
        ],
        [
            sub("v", "rel"),
            " = v − w     ",
            sub("F", "aero"),
            " = ",
            frac("1", "2"),
            "ρ",
            sub("C", "d"),
            "A",
            sub("v", "rel"),
            "|",
            sub("v", "rel"),
            "|",
        ],
        [sub("F", "acc"), " = ma"],
    ],
    "wheel": [
        [
            sub("P", "wheel"),
            " = (",
            sub("F", "roll"),
            " + ",
            sub("F", "grade"),
            " + ",
            sub("F", "aero"),
            " + ",
            sub("F", "acc"),
            ")v",
        ]
    ],
    "density": [["ρ = ", frac("p", "287.05(T + 273.15)"), "     T en °C"]],
    "power": [
        [
            sub("P", "human wheel"),
            " = ",
            sub("η", "drive"),
            sub("P", "pedal"),
            "     limitado a demanda positiva",
        ],
        [
            sub("P", "shaft"),
            " = ",
            frac(sub("P", "motor wheel"), sub("η", "drive")),
            "     ",
            sub("P", "electric motor"),
            " = ",
            frac(sub("P", "shaft"), sub("η", "motor")),
        ],
    ],
    "capacity": [
        [sub("E", "full"), " = ", sub("E", "nominal"), sub("f", "usable"), sub("f", "temperature")],
        [
            sub("E", "available"),
            " = ",
            sub("E", "full"),
            "(",
            sub("SOC", "initial"),
            " − ",
            sub("SOC", "min"),
            ")",
        ],
    ],
    "soc": [
        [
            "ΔSOC = −",
            frac([sub("P", "terminal"), "Δt"], ["3600", sub("E", "full")]),
            "     Δt en s y E en Wh",
        ]
    ],
    "ecm": [
        ["V = OCV(SOC) − ", sub("R", "0"), "I − ", sub("V", "RC")],
        [
            frac(["d", sub("V", "RC")], "dt"),
            " = −",
            frac(sub("V", "RC"), [sub("R", "1"), sub("C", "1")]),
            " + ",
            frac("I", sub("C", "1")),
        ],
        ["ΔSOC = −", frac("IΔt", ["3600", sub("Q", "effective")]), "     Q en Ah"],
    ],
    "terminal": [
        [
            sub("P", "terminal"),
            " = ",
            sub("P", "electric motor"),
            " + ",
            sub("P", "aux"),
            " − ",
            sub("P", "regen"),
        ]
    ],
    "fit": [
        [
            "θ* = ",
            sub("arg min", "θ"),
            sub("Σ", "i"),
            sub("w", "i"),
            sup(["(", sub("E", "pred i"), "(θ) − ", sub("E", "obs i"), ")"], "2"),
        ]
    ],
    "residual": [
        [
            sub("r", "i"),
            " = ",
            frac([sub("E", "obs i"), " − ", sub("E", "phys i")], sub("L", "i")),
            "     r en Wh/km",
        ]
    ],
    "models": [
        ["M1     Ê = ", sub("E", "phys"), "        M2     Ê = ", sub("E", "data")],
        ["M3     Ê = ", sub("E", "phys"), " + r̂L"],
        ["M4     Ê = ", sub("E", "phys"), " + α(x)r̂L"],
    ],
    "gate": [
        [
            "α(x) = ",
            frac("n", "n + 20"),
            frac(["exp(−", sup("max(d − 1, 0)", "2"), ")"], ["1 + ", sup("u", "2")]),
        ]
    ],
    "conformal": [
        ["k = ⌈(n + 1)c⌉"],
        [sub("I", "c"), " = [Ê − ", sub("q", "c"), "L, Ê + ", sub("q", "c"), "L]"],
    ],
    "mission": [["p̂ = ", frac([sub("N", "successful")], "N")]],
    "sobol": [
        [
            sub("S", "i"),
            " = ",
            frac(["mean[(f(B) − f̄)(f(", sub("AB", "i"), ") − f(A))]"], "Var(f)"),
        ],
        [
            sub("ST", "i"),
            " = ",
            frac(["mean[", sup(["(f(A) − f(", sub("AB", "i"), "))"], "2"), "]"], "2 Var(f)"),
        ],
    ],
}


def field(paragraph, instruction):
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = instruction
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in [begin, code, end]:
        run = OxmlElement("w:r")
        run.append(element)
        paragraph._p.append(run)


def inline(paragraph, text):
    pattern = r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))"
    for piece in re.split(pattern, text):
        if piece.startswith("**"):
            paragraph.add_run(piece[2:-2]).bold = True
        elif piece.startswith("`"):
            run = paragraph.add_run(piece[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(10)
        elif piece.startswith("[") and "](" in piece:
            label, target = piece[1:].split("](", 1)
            target = target[:-1]
            if target.startswith("http"):
                relation = paragraph.part.relate_to(
                    target,
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                    is_external=True,
                )
                link = OxmlElement("w:hyperlink")
                link.set(qn("r:id"), relation)
                run = OxmlElement("w:r")
                props = OxmlElement("w:rPr")
                color = OxmlElement("w:color")
                color.set(qn("w:val"), "17517A")
                props.append(color)
                run.append(props)
                word = OxmlElement("w:t")
                word.text = label
                run.append(word)
                link.append(run)
                paragraph._p.append(link)
            else:
                paragraph.add_run(f"{label} ({target})")
        else:
            paragraph.add_run(piece)


def table(doc, rows, widths=None):
    widths = widths or ([2.1, 4.4] if len(rows[0]) == 2 else [6.5 / len(rows[0])] * len(rows[0]))
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.autofit = False
    for column, width in zip(t.columns, widths):
        column.width = Inches(width)
    borders = OxmlElement("w:tblBorders")
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        edge = OxmlElement(f"w:{side}")
        for key, val in [("val", "single"), ("sz", "4"), ("color", "D9D9D9")]:
            edge.set(qn(f"w:{key}"), val)
        borders.append(edge)
    t._tbl.tblPr.append(borders)
    for index, values in enumerate(rows):
        row = t.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        if index == 0:
            row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for column, (cell, value, width) in enumerate(zip(row.cells, values, widths)):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side, val in [("top", "75"), ("bottom", "75"), ("left", "105"), ("right", "105")]:
                element = OxmlElement(f"w:{side}")
                element.set(qn("w:w"), val)
                element.set(qn("w:type"), "dxa")
                margins.append(element)
            props.append(margins)
            shade = OxmlElement("w:shd")
            shade.set(
                qn("w:fill"), "36454F" if index == 0 else ("F1F3F4" if index % 2 == 0 else "FFFFFF")
            )
            props.append(shade)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            if len(values) >= 4 and column:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            inline(p, value)
            for run in p.runs:
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255) if index == 0 else BLACK
                run.bold = index == 0
    spacer = doc.add_paragraph()
    spacer.paragraph_format.line_spacing = Pt(5)
    spacer.paragraph_format.space_after = Pt(6)


def special(doc, text):
    if text.startswith("{{EQ:"):
        for tokens in EQUATIONS[text[5:-2]]:
            add_equation(doc, tokens)
    elif text == "{{SOURCE}}":
        source = hashlib.sha256()
        package = ROOT / "src/bikeenergylab"
        for path in sorted(package.rglob("*.py")):
            source.update(path.relative_to(package).as_posix().encode())
            source.update(path.read_bytes())
        identity = source.hexdigest()
        doc.add_paragraph(f"Identidad SHA256 de las fuentes de la versión {VERSION}")
        p = doc.add_paragraph(identity)
        p.paragraph_format.space_after = Pt(10)
        p.runs[0].font.name = "Consolas"
        p.runs[0].font.size = Pt(9.5)
    elif text == "{{TABLE:ID}}":
        path = ROOT / "docs/validation_data/predictive_aggregate.csv"
        rows = [["Modelo", "MAE Wh", "CRPS Wh", "Cobertura 95%", "Brier"]]
        with path.open(encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row["scenario"] == "ID":
                    rows.append(
                        [
                            row["model"],
                            f"{float(row['mae_wh_mean']):.3f}",
                            f"{float(row['crps_wh_mean']):.3f}",
                            f"{100 * float(row['empirical_coverage95_mean']):.2f}%",
                            f"{float(row['energy_budget_brier_mean']):.4f}",
                        ]
                    )
        table(doc, rows, [1.0, 1.2, 1.2, 1.6, 1.5])
    elif text == "{{TABLE:DRIFT}}":
        path = ROOT / "docs/validation_data/prequential_metrics.csv"
        rows = [["Estrategia", "Modelo", "MAE Wh", "RMSE Wh"]]
        with path.open(encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                rows.append(
                    [
                        "Adaptativa" if row["strategy"] == "adaptive" else "Congelada",
                        row["model"],
                        f"{float(row['mae']):.3f}",
                        f"{float(row['rmse']):.3f}",
                    ]
                )
        table(doc, rows, [2.0, 1.2, 1.65, 1.65])
    else:
        raise ValueError(text)


def markdown(doc, content, user_manual=False):
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.startswith("# "):
            continue
        if line.startswith("{{"):
            special(doc, line)
        elif line.startswith("##"):
            level = len(line) - len(line.lstrip("#")) - 1
            heading = re.sub(r"[^\w\s]", " ", line.lstrip("# "), flags=re.UNICODE)
            doc.add_heading(re.sub(r"\s+", " ", heading).strip(), min(level, 3))
        elif line.startswith("```"):
            while i < len(lines) and not lines[i].startswith("```"):
                p = doc.add_paragraph(lines[i], "Code")
                p.paragraph_format.keep_with_next = i + 1 < len(lines) and not lines[
                    i + 1
                ].startswith("```")
                i += 1
            i += 1
        elif line.startswith("|"):
            rows = [[x.strip() for x in line.strip("|").split("|")]]
            while i < len(lines) and lines[i].strip().startswith("|"):
                values = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", value) for value in values):
                    rows.append(values)
                i += 1
            table(doc, rows)
        else:
            parts = [line]
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#|\||```|\{\{|\d+\. |[-*] )", lines[i].strip())
            ):
                parts.append(lines[i].strip())
                i += 1
            text = " ".join(parts)
            match = re.match(r"\d+\. \*\*(.+?):\*\* (.*)", text)
            if user_manual and match:
                heading = match[1].replace("38%", "38 por ciento")
                doc.add_heading(heading, 2)
                text = match[2]
                openings = {
                    "ejecutar ": "Abra el programa con ",
                    "masas, ": "Configure masas, ",
                    "masa y potencia ": "Defina masa y potencia ",
                    "eficiencia constante/mapa y límites.": "Configure eficiencia constante o un mapa y sus límites.",
                    "Wh nominales, ": "Indique Wh nominales, ",
                    "crear un perfil ": "Cree un perfil ",
                    "configurar timestep y auxiliares; pulsar Simular.": "Configure el paso de tiempo y los auxiliares; pulse Simular.",
                    "cargar CSV ": "Cargue CSV ",
                    "entrenar CGPRA ": "Entrene CGPRA ",
                    "editar las distribuciones en YAML y Aplicar YAML.": "Edite las distribuciones en YAML y pulse Aplicar YAML.",
                    "configurar initial_soc": "Configure initial_soc",
                    "temperatura, viento ": "Configure temperatura, viento ",
                    "ejecutar benchmark ": "Ejecute benchmark ",
                    "escoger carpeta ": "Escoja una carpeta ",
                }
                for original, revised in sorted(
                    openings.items(), key=lambda item: len(item[0]), reverse=True
                ):
                    if text.startswith(original):
                        text = revised + text[len(original) :]
                        break
                text = text.replace("Usar constante,", "Use un valor constante,")
                text = text.replace(
                    "Use un valor constante, perfil en CSV o modo dependiente",
                    "Use un valor constante, un perfil en CSV o el modo dependiente",
                )
                text = text.replace("reemplazarlos por mediciones", "reemplácelos por mediciones")
                text = text.replace("o importar CSV/GPX", "o importe CSV/GPX")
                text = text.replace("Pulsar **Visualizar ruta**", "Pulse **Visualizar ruta**")
                text = text.replace(
                    "Configure temperatura, viento (negativo frontal), presión/densidad.",
                    "Configure temperatura, viento (negativo frontal) y presión o densidad.",
                )
                text = text.replace(
                    "Configure initial_soc=0.38, importar ruta",
                    "Configure initial_soc=0.38, importe una ruta",
                )
                text = text.replace("y seleccionar sensibilidad", "y seleccione sensibilidad")
                text = text.replace("no comparar MAE", "no compare MAE")
                text = text.replace(
                    "El cálculo corre en background.", "El cálculo se realiza en segundo plano."
                )
                text = text.replace(
                    "Revisar energía, SOC, distancia y `feasible`.",
                    "Revise energía, SOC, distancia, `completed_route` y `feasible`.",
                )
                text = text.replace("Inspeccionar reporte", "Inspeccione el reporte")
                text = text.replace("Leer resultados positivos", "Lea los resultados positivos")
            p = doc.add_paragraph()
            inline(p, text)


def new_document(title, short, introduction):
    doc = Document()
    for border in list(doc.styles.element.xpath(".//w:pBdr")):
        border.getparent().remove(border)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Inches(0.8), Inches(0.8)
    sec.left_margin, sec.right_margin = Inches(1), Inches(1)
    sec.header_distance, sec.footer_distance = Inches(0.35), Inches(0.35)
    for name in ["Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3", "Caption"]:
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = BLACK
        style.font.underline = False
    normal = doc.styles["Normal"]
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(7 if short == "Manual de usuario" else 4)
    normal.paragraph_format.line_spacing = 1.12
    normal.paragraph_format.widow_control = True
    for level, size in [(1, 16), (2, 13), (3, 11.5)]:
        style = doc.styles[f"Heading {level}"]
        style.font.size = Pt(size)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(13)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True
    code = doc.styles.add_style("Code", 1)
    code.font.name, code.font.size, code.font.color.rgb = "Consolas", Pt(9.5), BLACK
    code.paragraph_format.space_after = Pt(1)
    code.paragraph_format.line_spacing = 1.05
    for name in ["TOC 1", "TOC 2", "TOC 3"]:
        if name not in doc.styles:
            doc.styles.add_style(name, 1)
        doc.styles[name].font.name = "Arial"
        doc.styles[name].font.size = Pt(10)
        doc.styles[name].font.color.rgb = BLACK
        doc.styles[name].paragraph_format.space_after = Pt(2)
        doc.styles[name].paragraph_format.line_spacing = 1.0
    language = OxmlElement("w:lang")
    language.set(qn("w:val"), "es-CO")
    normal.element.get_or_add_rPr().append(language)
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)
    header = sec.header.paragraphs[0]
    header.text = f"BikeEnergyLab     {short}"
    header.runs[0].font.name, header.runs[0].font.size = "Arial", Pt(9)
    header.runs[0].font.color.rgb = BLACK
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run(f"Versión {VERSION}     Página ")
    field(footer, " PAGE ")
    footer.add_run(" de ")
    field(footer, " NUMPAGES ")
    for run in footer.runs:
        run.font.name, run.font.size, run.font.color.rgb = "Arial", Pt(9), BLACK
    doc.styles["Title"].font.size = Pt(24)
    doc.styles["Title"].paragraph_format.space_after = Pt(12)
    doc.add_paragraph(title, "Title")
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    doc.add_paragraph(
        f"Versión {VERSION}   •   {RELEASE_DATE.day} de {months[RELEASE_DATE.month - 1]} de {RELEASE_DATE.year}"
    )
    doc.add_paragraph(
        "Francisco Javier Burgos Flórez\nJuan Guillermo Popayán Hernández\nfjburgosf@gmail.com"
    )
    doc.add_paragraph(introduction)
    doc.add_paragraph(
        "Los datos de práctica y los experimentos de esta entrega son sintéticos. La verificación de software no establece precisión con bicicletas reales."
    )
    contents = doc.add_paragraph("Contenido")
    contents.runs[0].bold = True
    contents.runs[0].font.size = Pt(14)
    field(doc.add_paragraph(), ' TOC \\o "1-1" \\h \\z \\u ')
    doc.add_page_break()
    doc.core_properties.title = title
    doc.core_properties.author = "Francisco Javier Burgos Flórez; Juan Guillermo Popayán Hernández"
    doc.core_properties.language = "es-CO"
    doc.core_properties.subject = f"Documentación de BikeEnergyLab {VERSION}"
    return doc


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    specifications = [
        (
            f"Manual_de_usuario_BikeEnergyLab_{VERSION}.docx",
            "Manual de usuario de BikeEnergyLab",
            "Manual de usuario",
            "Este manual guía al usuario desde abrir el programa y practicar con ejemplos hasta configurar su bicicleta, simular, interpretar resultados, calibrar y exportar. El menú Ejemplos y el tutorial integrado permiten comenzar sin preparar archivos de datos.",
            ROOT / "docs/user_manual.md",
            True,
        ),
        (
            f"Manual_tecnico_BikeEnergyLab_{VERSION}.docx",
            "Manual técnico de BikeEnergyLab",
            "Manual técnico",
            "Este manual describe la arquitectura, las clases públicas, la configuración, los algoritmos y la reproducción de BikeEnergyLab. Está dirigido a desarrolladores e investigadores que necesitan utilizar la API, revisar decisiones de implementación y repetir las verificaciones de la distribución.",
            ROOT / "docs/docx_sources/manual_tecnico_es.md",
            False,
        ),
        (
            f"Metodologia_cientifica_BikeEnergyLab_{VERSION}.docx",
            "Metodología científica de BikeEnergyLab",
            "Metodología científica",
            "Este documento formula el modelo físico y el método híbrido, explica calibración e incertidumbre y presenta los resultados sintéticos conservados. Las ecuaciones son objetos editables de Word. Los hallazgos incluyen fallos OOD y comparaciones desfavorables, porque la evidencia disponible no demuestra superioridad universal de CGPRA.",
            ROOT / "docs/docx_sources/metodologia_es.md",
            False,
        ),
    ]
    for filename, title, short, intro, source, user in specifications:
        doc = new_document(title, short, intro)
        if user:
            doc.add_heading("Abrir la distribución portátil", 1)
            doc.add_paragraph(
                "Extraiga toda la carpeta BikeEnergyLab del ZIP y abra BikeEnergyLab.exe. Conserve _internal junto al ejecutable. Esta distribución Windows x64 incluye las dependencias y funciona sin instalar Python ni conectarse a Internet. Si usa la API o CLI Python, instale Python 3.11 o superior y las dependencias indicadas en README.md."
            )
        markdown(doc, source.read_text(encoding="utf-8"), user_manual=user)
        doc.add_heading("Autoría y condiciones de uso", 1)
        doc.add_paragraph(
            "Autores: Francisco Javier Burgos Flórez y Juan Guillermo Popayán Hernández. Contacto: fjburgosf@gmail.com. Conserve CITATION.cff para citar el software. Los derechos y condiciones de uso son los indicados en LICENSE; no se presume una licencia abierta."
        )
        path = OUT / filename
        doc.save(path)
        print(path)


if __name__ == "__main__":
    main()

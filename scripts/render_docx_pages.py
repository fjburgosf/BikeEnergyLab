"""Use the packaged render_docx.py rasterizer with native Word PDFs on Windows.

LibreOffice is absent on this host. render_docx_word.ps1 first updates and exports
only task-owned DOCX files with a hidden Word instance; other documents are untouched.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
skill_root = Path.home() / ".codex/plugins/cache/openai-primary-runtime/documents"
renderers = sorted(
    skill_root.glob("*/skills/documents/render_docx.py"),
    key=lambda p: tuple(int(part) for part in p.parents[2].name.split(".")),
)
if not renderers:
    raise FileNotFoundError("Install the documents skill before rendering")
SKILL = renderers[-1].parent
spec = importlib.util.spec_from_file_location("packaged_render_docx", SKILL / "render_docx.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def native_pdf(doc_path, user_profile, convert_tmp_dir, stem, verbose=False):
    pdf = ROOT / "build/docx-qa" / f"{stem}.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"Export a native Word PDF first: {pdf}")
    return str(pdf), "Rendered with native Microsoft Word; LibreOffice unavailable on host"


renderer.convert_to_pdf = native_pdf
for path in sorted((ROOT / "docs/docx").glob("*.docx")):
    if path.name.startswith("~$"):
        continue
    sys.argv = [
        "render_docx.py",
        str(path),
        "--output_dir",
        str(ROOT / "build/docx-qa" / path.stem),
        "--dpi",
        "150",
        "--emit_pdf",
    ]
    renderer.main()

"""Use the packaged render_docx.py rasterizer with native Word PDFs on Windows.

LibreOffice is absent on this host. render_docx_word.ps1 first updates and exports
only task-owned DOCX files with a hidden Word instance; other documents are untouched.
"""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
renderer_setting = os.environ.get("BIKEENERGYLAB_DOCX_RENDERER")
if not renderer_setting:
    raise RuntimeError("Set BIKEENERGYLAB_DOCX_RENDERER to an installed render_docx.py")
renderer_path = Path(renderer_setting).expanduser().resolve()
if not renderer_path.is_file():
    raise FileNotFoundError(renderer_path)
spec = importlib.util.spec_from_file_location("external_render_docx", renderer_path)
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

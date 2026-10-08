"""Capture the application's own Tk test window for the illustrated manual.

Windows Graphics Capture is unavailable on the documentation host. PrintWindow
reads only this process's application window; it never captures the desktop or
other applications. This uses the same Application class as the released GUI.
"""

import argparse
import ctypes
import hashlib
import json
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
from unittest.mock import patch

from PIL import Image

from bikeenergylab import __version__
from bikeenergylab.gui.app import Application
from bikeenergylab.gui.onboarding import EXAMPLES, TUTORIAL
from bikeenergylab.io import json_safe

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/images/gui-1.0.0"


def capture(root, path):
    """Read pixels from this process's own window with checked GDI handles."""
    root.update_idletasks()
    root.update()
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetDC.argtypes = [wintypes.HWND]
    user.GetDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    hwnd = user.GetAncestor(root.winfo_id(), 2)
    rect = wintypes.RECT()
    assert user.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    assert width > 900 and height > 600
    header = (ctypes.c_int32 * 10)(40, width, -height, 0x200001, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.c_void_p()
    dc = user.GetDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateDIBSection(memory, header, 0, ctypes.byref(pixels), None, 0)
    previous = gdi.SelectObject(memory, bitmap)
    try:
        assert user.PrintWindow(hwnd, memory, 2), "PrintWindow failed"
        raw = ctypes.string_at(pixels, width * height * 4)
        image = Image.frombytes("RGB", (width, height), raw, "raw", "BGRX")
        assert len(image.getcolors(width * height) or []) > 30, "Empty window pixels"
        image.save(path)
    finally:
        gdi.SelectObject(memory, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd, dc)
    return width, height


def walk(parent):
    for child in parent.winfo_children():
        yield child
        yield from walk(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home-only", action="store_true")
    parser.add_argument("--panels-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = Application(root)
    errors, screenshots, results, buttons = [], [], {}, set()

    def wait():
        deadline = time.monotonic() + 300
        while app.job is not None:
            root.update()
            time.sleep(0.02)
            assert time.monotonic() < deadline, "Scientific job timeout"
        assert not errors, errors

    def shot(name):
        for _ in range(4):
            root.update()
            time.sleep(0.05)
        path = OUT / f"{name}.png"
        width, height = capture(root, path)
        for w in walk(root):
            if isinstance(w, (ttk.Button, tk.Button, ttk.Checkbutton, tk.Checkbutton)):
                text = str(w.cget("text"))
                if text:
                    buttons.add(text)
        screenshots.append(
            {
                "file": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "width": width,
                "height": height,
                "section": app.section,
                "loaded_example": app.loaded_example_key,
                "selected_result_tab": (
                    app.plot_frame.tab(app.plot_frame.select(), "text")
                    if app.section == "results" and app.plot_frame.select()
                    else None
                ),
            }
        )
        print("Captured:", name, flush=True)

    try:
        with patch.object(messagebox, "showerror", lambda *a, **kw: errors.append(a)):
            shot("01-inicio")
            if args.home_only:
                return
            for section in Application.sections:
                app.navigation.selection_set(section)
                app.show(section)
                shot("panel-" + section)
            if args.panels_only:
                path = OUT / "captures.json"
                report = json.loads(path.read_text(encoding="utf-8"))
                replacements = {s["file"]: s for s in screenshots}
                report["screenshots"] = [
                    replacements.get(s["file"], s) for s in report["screenshots"]
                ]
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
                return
            for index, example in enumerate(EXAMPLES, 1):
                app.load_example(example.key)
                app.run_simulation()
                wait()
                app.show("results")
                if example.key != "calibration":
                    app.plot_frame.select(app.details_frame)
                    if example.key == "hybrid":
                        location = app.result_text.search('"CGPRA"', "1.0")
                        if location:
                            app.result_text.see(location)
                    else:
                        app.result_text.see("1.0")
                shot(f"ejemplo-{index:02d}-{example.key}")
                results[example.key] = json_safe(app.last_result.summary)
            app.load_example("flat")
            app.start_tutorial()
            shot("tutorial-inicio")
            app.close_tutorial()
            app.run_simulation()
            wait()
            app.show("results")
            app.plot_frame.select(2)
            shot("resultado-plano")
    finally:
        app.close()
    source = hashlib.sha256()
    for path in sorted((ROOT / "src/bikeenergylab").rglob("*.py")):
        source.update(path.relative_to(ROOT / "src/bikeenergylab").as_posix().encode())
        source.update(path.read_bytes())
    gui = hashlib.sha256()
    for path in sorted((ROOT / "src/bikeenergylab/gui").rglob("*.py")):
        gui.update(path.relative_to(ROOT / "src/bikeenergylab/gui").as_posix().encode())
        gui.update(path.read_bytes())
    executable = ROOT / "dist/BikeEnergyLab/BikeEnergyLab.exe"
    executable_manifest = ROOT / "dist/BikeEnergyLab/_internal/bikeenergylab/source_manifest.json"
    distributed_source = (
        json.loads(executable_manifest.read_text(encoding="utf-8"))["source_sha256"]
        if executable_manifest.is_file()
        else None
    )
    report = {
        "version": __version__,
        "revision": "auditoria-2026-10-08",
        "source_sha256": source.hexdigest(),
        "gui_sha256": gui.hexdigest(),
        "executable_sha256": (
            hashlib.sha256(executable.read_bytes()).hexdigest() if executable.is_file() else None
        ),
        "executable_source_sha256": distributed_source,
        "source_matches_executable": distributed_source == source.hexdigest(),
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "PrintWindow of this process's own live Tk Application window",
        "screenshots": screenshots,
        "buttons": sorted(buttons),
        "example_results": results,
        "examples": [
            {
                "key": example.key,
                "title": example.text("es"),
                "description": example.text("es", description=True),
                "operation": example.operation,
            }
            for example in EXAMPLES
        ],
        "tutorial": [
            {
                "title": step.text("titles", "es"),
                "description": step.text("descriptions", "es"),
                "button": step.text("buttons", "es"),
                "action": step.action,
            }
            for step in TUTORIAL
        ],
        "errors": errors,
        "limits": "Documentation fixtures are synthetic; capture is source GUI, not native dialog certification",
    }
    (OUT / "captures.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    main()

"""Embed the same source identity in a frozen executable as source-mode runs."""

import hashlib
import json
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
package = root / "src" / "bikeenergylab"
digest = hashlib.sha256()
for source in sorted(package.rglob("*.py")):
    digest.update(source.relative_to(package).as_posix().encode())
    digest.update(source.read_bytes())
destination = root / "build" / "source_manifest.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(
    json.dumps({"source_sha256": digest.hexdigest()}, indent=2), encoding="utf-8"
)
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
numeric_version = tuple(int(part) for part in version.split(".")) + (0,)
if len(numeric_version) != 4:
    raise ValueError("Windows builds require a three-part numeric release version")
(root / "build/windows_version_info.txt").write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric_version!r}, prodvers={numeric_version!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'BikeEnergyLab'),
    StringStruct('FileVersion', {version!r}),
    StringStruct('InternalName', 'BikeEnergyLab'),
    StringStruct('OriginalFilename', 'BikeEnergyLab.exe'),
    StringStruct('ProductName', 'BikeEnergyLab'),
    StringStruct('ProductVersion', {version!r})
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""",
    encoding="utf-8",
)

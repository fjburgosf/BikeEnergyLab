"""Create a non-self-referential SHA256 inventory for distributed evidence."""

import hashlib
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from release_evidence import EVIDENCE_FILES

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/evidence-inventory-1.0.0.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    captures = json.loads((ROOT / "docs/images/gui-1.0.0/captures.json").read_text("utf-8"))
    assert captures["source_matches_executable"]
    files = {}
    for relative in EVIDENCE_FILES:
        if relative == OUTPUT.relative_to(ROOT).as_posix():
            continue
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        files[relative] = sha256(path)
    record = {
        "version": version,
        "revision": "auditoria-2026-10-08",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Original selected evidence and primary logs; full raw protocols remain in the development workspace",
        "source_sha256": captures["source_sha256"],
        "executable_sha256": captures["executable_sha256"],
        "files": files,
    }
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{len(files)} evidence files inventoried: {OUTPUT}")


if __name__ == "__main__":
    main()

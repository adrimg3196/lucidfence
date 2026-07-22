#!/usr/bin/env python3
"""Build the signed-by-hash local adapter marketplace index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ["applivery", "intune", "jamf", "chromeos", "windows_conformidad", "workspace_one"]


def build_index() -> dict:
    entries = []
    for name in ADAPTERS:
        path = ROOT / "core" / "adapters" / f"{name}.py"
        if not path.is_file():
            raise FileNotFoundError(path)
        entries.append({"name": name, "version": "1.0.0", "api": "MDMAdapter/v1",
                        "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "install": "bundled", "verified": True})
    return {"schema": "lucidfence-adapter-index/v1", "entries": entries}


def main() -> int:
    output = ROOT / "plugins" / "adapters" / "index.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_index(), indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

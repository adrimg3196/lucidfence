#!/usr/bin/env python3
"""Generate a deterministic CycloneDX 1.5 SBOM without third-party tooling."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REQ = re.compile(r"^([A-Za-z0-9_.-]+)==([^\\\s]+)")


def build_sbom(root: Path) -> dict:
    components = []
    for line in (root / "requirements.lock").read_text(encoding="utf-8").splitlines():
        match = REQ.match(line.strip())
        if match:
            name, version = match.groups()
            components.append({"type": "library", "name": name, "version": version,
                               "purl": f"pkg:pypi/{name.lower()}@{version}"})
    components.sort(key=lambda item: item["purl"])
    files = []
    for path in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part in {"build", "dist", "__pycache__"} for part in path.relative_to(root).parts):
            continue
        files.append({"path": str(path.relative_to(root)),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {"type": "application", "name": "lucidfence", "version": "1.3.1"}},
        "components": components,
        "properties": [{"name": "lucidfence:source-file-count", "value": str(len(files))},
                       {"name": "lucidfence:source-manifest-sha256",
                        "value": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", default="sbom.cdx.json")
    args = parser.parse_args()
    root = Path(args.root).resolve(); output = Path(args.out)
    if not output.is_absolute(): output = root / output
    output.write_text(json.dumps(build_sbom(root), indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

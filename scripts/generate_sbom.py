#!/usr/bin/env python3
"""Generate a deterministic CycloneDX 1.5 SBOM without third-party tooling."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:  # Python >= 3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for < 3.11
    tomllib = None

REQ = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)")


def read_project_version(root: Path) -> str:
    """Read the application version from pyproject.toml (single source of truth).

    Uses tomllib on Python >= 3.11; falls back to a regex on older
    interpreters. Never hardcodes a version.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        if tomllib is not None:
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            version = data.get("project", {}).get("version")
            if version:
                return version
        text = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.M)
        if m:
            return m.group(1)
    return "0.0.0"


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
    app_version = read_project_version(root)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {"type": "application", "name": "lucidfence",
                                   "version": app_version}},
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

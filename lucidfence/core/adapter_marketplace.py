"""Verification for the local adapter marketplace manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify_index(root: Path) -> dict:
    path = root / "plugins" / "adapters" / "index.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": type(exc).__name__, "entries": 0}
    if payload.get("schema") != "lucidfence-adapter-index/v1":
        return {"ok": False, "error": "schema", "entries": 0}
    checked = 0
    for entry in payload.get("entries", []):
        target = (root / str(entry.get("path", ""))).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return {"ok": False, "error": "path_escape", "entries": checked}
        if not target.is_file():
            return {"ok": False, "error": "missing", "entries": checked}
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            return {"ok": False, "error": "hash_mismatch", "entries": checked}
        checked += 1
    return {"ok": checked > 0, "entries": checked}

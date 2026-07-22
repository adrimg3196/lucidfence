"""Operational preflight for LucidFence installations."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def run_doctor(root: Path, data_root: Path, port: int = 8765) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, severity: str = "error"):
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "detail": detail})

    add("python", sys.version_info >= (3, 9), sys.version.split()[0])
    required = ["saas_server.py", "config.json", "static/dashboard.html", "roadmap.json"]
    missing = [name for name in required if not (root / name).is_file()]
    add("installation", not missing, "complete" if not missing else "missing: " + ", ".join(missing))
    try:
        json.loads((root / "config.json").read_text(encoding="utf-8"))
        add("config", True, "valid JSON")
    except Exception as exc:
        add("config", False, type(exc).__name__)
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix=".doctor-", dir=data_root)
        os.close(fd); Path(probe).unlink()
        add("data_directory", True, str(data_root))
    except OSError as exc:
        add("data_directory", False, f"{type(exc).__name__}: {exc.errno}")
    try:
        import roadmap_tooling
        errors = roadmap_tooling.validate_roadmap(roadmap_tooling.load_roadmap())
        add("roadmap", not errors, "valid" if not errors else "; ".join(errors[:3]))
    except Exception as exc:
        add("roadmap", False, type(exc).__name__)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/readyz", timeout=1.5) as response:
            payload = json.loads(response.read())
            add("runtime", response.status == 200 and payload.get("ready") is True, f"HTTP {response.status}")
    except (OSError, urllib.error.URLError):
        add("runtime", False, f"not listening on 127.0.0.1:{port}", "warning")
    errors = [item for item in checks if not item["ok"] and item["severity"] == "error"]
    return {"ok": not errors, "checks": checks, "errors": len(errors),
            "warnings": sum(1 for item in checks if not item["ok"] and item["severity"] == "warning")}

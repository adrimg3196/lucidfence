"""Tenant-local multi-UEM provider registry.

The provider *list* (names + non-secret config + secret) lives in each tenant's
isolated ``integration.json`` (chmod 0600). The secret is masked on read-back
(see ``mask_provider``) so GET endpoints never echo credentials.
"""
from __future__ import annotations

import json
from pathlib import Path


def list_providers(tdir: Path) -> list[dict]:
    """Return the provider list for a tenant (empty if none configured)."""
    runtime = _tenant_runtime(tdir)
    return [p for p in runtime.get("providers", []) if isinstance(p, dict)]


def save_providers(tdir: Path, providers: list[dict]) -> None:
    """Persist the provider list into the tenant's integration.json (0600)."""
    import json
    import os

    runtime = _tenant_runtime(tdir)
    runtime["providers"] = providers
    path = tdir / "integration.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def mask_provider(p: dict) -> dict:
    """Return a provider dict safe to send to the client (no secret)."""
    out = {k: v for k, v in p.items() if k != "secret"}
    out["configured"] = bool(p.get("secret") or p.get("endpoint") or p.get("api_key"))
    return out


def _tenant_runtime(tdir: Path) -> dict:
    try:
        data = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

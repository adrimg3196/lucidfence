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


# Minimal catalog of supported UEM connectors. Kept here (not in the adapters)
# because it is presentation metadata for the wizard, not engine contract.
PROVIDER_CATALOG: dict[str, dict] = {
    "applivery": {"label": "Applivery", "fields": ["api_key", "org_id"]},
    "intune": {"label": "Microsoft Intune", "fields": ["api_key", "org_id"]},
    "jamf": {"label": "Jamf", "fields": ["api_key", "org_id"]},
    "fleet": {"label": "FleetDM", "fields": ["api_key", "endpoint"]},
    "workspace_one": {"label": "Workspace ONE", "fields": ["api_key", "org_id"]},
    "chromeos": {"label": "ChromeOS", "fields": ["api_key", "org_id"]},
    "windows_conformidad": {"label": "Windows (conformidad)", "fields": ["api_key", "org_id"]},
    "simulation": {"label": "Simulación (demo)", "fields": []},
}


def catalog() -> list[dict]:
    """Return the list of UEM connectors an admin can connect."""
    return [
        {"name": name, "label": meta["label"], "fields": meta["fields"]}
        for name, meta in PROVIDER_CATALOG.items()
    ]

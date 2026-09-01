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


_SECRET_KEYS = ("secret", "api_key", "client_secret", "refresh_token", "password", "token")


def mask_provider(p: dict) -> dict:
    """Return a provider dict safe to send to the client (no secret)."""
    out = {k: v for k, v in p.items() if k not in _SECRET_KEYS}
    out["configured"] = bool(p.get("secret") or p.get("api_key")
                             or p.get("client_secret") or p.get("refresh_token")
                             or p.get("endpoint") or p.get("tenant_id"))
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
    "applivery": {"label": "Applivery", "fields": ["api_key", "org_id"],
     "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "intune": {"label": "Microsoft Intune", "fields": ["tenant_id", "client_id", "client_secret"],
     "declarative": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": True}},
    "jamf": {"label": "Jamf", "fields": ["client_id", "client_secret"],
     "declarative": {"supports_ddm": True, "supports_dsc": False, "supports_amapi_policy": False}},
    "fleet": {"label": "FleetDM", "fields": ["api_key", "endpoint"],
     "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "workspace_one": {"label": "Workspace ONE", "fields": ["api_key", "org_id"],
     "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": True}},
    "chromeos": {"label": "ChromeOS", "fields": ["client_id", "client_secret", "refresh_token"],
     "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "windows_conformidad": {"label": "Windows (conformidad)", "fields": ["api_key", "org_id"],
     "declarative": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": False}},
    "simulation": {"label": "Simulación (demo)", "fields": [],
     "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
}

PROVIDER_DECLARATIVE_CAPABILITIES: dict[str, dict] = {
    "jamf": {"supports_ddm": True, "supports_dsc": False, "supports_amapi_policy": False},
    "intune": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": True},
    "windows_conformidad": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": False},
    "fleet": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False},
    "applivery": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False},
    "workspace_one": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": True},
    "chromeos": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False},
    "simulation": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False},
}


def catalog() -> list[dict]:
    """Return the list of UEM connectors an admin can connect."""
    return [
        {"name": name, "label": meta["label"], "fields": meta["fields"]}
        for name, meta in PROVIDER_CATALOG.items()
    ]

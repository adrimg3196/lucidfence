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


# Toda clave que porte un secreto de conexión. `api_token` es la credencial de
# Fleet: sin ella aquí, un provider Fleet guardado echaba el token en el GET.
_SECRET_KEYS = ("secret", "api_key", "api_token", "client_secret",
                "refresh_token", "password", "token")


def mask_provider(p: dict) -> dict:
    """Return a provider dict safe to send to the client (no secret)."""
    out = {k: v for k, v in p.items() if k not in _SECRET_KEYS}
    out["configured"] = bool(p.get("secret") or p.get("api_key")
                             or p.get("api_token") or p.get("password")
                             or p.get("client_secret") or p.get("refresh_token")
                             or p.get("endpoint") or p.get("tenant_id"))
    return out


def _tenant_runtime(tdir: Path) -> dict:
    try:
        data = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# Catálogo de conectores UEM. Presentación para el wizard, derivada del
# contrato REAL de cada adapter: cada `key` es exactamente el kwarg que consume
# su constructor / build_*_from_config (lucidfence/core/adapters/<uem>.py).
# tests/test_provider_catalog.py verifica esa correspondencia contra
# inspect.signature — si un adapter cambia de credenciales, ese test cae.
#
# Shape de cada field:
#   key         -> nombre del kwarg del adapter (viaja tal cual en save/test)
#   label       -> etiqueta humana del input
#   type        -> "text" | "secret" | "url"  (secret => en _SECRET_KEYS)
#   placeholder -> ejemplo del formato esperado ("" si no aplica)
#   help        -> dónde encontrarlo en la consola real de ese UEM
#   optional    -> True si el adapter tiene default razonable sin él
PROVIDER_CATALOG: dict[str, dict] = {
    "applivery": {
        "label": "Applivery",
        "min_permission": "API key con permiso de solo lectura de dispositivos",
        "fields": [
            {"key": "api_key", "label": "API key", "type": "secret", "placeholder": "",
             "help": "Dashboard → Organization → API keys. La organización va implícita en la key."},
        ],
    },
    "intune": {
        "label": "Microsoft Intune",
        "min_permission": "App de Entra con permiso de aplicación DeviceManagementManagedDevices.Read.All",
        "fields": [
            {"key": "tenant_id", "label": "Tenant ID", "type": "text",
             "placeholder": "00000000-0000-0000-0000-000000000000",
             "help": "Entra ID (entra.microsoft.com) → Overview → Tenant ID"},
            {"key": "client_id", "label": "Client ID", "type": "text", "placeholder": "",
             "help": "Entra ID → App registrations → tu app → Application (client) ID"},
            {"key": "client_secret", "label": "Client secret", "type": "secret", "placeholder": "",
             "help": "Entra ID → App registrations → tu app → Certificates & secrets → New client secret (cópialo al crearlo: no vuelve a mostrarse)"},
        ],
    },
    "jamf": {
        "label": "Jamf Pro",
        "min_permission": "API role de solo lectura (Read Computers, Read Mobile Devices)",
        "fields": [
            {"key": "base_url", "label": "URL de tu Jamf", "type": "url",
             "placeholder": "https://tuorg.jamfcloud.com",
             "help": "La URL con la que entras a Jamf"},
            {"key": "client_id", "label": "Client ID", "type": "text", "placeholder": "",
             "help": "Settings → API roles and clients → New client"},
            {"key": "client_secret", "label": "Client secret", "type": "secret", "placeholder": "",
             "help": "Se muestra una sola vez al crear el client"},
        ],
    },
    "fleet": {
        "label": "FleetDM",
        "min_permission": "Usuario API con rol observer (solo lectura)",
        "fields": [
            {"key": "base_url", "label": "URL de tu Fleet", "type": "url",
             "placeholder": "https://fleet.tuorg.com",
             "help": "La URL donde sirves Fleet (la misma que usas en el navegador)"},
            {"key": "api_token", "label": "API token", "type": "secret", "placeholder": "",
             "help": "fleetctl user create --api-only --global-role observer · o en la UI: tu cuenta → Settings → API token"},
        ],
    },
    "workspace_one": {
        "label": "Workspace ONE UEM",
        "min_permission": "Cuenta de servicio de solo lectura + REST API key del tenant",
        "fields": [
            {"key": "base_url", "label": "URL del servidor API", "type": "url",
             "placeholder": "https://asXXXX.awmdm.com",
             "help": "La URL de tu consola Workspace ONE UEM (servidor REST API)"},
            {"key": "tenant_code", "label": "Tenant code (aw-tenant-code)", "type": "text",
             "placeholder": "",
             "help": "Groups & Settings → All Settings → System → Advanced → API → REST API (API key)"},
            {"key": "username", "label": "Usuario API", "type": "text", "placeholder": "",
             "help": "Accounts → Administrators: cuenta de servicio con rol de solo lectura"},
            {"key": "password", "label": "Contraseña", "type": "secret", "placeholder": "",
             "help": "La contraseña de esa cuenta de servicio (Basic auth de la REST API)"},
        ],
    },
    "chromeos": {
        "label": "ChromeOS",
        "min_permission": "OAuth con scope admin.directory.device.chromeos.readonly (Admin SDK)",
        "fields": [
            {"key": "client_id", "label": "OAuth client ID", "type": "text", "placeholder": "",
             "help": "console.cloud.google.com → APIs & Services → Credentials → OAuth client ID (con la Admin SDK API habilitada)"},
            {"key": "client_secret", "label": "OAuth client secret", "type": "secret", "placeholder": "",
             "help": "El secret del mismo OAuth client en console.cloud.google.com"},
            {"key": "refresh_token", "label": "Refresh token", "type": "secret", "placeholder": "",
             "help": "Del flujo de consentimiento de ese OAuth client con scope admin.directory.device.chromeos.readonly"},
            {"key": "customer_id", "label": "Customer ID", "type": "text", "placeholder": "my_customer",
             "optional": True,
             "help": "Google Admin → Cuenta → Configuración de la cuenta → ID de cliente. Vacío = my_customer (tu propio dominio)"},
        ],
    },
    "windows_conformidad": {
        "label": "Windows (conformidad)",
        "min_permission": "App de Entra con permiso de aplicación DeviceManagementManagedDevices.Read.All",
        "fields": [
            {"key": "tenant_id", "label": "Tenant ID", "type": "text",
             "placeholder": "00000000-0000-0000-0000-000000000000",
             "help": "Entra ID (entra.microsoft.com) → Overview → Tenant ID"},
            {"key": "client_id", "label": "Client ID", "type": "text", "placeholder": "",
             "help": "Entra ID → App registrations → tu app → Application (client) ID"},
            {"key": "client_secret", "label": "Client secret", "type": "secret", "placeholder": "",
             "help": "Entra ID → App registrations → tu app → Certificates & secrets → New client secret (cópialo al crearlo: no vuelve a mostrarse)"},
        ],
    },
    "simulation": {
        "label": "Simulación (demo)",
        "min_permission": "Sin credenciales · flota de ejemplo local",
        "fields": [],
    },
}


def catalog() -> list[dict]:
    """Return the list of UEM connectors an admin can connect.

    Each entry: {name, label, min_permission, fields, field_keys}. `fields` is
    the rich per-UEM schema (see PROVIDER_CATALOG); `field_keys` is the flat
    list of key names for consumers that only need the wire keys.
    """
    return [
        {
            "name": name,
            "label": meta["label"],
            "min_permission": meta.get("min_permission", ""),
            "fields": meta["fields"],
            "field_keys": [f["key"] for f in meta["fields"]],
        }
        for name, meta in PROVIDER_CATALOG.items()
    ]

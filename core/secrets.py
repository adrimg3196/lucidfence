#!/usr/bin/env python3
"""Local, safe Applivery credential storage for the LucidFence product.

Design goals (security first, 100% local):
- Credentials live in a `.env` file NEXT TO config.json (project root), never in
  `data/` (which may be synced/backed up) and never in logs or API responses.
- The file is created with mode 0600 (owner read/write only).
- GET endpoints only ever return a *status boolean* (configured or not) and the
  chosen mode — never the key itself.
- Saving validates the key shape loosely (non-empty, looks like a token) but does
  NOT phone home or validate against the Applivery API.
"""
from __future__ import annotations

import json
import os
import ssl
import stat
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENV_KEY = "APPLIVERY_API_KEY"
ORG_KEY = "APPLIVERY_ORG_ID"

# Tokens we never accept (obviously placeholder values).
_REJECT = {"", "YOUR_API_KEY", "CHANGE_ME", "TODO", "test", "xxxx"}


def env_path(root: Path) -> Path:
    return Path(root) / ".env"


def _secure_write(path: Path, text: str) -> None:
    # Write to a temp file then atomically replace, then tighten perms.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    # Belt-and-suspenders: ensure 0600 on the final file too.
    os.chmod(path, 0o600)


def save_credentials(root: Path, api_key: Optional[str], org_id: Optional[str]) -> dict:
    """Persist credentials to .env (0600). Returns a status dict (no secrets)."""
    path = env_path(root)
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            existing[k.strip()] = v.strip().strip('"').strip("'")

    if api_key is not None:
        ak = api_key.strip()
        if ak.lower() in _REJECT or len(ak) < 8:
            return {"ok": False, "error": "api_key rechazado: parece un placeholder o es demasiado corto."}
        existing[ENV_KEY] = ak
    if org_id is not None:
        oi = org_id.strip()
        if oi:
            existing[ORG_KEY] = oi

    lines = [f"{k}={v}" for k, v in existing.items() if v]
    _secure_write(path, "\n".join(lines) + "\n")
    # Make the key available to the running process immediately.
    if ENV_KEY in existing:
        os.environ[ENV_KEY] = existing[ENV_KEY]
    if ORG_KEY in existing:
        os.environ[ORG_KEY] = existing[ORG_KEY]
    return {"ok": True, "configured": bool(existing.get(ENV_KEY)), "path": str(path)}


def status(root: Path) -> dict:
    """Return only non-secret status: is a key configured, current mode hint."""
    path = env_path(root)
    has_key = False
    org = ""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == ENV_KEY and v and v.lower() not in _REJECT:
                has_key = True
            elif k == ORG_KEY:
                org = v
    return {"configured": has_key, "org_id_set": bool(org), "file": str(path)}


def read_key(root: Path) -> str:
    """Internal use only (e.g. live token test). NEVER expose the return value via API."""
    path = env_path(root)
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == ENV_KEY:
            v = v.strip().strip('"').strip("'")
            if v and v.lower() not in _REJECT:
                return v
    return ""


def read_org_id(root: Path) -> str:
    """Read the tenant's Applivery workspace ID without exposing its token."""
    path = env_path(root)
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == ORG_KEY:
            return value.strip().strip('"').strip("'")
    return ""


def mask_key(root: Path) -> str:
    """Return a masked preview like 'ab12••••••••••w9z3' or '' if none."""
    path = env_path(root)
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == ENV_KEY:
            v = v.strip().strip('"').strip("'")
            if len(v) <= 4:
                return "••••"
            return v[:4] + "•" * max(0, len(v) - 8) + v[-4:]
    return ""


def test_applivery_token(api_key: str) -> dict:
    """Validate a token against the real Applivery API (read-only GET /v1).

    Semantics are intentionally honest because /v1 may be an ambiguous probe:
    - 2xx  -> token confirmed valid.
    - 3xx  -> server reachable; token not confirmed.
    - 401/403 -> token rejected; connectivity OK.
    - 404  -> root probe unavailable/ambiguous; not a network failure.
    - other <500 -> server responded; inconclusive.
    - >=500, timeout, connection errors -> service/network failure.
    The token is never returned or logged.
    """
    def classify(code: int) -> dict:
        if 200 <= code < 300:
            return {"ok": True, "valid": True, "http_status": code, "category": "valid",
                    "message": "Token válido: la API de Applivery respondió correctamente."}
        if 300 <= code < 400:
            return {"ok": True, "valid": None, "http_status": code, "category": "redirect",
                    "message": f"La API respondió HTTP {code}. Hay conectividad, pero el token no queda confirmado."}
        if code in (401, 403):
            return {"ok": True, "valid": False, "http_status": code, "category": "unauthorized",
                    "message": f"Token rechazado (HTTP {code}). Verifica que sea correcto y no haya expirado."}
        if code == 404:
            return {"ok": True, "valid": None, "http_status": code, "category": "ambiguous_probe",
                    "message": "La API respondió 404 en /v1. Hay respuesta del servidor, pero el probe raíz no confirma el token."}
        if 400 <= code < 500:
            return {"ok": True, "valid": None, "http_status": code, "category": "client_status_inconclusive",
                    "message": f"La API respondió HTTP {code}. Conectividad OK; validación no concluyente."}
        return {"ok": False, "valid": None, "http_status": code, "category": "service_error",
                "message": f"La API respondió HTTP {code}. Posible fallo temporal del servicio."}

    url = "https://api.applivery.io/v1"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    try:
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=8, context=ctx) as resp:
            return classify(int(resp.getcode()))
    except HTTPError as e:
        return classify(int(getattr(e, "code", 0) or 0))
    except (URLError, TimeoutError, ConnectionError) as e:
        return {"ok": False, "valid": None, "http_status": 0, "category": "connection_failed",
                "message": "No se pudo conectar con la API de Applivery (red, DNS o timeout)."}
    except Exception as e:  # noqa: BLE001 - report class only, never secret
        return {"ok": False, "valid": None, "http_status": 0, "category": "validation_error",
                "message": f"Error de validación: {type(e).__name__}."}


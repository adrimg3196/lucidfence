"""VMware Workspace ONE UEM adapter (mock-ready and live-capable).

Live mode uses the documented UEM REST surface with tenant-code + Basic auth.
The adapter never contacts the vendor in its constructor and never raises from
``execute``.  Without credentials it stays in deterministic mock mode.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Any
from urllib.parse import quote

import requests

from core.adapters.base import MDMAdapter


COMMANDS = {
    "lock": "DeviceLock",
    "wipe": "EnterpriseWipe",
    "clear_passcode": "ClearPasscode",
    "reboot": "DeviceReboot",
    "locate": "RequestDeviceLocation",
    "message": "SendMessage",
}


class WorkspaceONEAdapter(MDMAdapter):
    name = "workspace_one"

    def __init__(self, org_id: str = "", endpoint_template: str = "", webhook_url: str = "",
                 api_key: str = "", live: bool = False, base_url: str = "", tenant_code: str = "",
                 username: str = "", password: str = "", timeout: int = 30):
        self.org_id = org_id
        self.base_url = (base_url or endpoint_template or os.environ.get("WORKSPACE_ONE_BASE_URL", "")).rstrip("/")
        self.tenant_code = tenant_code or os.environ.get("WORKSPACE_ONE_TENANT_CODE", "")
        self.username = username or os.environ.get("WORKSPACE_ONE_USERNAME", "")
        self.password = password or api_key or os.environ.get("WORKSPACE_ONE_PASSWORD", "")
        self.live = bool(live)
        self.timeout = timeout

    def _headers(self) -> dict:
        basic = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {basic}", "aw-tenant-code": self.tenant_code,
                "Accept": "application/json", "Content-Type": "application/json"}

    @staticmethod
    def _device_id(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        try:
            if not self.live:
                return self._mock(device, action, params, dry_run)
            if not (self.base_url and self.tenant_code and self.username and self.password):
                return self._error(device, action, "auth_error", "Workspace ONE live credentials are incomplete")
            if action == "list":
                return self._list_live(dry_run)
            device_id = self._device_id(device)
            if not device_id:
                return self._error(device, action, "missing_device_id", "device_id is required")
            if action == "sync_geofences":
                return self._sync_geofences(device_id, params, dry_run)
            command = COMMANDS.get(action)
            if not command:
                return self._error(device, action, "unsupported_action", f"unsupported action: {action}")
            url = f"{self.base_url}/API/mdm/devices/{quote(device_id, safe='')}/commands"
            payload = {"Command": command}
            if action == "message":
                payload["Message"] = str(params.get("text") or "")[:1000]
            if dry_run:
                return self._ok(device_id, action, "dry_run", would_send={"method": "POST", "url": url, "json": payload})
            response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            return self._response(device, action, response)
        except requests.RequestException as exc:
            return self._error(device, action, "transport_error", repr(exc))
        except Exception as exc:  # contract: never raise
            return self._error(device, action, "unknown_error", repr(exc))

    def _list_live(self, dry_run: bool) -> dict:
        url = f"{self.base_url}/API/mdm/devices/search"
        if dry_run:
            return {"adapter": self.name, "ok": True, "action": "list", "mode": "dry_run",
                    "would_send": {"method": "GET", "url": url}}
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if response.status_code >= 400:
            return self._http_error({}, "list", response)
        payload = response.json()
        source = payload.get("Devices") or payload.get("devices") or []
        devices = [{"device_id": str(row.get("Id") or row.get("id") or ""),
                    "name": row.get("DeviceFriendlyName") or row.get("name"),
                    "platform": str(row.get("Platform") or row.get("platform") or "").lower(),
                    "compliant": row.get("ComplianceStatus") in (True, "Compliant", "compliant")}
                   for row in source if isinstance(row, dict)]
        return {"adapter": self.name, "ok": True, "action": "list", "mode": "live",
                "count": len(devices), "devices": devices}

    def _sync_geofences(self, device_id: str, params: dict, dry_run: bool) -> dict:
        fences = params.get("fences") or []
        if not isinstance(fences, list):
            return self._error({"device_id": device_id}, "sync_geofences", "invalid_payload", "fences must be a list")
        # Workspace ONE assignment/profile APIs vary by tenant version.  Export a
        # normalized, auditable payload and only send when an explicit endpoint is configured.
        endpoint = str(params.get("endpoint") or "").strip()
        if not endpoint:
            return {"adapter": self.name, "ok": True, "action": "sync_geofences", "mode": "export",
                    "device_id": device_id, "fences": fences, "count": len(fences),
                    "note": "Normalized profile ready; configure a tenant profile endpoint for live push."}
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        payload = {"device_id": device_id, "geofences": fences}
        if dry_run:
            return self._ok(device_id, "sync_geofences", "dry_run", would_send={"method": "POST", "url": url, "json": payload})
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        return self._response({"device_id": device_id}, "sync_geofences", response)

    def _response(self, device: Any, action: str, response) -> dict:
        if response.status_code >= 400:
            return self._http_error(device, action, response)
        return self._ok(self._device_id(device), action, "live", http_status=response.status_code)

    def _http_error(self, device: Any, action: str, response) -> dict:
        kind = "auth_error" if response.status_code in (401, 403) else "rate_limited" if response.status_code == 429 else "device_not_found" if response.status_code == 404 else "vendor_rejected"
        return self._error(device, action, kind, f"Workspace ONE HTTP {response.status_code}: {response.text[:200]}")

    def _mock(self, device: Any, action: str, params: dict, dry_run: bool) -> dict:
        device_id = self._device_id(device)
        if action not in set(COMMANDS) | {"list", "sync_geofences"}:
            return self._error(device, action, "unsupported_action", f"unsupported action: {action}")
        command_id = hashlib.sha256(f"{device_id}:{action}".encode()).hexdigest()[:12]
        if action == "list":
            return {"adapter": self.name, "ok": True, "mock": True, "action": "list", "devices": [], "count": 0}
        return {"adapter": self.name, "ok": True, "mock": True, "dry_run": dry_run,
                "device_id": device_id, "action": action, "command_id": f"ws1-{command_id}", "params": params}

    def _ok(self, device_id: str, action: str, mode: str, **extra) -> dict:
        return {"adapter": self.name, "ok": True, "device_id": device_id, "action": action, "mode": mode, **extra}

    def _error(self, device: Any, action: str, kind: str, message: str) -> dict:
        return {"adapter": self.name, "ok": False, "device_id": self._device_id(device),
                "action": action, "error_type": kind, "error": message}


def build_workspace_one_adapter_from_config(cfg: dict) -> WorkspaceONEAdapter:
    section = (cfg.get("mdm") or {}).get("workspace_one") or {}
    return WorkspaceONEAdapter(live=section.get("live", False), base_url=section.get("base_url", ""),
                               tenant_code=section.get("tenant_code", ""), username=section.get("username", ""),
                               password=section.get("password", ""))

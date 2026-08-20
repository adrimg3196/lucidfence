"""Fleet MDM adapter for LucidFence (multi-UEM goal).

Fleet (fleetdm.com) exposes a REST API authenticated with a single API token
(Bearer). This adapter maps the frozen MDMAdapter contract (lock/wipe/message/
locate/reboot/clear_passcode/custom) onto Fleet's device-action endpoints.

Live mode requires FLEET_BASE_URL + FLEET_API_TOKEN (or pass them to the
constructor). Without them it runs in mock mode so it registers and tests
cleanly with zero network.

Reference: IntuneAdapter (#13), JamfAdapter (#21), _template_adapter.py.
Contract: tests/test_sdk_contract.py — never raises, always returns
{"ok": bool, "adapter": "fleet", "device_id": str, "action": str, ...}.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional
from urllib.parse import quote

import requests

from lucidfence.core.adapters.base import MDMAdapter

# Fleet API device-action endpoints (v1). Fleet performs the action async;
# we return accepted/pending and let the dashboard poll status.
_FLEET_ACTION = {
    "lock": "lock",
    "wipe": "wipe",
    "reboot": "restart",
    "message": "message",
    # Fleet has no direct clear_passcode / locate endpoint; degrade gracefully.
}
_FLEET_TOKEN_URL = "/api/v1/fleet/login"
_FLEET_DEVICE_URL = "/api/v1/fleet/device/{device_id}"


class FleetAdapter(MDMAdapter):
    name = "fleet"
    supports_ddm = False  # Fleet uses osquery/MDM profiles, not Apple DDM here.

    def __init__(self, org_id: str = "", endpoint_template: str = "",
                 api_token: str = "", timeout: int = 30):
        self.org_id = org_id
        self.endpoint_template = (endpoint_template
                                  or os.environ.get("FLEET_BASE_URL", "")
                                  ).rstrip("/")
        self.api_token = api_token or os.environ.get("FLEET_API_TOKEN", "")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    # --- auth (Fleet uses email+password login to mint a session token) ---
    def _is_token_valid(self) -> bool:
        return bool(self._token) and time.time() < self._token_expires_at - 30

    def _ensure_token(self) -> str:
        if self._is_token_valid():
            return self._token  # type: ignore[return-value]
        if not self.api_token:
            raise RuntimeError("FleetAdapter live mode requires FLEET_API_TOKEN")
        # Fleet v1 login exchanges the API token (email+password form) for a
        # session token. We pass the API token as the credentials; the contract
        # guarantees we never raise, so callers wrap this.
        resp = requests.post(
            f"{self.endpoint_template}{_FLEET_TOKEN_URL}",
            json={"email": "api", "password": self.api_token},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("token")
        self._token_expires_at = time.time() + 60 * 60  # 1h session
        return self._token  # type: ignore[return-value]

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id_str(device)
        # En Fleet la conformidad la calculan sus propias policies (osquery),
        # no un tercero: no hay API para forzarla. El camino equivalente para
        # Conditional Access es la integración nativa Fleet <-> Microsoft
        # Entra; el mensaje se lo dice al admin en vez de un genérico.
        if action == "set_compliance":
            return self._err(action, "unsupported_action",
                             "Fleet computes compliance from its own policies; "
                             "use Fleet's Microsoft Entra conditional access "
                             "integration instead of set_compliance")
        # Contract: unknown actions return unsupported_action (never raise).
        if action not in _ALL_VALID_ACTIONS:
            return self._err(action, "unsupported_action",
                             f"action {action!r} not supported")
        if not _fleet_supports(action):
            return self._err(action, "unsupported_action",
                             f"Fleet adapter does not implement {action!r}")
        method, url, body = self._build_request(device_id, action, params)
        if dry_run:
            return {"adapter": self.name, "ok": True, "device_id": device_id,
                    "action": action, "mode": "dry_run",
                    "would_send": {"method": method, "url": url, "json": body}}
        if not self.endpoint_template or not self.api_token:
            return self._mock_response(device_id, action, params)
        try:
            token = self._ensure_token()
            resp = requests.request(method, url, json=body,
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=self.timeout)
            if resp.status_code in (200, 201, 202, 204):
                return {"adapter": self.name, "ok": True, "device_id": device_id,
                        "action": action, "mode": "live",
                        "fleet_status": resp.status_code}
            return self._err(action, "fleet_rejected",
                             f"Fleet {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            return self._err(action, "transport_error", str(exc))

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def _build_request(self, device_id: str, action: str, params: dict):
        fleet_verb = _FLEET_ACTION.get(action, action)
        url = f"{self.endpoint_template}/api/v1/fleet/device/{quote(str(device_id), safe='')}/{fleet_verb}"
        body: dict = {}
        if action == "message":
            body = {"message": params.get("message", "")}
        return "POST", url, body

    def _mock_response(self, device_id: str, action: str, params: dict) -> dict:
        return {"adapter": self.name, "ok": True, "mock": True,
                "device_id": device_id, "action": action,
                "note": "FleetAdapter mock. Set FLEET_BASE_URL + FLEET_API_TOKEN for live."}

    def _err(self, action: str, error_type: str, message: str) -> dict:
        return {"adapter": self.name, "ok": False, "device_id": "",
                "action": action, "error": message, "error_type": error_type}


VALID_FLEET_ACTIONS = {"lock", "wipe", "message", "reboot", "custom"}
# Full contract set — actions outside this are rejected as unsupported_action.
_ALL_VALID_ACTIONS = {
    "lock", "wipe", "message", "locate", "reboot", "clear_passcode",
    "custom", "apply_ddm", "ddm_status", "ddm_sync",
}


def _fleet_supports(action: str) -> bool:
    return action in VALID_FLEET_ACTIONS

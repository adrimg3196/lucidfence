"""SDK template for new community MDM adapters.

Drop-in starter for Workspace ONE, Fleet, SOTI, Mosyle, Kandji, etc.

Usage:
    cp core/adapters/_template_adapter.py core/adapters/<your_mdm>.py
    # Edit name, _build_request, the live-path branch in execute().
    # Register in core/adapters/__init__.py:
    #     ADAPTER_REGISTRY["<your_mdm>"] = <YourMdm>Adapter

Contract (frozen — see tests/test_sdk_contract.py):
  * name:    lowercase stable identifier
  * execute:  never raises; returns {"ok": bool, "adapter": str, "device_id": str, "action": str, ...}
  * dry_run: builds the request but does not send it
  * errors:  map to AuthError / TransportError → ok=False with "error_type"
"""

from __future__ import annotations

import os
from typing import Any, Optional

from core.adapters.base import MDMAdapter


_VALID_ACTIONS_FOR_TEMPLATE = {"lock", "wipe", "message", "locate", "reboot", "clear_passcode", "custom"}


class TemplateMdmAdapter(MDMAdapter):
    """Replace `name` and execute() with your MDM integration.

    Reference: IntuneAdapter (#13), JamfAdapter (#21).
    """

    name = "template_mdm"

    def __init__(self, org_id: str = "", endpoint_template: str = "",
                 timeout: int = 30, api_key: str = ""):
        self.org_id = org_id
        self.endpoint_template = endpoint_template
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("TEMPLATE_MDM_TOKEN", "")

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id_str(device)
        if action not in _VALID_ACTIONS_FOR_TEMPLATE:
            return self._err(action, "unsupported_action", f"action {action!r} not supported")
        method, url, body = self._build_request(device_id, action, params)
        if dry_run:
            return {"adapter": self.name, "ok": True, "device_id": device_id,
                    "action": action, "mode": "dry_run",
                    "would_send": {"method": method, "url": url, "json": body}}
        return self._mock_response(device_id, action, params)

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def _build_request(self, device_id: str, action: str, params: dict):
        url = f"{self.endpoint_template}/devices/{device_id}/{action}"
        return "POST", url, params or {}

    def _mock_response(self, device_id: str, action: str, params: dict) -> dict:
        return {"adapter": self.name, "ok": True, "mock": True,
                "device_id": device_id, "action": action,
                "note": "TemplateMdmAdapter stub. Implement live path with your MDM."}

    def _err(self, action: str, error_type: str, message: str) -> dict:
        return {"adapter": self.name, "ok": False, "device_id": "",
                "action": action, "error": message, "error_type": error_type}

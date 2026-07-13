"""Jamf Pro (MDM) adapter — stub listo para live.

Estado: implementación funcional contra MOCK. Para live real falta el token de
Jamf Pro API (Basic Auth con client_id/secret, o Bearer) y el endpoint de
comandos por ID de dispositivo. Hasta entonces opera en modo simulación local
y es el otro objetivo del Adapter Bounty Sprint.

Rutas live (Jamf Pro API):
  Auth : Basic <client_id:client_secret> o Bearer <token>
  Token: POST /api/v1/auth/token
  List : GET /api/v1/computers-inventory?section=GENERAL
  Action: POST /api/v1/mobile-devices/{id}/commands (verb: LOCK_DEVICE | ERASE_DEVICE | ...)
  Acciones: LOCK_DEVICE, ERASE_DEVICE, RESTART_DEVICE, UNLOCK_USER

Implementa MDMAdapter.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import requests

from core.adapters.base import MDMAdapter

# Acción UEM -> comando Jamf (verb del endpoint de commands)
JAMF_VERB = {
    "lock": "LOCK_DEVICE",
    "wipe": "ERASE_DEVICE",
    "reboot": "RESTART_DEVICE",
    "clear_passcode": "CLEAR_PASSCODE",
    "locate": "LOCATE_DEVICE",
    "message": "SEND_MESSAGE",
}


class JamfAdapter(MDMAdapter):
    name = "jamf"

    def __init__(self, org_id: str = "", endpoint_template: str = "", timeout: int = 30,
                 webhook_url: str = "", api_key: str = ""):
        self.org_id = org_id
        self.api_key = api_key or ""
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")
        self.base_url = os.environ.get("JAMF_BASE_URL", "").rstrip("/")

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id(device)
        if not self.base_url or not self.api_key:
            cmd_id = f"jamf-mock-{uuid.uuid4().hex[:12]}"
            return {
                "adapter": self.name,
                "ok": True,
                "mock": True,
                "command_id": cmd_id,
                "device_id": device_id,
                "device_name": self._dev_name(device),
                "action": action,
                "jamf_verb": JAMF_VERB.get(action),
                "params": params,
                "dry_run": dry_run,
                "note": "Jamf adapter en modo mock (sin JAMF_BASE_URL/JAMF_API_KEY). Completa el live en el Enterprise on-prem.",
            }
        verb = JAMF_VERB.get(action, action)
        url = f"{self.base_url}/api/v1/mobile-devices/{device_id}/commands"
        body = {"clientData": [{"managementId": device_id}], "commandData": {"commandType": verb}}
        if dry_run:
            return {"adapter": self.name, "ok": True, "dry_run": True, "method": "POST",
                    "url": url, "body": body, "note": "Dry run: request built but not sent."}
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {self.api_key}",
                                             "Content-Type": "application/json"},
                              json=body, timeout=self.timeout)
            return {"adapter": self.name, "ok": r.ok, "status_code": r.status_code,
                    "device_id": device_id, "action": action, "command": verb,
                    "response": r.text[:500] if r.text else ""}
        except Exception as exc:
            return {"adapter": self.name, "ok": False, "device_id": device_id,
                    "action": action, "error": f"{type(exc).__name__}: {exc}"}

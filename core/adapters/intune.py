"""Microsoft Intune (MDM) adapter — stub listo para live.

Estado: implementación funcional contra MOCK. Para llevarlo a live real falta
configurar el token de Microsoft Graph (DeviceManagementManagedDevices
/\{id\}/\{action\}) vía el flux de OAuth del Enterprise on-prem. Hasta entonces,
el adapter opera en modo simulación local (igual que SimulationAdapter) y es el
punto de partida del Adapter Bounty Sprint.

Rutas live (Microsoft Graph):
  Base : https://graph.microsoft.com/v1.0
  List : GET /deviceManagement/managedDevices
  Action: POST /deviceManagement/managedDevices/{id}/remoteLock
                .../resetPasscode  | /wipe  | /rebootNow  | /locateDevice
  Auth : Bearer <Graph token> (OAuth client-credentials con scope DeviceManagementConfiguration.ReadWrite.All)

Implementa MDMAdapter.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional

import requests

from core.adapters.base import MDMAdapter

# Mapeo acción UEM -> llamada Graph (para cuando se complete el live)
GRAPH_ACTION = {
    "lock": "remoteLock",
    "wipe": "wipe",
    "clear_passcode": "resetPasscode",
    "reboot": "rebootNow",
    "locate": "locateDevice",
    "message": "sendCustomNotification",  # body distinto
}


class IntuneAdapter(MDMAdapter):
    name = "intune"

    def __init__(self, org_id: str = "", endpoint_template: str = "", timeout: int = 30,
                 webhook_url: str = "", api_key: str = ""):
        self.org_id = org_id
        self.api_key = api_key or ""
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id(device)
        token = self.api_key or os.environ.get("INTUNE_GRAPH_TOKEN", "")
        if not token:
            # Modo mock: opera localmente (compatible con el Adapter Bounty Sprint).
            cmd_id = f"intune-mock-{uuid.uuid4().hex[:12]}"
            return {
                "adapter": self.name,
                "ok": True,
                "mock": True,
                "command_id": cmd_id,
                "device_id": device_id,
                "device_name": self._dev_name(device),
                "action": action,
                "graph_action": GRAPH_ACTION.get(action),
                "params": params,
                "dry_run": dry_run,
                "note": "Intune adapter en modo mock (sin INTUNE_GRAPH_TOKEN). Completa el live en el Enterprise on-prem.",
            }
        # Live real (cuando haya token Graph): POST al endpoint correspondiente.
        base = "https://graph.microsoft.com/v1.0"
        gaction = GRAPH_ACTION.get(action, action)
        url = f"{base}/deviceManagement/managedDevices/{device_id}/{gaction}"
        body = params or {}
        if dry_run:
            return {"adapter": self.name, "ok": True, "dry_run": True, "method": "POST",
                    "url": url, "body": body, "note": "Dry run: request built but not sent."}
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                             "Content-Type": "application/json"},
                              json=body, timeout=self.timeout)
            return {"adapter": self.name, "ok": r.ok, "status_code": r.status_code,
                    "device_id": device_id, "action": action,
                    "response": r.text[:500] if r.text else ""}
        except Exception as exc:
            return {"adapter": self.name, "ok": False, "device_id": device_id,
                    "action": action, "error": f"{type(exc).__name__}: {exc}"}

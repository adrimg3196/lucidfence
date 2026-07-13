"""Applivery UEM (MDM) live adapter.

Verified contract (2026-07-09, live contra api.applivery.io con token real):
  Auth : Authorization: Bearer <APPLIVERY_API_KEY>   (NO X-Api-Token)
  Base : https://api.applivery.io/v1
  Devices list: GET /v1/organizations/{org}/mdm/devices   (200; data.items)
  Command endpoint: POST /v1/organizations/{org}/mdm/devices/{deviceId}/commands
    NOTA: el endpoint de comandos remotos NO está en la referencia pública y
    nuestros probes devolvieron 404 en cada ruta candidata. El adapter usa la
    ruta UEM estándar y — si falla — delega la remediación vía webhook
    (patrón enterprise: Zapier/Make/PowerAutomate) y registra la delegación.
    NUNCA hace raise, así el dashboard nunca 500ea.

Implementa MDMAdapter.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

import requests

from core.adapters.base import MDMAdapter


def _safe_text(r: requests.Response) -> str:
    try:
        return r.text[:500]
    except Exception:
        return ""


class AppliveryAdapter(MDMAdapter):
    name = "applivery"

    def __init__(self, org_id: str, endpoint_template: str, timeout: int = 30,
                 webhook_url: str = "", api_key: str = ""):
        self.org_id = org_id
        self.api_key = api_key or ""
        # Ruta estándar de comando UEM (ver docstring sobre probes 404).
        self.endpoint_template = endpoint_template or \
            "/organizations/{org_id}/mdm/devices/{device_id}/commands"
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")

    def _headers(self) -> dict:
        key = self.api_key or os.environ.get("APPLIVERY_API_KEY") or os.environ.get("applivery_api_key")
        if not key:
            raise RuntimeError("APPLIVERY_API_KEY not set; cannot run live UEM actions.")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _delegate_webhook(self, device: Any, action: str, params: dict, reason: str) -> dict:
        device_id = self._dev_id(device)
        payload = {
            "event": "geofence_remediation",
            "device_id": device_id,
            "device_name": self._dev_name(device),
            "platform": getattr(device, "platform", None) if not isinstance(device, dict) else device.get("platform"),
            "action": action,
            "params": params or {},
            "org_id": self.org_id,
            "reason": reason,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if not self.webhook_url:
            return {
                "delegated": False,
                "webhook": None,
                "note": "No remediation webhook configured; action not delegated.",
            }
        try:
            r = requests.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            accepted = 200 <= r.status_code < 300
            return {
                "delegated": accepted,
                "attempted": True,
                "webhook": self.webhook_url,
                "webhook_status": r.status_code,
                "webhook_response": _safe_text(r),
                "payload": payload,
                **({} if accepted else {"error": f"webhook returned HTTP {r.status_code}"}),
            }
        except Exception as exc:
            return {
                "delegated": False,
                "webhook": self.webhook_url,
                "error": f"webhook failed: {type(exc).__name__}: {exc}",
            }

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        key = self.api_key or os.environ.get("APPLIVERY_API_KEY") or os.environ.get("applivery_api_key")
        device_id = self._dev_id(device)
        if not key:
            return {
                "adapter": self.name,
                "ok": False,
                "device_id": device_id,
                "action": action,
                "error": "APPLIVERY_API_KEY not set",
            }
        path = self.endpoint_template.format(org_id=self.org_id, device_id=device_id)
        base = os.environ.get("APPLIVERY_API_BASE", "https://api.applivery.io/v1").rstrip("/")
        url = f"{base}{path}"
        body = {"command": action, "params": params or {}}
        if dry_run:
            return {
                "adapter": self.name,
                "ok": True,
                "dry_run": True,
                "device_id": device_id,
                "action": action,
                "method": "POST",
                "url": url,
                "body": body,
                "note": "Dry run: request built but not sent.",
            }
        # 1) intenta el comando UEM nativo
        http_result = None
        try:
            r = requests.post(url, headers=self._headers(), json=body, timeout=self.timeout)
            http_result = {"status_code": r.status_code, "ok": r.ok, "response": _safe_text(r)}
        except Exception as exc:
            http_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if http_result.get("ok"):
            return {
                "adapter": self.name,
                "ok": True,
                "device_id": device_id,
                "action": action,
                "method": "POST",
                "url": url,
                "status_code": http_result.get("status_code"),
                "response": http_result.get("response"),
            }
        # 2) nativo no disponible -> delega vía webhook de remediación
        reason = f"Applivery command endpoint unavailable (HTTP {http_result.get('status_code') or http_result.get('error')})"
        delegation = self._delegate_webhook(device, action, params, reason)
        return {
            "adapter": self.name,
            "ok": False,
            "delegated": delegation.get("delegated", False),
            "device_id": device_id,
            "action": action,
            "method": "POST",
            "url": url,
            "http_result": http_result,
            "delegation": delegation,
            "note": "Native command failed; remediation delegated via webhook."
            if delegation.get("delegated")
            else "Native command failed; no remediation webhook configured.",
        }

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

from lucidfence.core.adapters.base import MDMAdapter


def _safe_text(r: requests.Response) -> str:
    try:
        return r.text[:500]
    except Exception:
        return ""


class AppliveryAdapter(MDMAdapter):
    name = "applivery"

    #: Applivery publica el passthrough de política de Android Enterprise
    #: (verificado 2026-08-02 vía el MCP de su doc oficial):
    #:   PUT /v1/organizations/{org}/mdm/android/enterprise/policies/{emmPolicyId}
    #: cuyo campo `config` es, literalmente, el "Google Android Enterprise
    #: policy configuration object". Por eso aquí sí marcamos la capacidad.
    supports_amapi_policy = True

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

    # --- AMAPI (declarativo) ---

    def _apply_amapi_policy(self, device: Any, params: dict) -> dict:
        """Genera el documento de política AMAPI para el estado de geocerca.

        Offline a propósito, igual que `apply_ddm` en Jamf: producimos el
        contrato, no lo publicamos. Publicar exigiría el `emmPolicyId` del
        tenant y mutaría la política de un cliente real; esa entrega la decide
        quien integra, con el cuerpo que devolvemos aquí.

        Si el dispositivo no es Android gestionado por AMAPI (o no sabemos su
        modo de gestión) devuelve ``fallback="imperative"`` para que el llamante
        siga por el camino de comandos de siempre.
        """
        from lucidfence.core.amapi import (
            build_fence_patch,
            management_mode_of,
            parse_device_compliance,
            supports_amapi,
        )

        device_id = self._dev_id(device)
        if not supports_amapi(device):
            return {
                "adapter": self.name, "ok": False, "device_id": device_id,
                "action": "apply_amapi_policy", "error": "amapi_unsupported",
                "fallback": "imperative",
            }
        policy = (params or {}).get("policy")
        if not policy:
            return {
                "adapter": self.name, "ok": False, "device_id": device_id,
                "action": "apply_amapi_policy", "error": "missing_parameter",
                "detail": "Missing 'policy' parameter",
            }
        fence_state = str(
            (device.get("fence_state") if isinstance(device, dict)
             else getattr(device, "fence_state", None)) or "unknown"
        )
        try:
            built = build_fence_patch(policy, fence_state, device)
        except ValueError as exc:
            return {
                "adapter": self.name, "ok": False, "device_id": device_id,
                "action": "apply_amapi_policy", "error": "invalid_restrictions",
                "detail": str(exc),
            }

        result = {
            "adapter": self.name, "ok": True, "device_id": device_id,
            "action": "apply_amapi_policy",
            "management_mode": management_mode_of(device),
            "fence_state": fence_state,
            "patch": built["patch"],
            # `update_mask` es para el PATCH directo de AMAPI. El passthrough de
            # Applivery es un PUT que reemplaza `config` entero, así que allí se
            # envía el objeto completo, no la máscara.
            "update_mask": built["update_mask"],
            "skipped": built["skipped"],
            "delivery": "offline",
        }
        # Readback: si el llamante ya trae el recurso Device de AMAPI, lo
        # traducimos al estado persistido (el engine hace merge, no reemplazo).
        readback = parse_device_compliance((params or {}).get("device_resource"))
        if readback:
            result["device_state"] = readback
        return result

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        if action == "apply_amapi_policy":
            return self._apply_amapi_policy(device, params or {})
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

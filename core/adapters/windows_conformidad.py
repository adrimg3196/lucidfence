"""Windows conformidad (compliance) adapter for LucidFence.

Reports on-device compliance posture for Windows 10/11 endpoints managed
via Microsoft Intune (Windows CSP reporting) or standalone WMI probes.
The adapter is read-only — it surfaces the compliance signal so the
dashboard can fence/lock/wipe based on the policy output, but does not
itself issue remediation commands.

Implementa MDMAdapter (read-only contract: action='report').
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

from core.adapters.base import MDMAdapter


class WindowsConformidadAdapter(MDMAdapter):
    """Read-only Windows compliance posture reporter.

    In live mode, requires Intune tenant creds (INTUNE_TENANT_ID/
    CLIENT_ID/CLIENT_SECRET env vars) and queries
    `/deviceManagement/managedDevices?$filter=operatingSystem eq 'Windows'`.

    In mock mode (default, no creds), returns a stable synthetic report
    so the dashboard pipeline is exercisable end-to-end without a
    Windows tenant.
    """

    name = "windows_conformidad"

    #: The contract for compliance reporting is action="report" only.
    #: Other actions degrade to a structured "unsupported_action" error
    #: so the dashboard never crashes on a Windows-only deployment.
    SUPPORTED_ACTIONS = {"report"}

    def __init__(
        self,
        org_id: str = "",
        endpoint_template: str = "https://graph.microsoft.com/v1.0",
        timeout: int = 30,
        webhook_url: str = "",
        api_key: str = "",
        live: bool = False,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ):
        self.org_id = org_id
        self.endpoint_template = endpoint_template
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")
        self.api_key = api_key or ""
        self.live = live
        self.tenant_id = tenant_id or os.environ.get("INTUNE_TENANT_ID", "")
        self.client_id = client_id or os.environ.get("INTUNE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("INTUNE_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # --- helpers ---

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def _is_token_valid(self) -> bool:
        return bool(self._token) and time.time() < self._token_expires_at - 30

    def _fetch_token(self) -> str:
        """OAuth client_credentials grant against Azure AD.

        Self-contained (does not depend on IntuneAdapter to keep the
        SDK surface small — community adapters should not need to
        import another adapter's internals).
        """
        import requests as _req
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise RuntimeError(
                "WindowsConformidadAdapter live mode requires "
                "tenant_id / client_id / client_secret (or INTUNE_* env vars)"
            )
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        resp = _req.post(
            url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Graph token request HTTP {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Graph token response missing access_token")
        self._token = token
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return token

    def _auth_headers(self) -> dict:
        if not self._is_token_valid():
            self._fetch_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    # --- public API ---

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id_str(device)
        if action not in self.SUPPORTED_ACTIONS:
            return self._err(action, "unsupported_action",
                             f"action {action!r} not supported (only 'report')")
        if self.live:
            return self._report_live(device_id, params, dry_run)
        return self._report_mock(device_id, params, dry_run)

    # --- live path (Microsoft Graph) ---

    def _report_live(self, device_id: str, params: dict, dry_run: bool) -> dict:
        import requests as _req
        if not (self.tenant_id and self.client_id and self.client_secret):
            return self._err("report", "auth_error",
                             "Windows conformity live mode requires "
                             "INTUNE_TENANT_ID / INTUNE_CLIENT_ID / INTUNE_CLIENT_SECRET")
        url = (
            f"{self.endpoint_template}/deviceManagement/managedDevices"
            "?$filter=operatingSystem%20eq%20'Windows'"
            "&$select=id,deviceName,operatingSystem,osVersion,complianceState,"
            "isEncrypted,deviceType,lastSyncDateTime"
        )
        if dry_run:
            return {
                "adapter": self.name,
                "ok": True,
                "mode": "dry_run",
                "would_send": {"method": "GET", "url": url,
                                "headers": {"Authorization": "Bearer <stub>"}},
            }
        try:
            resp = _req.get(url, headers=self._auth_headers(), timeout=self.timeout)
        except _req.RequestException as exc:
            return self._err("report", "transport_error", repr(exc))
        if resp.status_code in (401, 403):
            return self._err("report", "auth_error",
                             f"Graph rejected {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 500:
            return self._err("report", "transport_error",
                             f"Graph {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            return self._err("report", "graph_rejected",
                             f"Graph {resp.status_code}: {resp.text[:200]}")
        items = resp.json().get("value", [])
        devices = [self._normalize(item) for item in items]
        return {
            "adapter": self.name,
            "ok": True,
            "mode": "live",
            "action": "report",
            "count": len(devices),
            "devices": devices,
            "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @staticmethod
    def _normalize(item: dict) -> dict:
        return {
            "device_id": item.get("id"),
            "name": item.get("deviceName"),
            "os": item.get("operatingSystem"),
            "os_version": item.get("osVersion"),
            "compliant": item.get("complianceState") == "compliant",
            "encrypted": bool(item.get("isEncrypted")),
            "device_type": item.get("deviceType"),
            "last_sync": item.get("lastSyncDateTime"),
        }

    # --- mock fallback (stable synthetic report) ---

    def _report_mock(self, device_id: str, params: dict, dry_run: bool) -> dict:
        # Deterministic mock keyed off device_id so callers can assert.
        seed = abs(hash(device_id or "unknown")) if device_id else 0
        compliant = bool(seed % 2 == 0)
        encrypted = bool(seed % 3 != 0)
        if dry_run:
            return {
                "adapter": self.name,
                "ok": True,
                "mode": "dry_run",
                "would_send": {"method": "GET", "url": "<graph-windows>"},
            }
        device_obj = {
            "device_id": device_id or f"win-mock-{uuid.uuid4().hex[:8]}",
            "name": f"Windows device {device_id or 'unknown'}",
            "os": "Windows",
            "os_version": "10.0.22631",
            "compliant": compliant,
            "encrypted": encrypted,
            "device_type": "desktop",
            "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        report: dict = {
            "adapter": self.name,
            "ok": True,
            "mode": "mock",
            "action": "report",
            "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "devices": [device_obj],
            "summary": {
                "compliant": compliant,
                "encrypted": encrypted,
                "policy_id": params.get("policy_id", "default"),
            },
            "note": "WindowsConformidadAdapter mock mode (no tenant creds).",
        }
        report["count"] = len(report["devices"])
        return report

    # --- error helpers ---

    def _err(self, action: str, error_type: str, message: str) -> dict:
        return {
            "adapter": self.name,
            "ok": False,
            "device_id": "",
            "action": action,
            "error": message,
            "error_type": error_type,
        }


def build_windows_conformidad_adapter_from_config(cfg: dict) -> WindowsConformidadAdapter:
    """Construct from a config dict (mirrors IntuneAdapter helper shape)."""
    wcfg = (cfg.get("mdm") or {}).get("windows") or {}
    return WindowsConformidadAdapter(
        live=wcfg.get("live", False),
        tenant_id=wcfg.get("tenant_id", ""),
        client_id=wcfg.get("client_id", ""),
        client_secret=wcfg.get("client_secret", ""),
        endpoint_template=wcfg.get("endpoint_template",
                                   "https://graph.microsoft.com/v1.0"),
    )